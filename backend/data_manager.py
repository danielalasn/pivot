import sqlite3
import pandas as pd
import os
from datetime import date, datetime, timezone
import calendar
import finnhub
import time
import json
from dotenv import load_dotenv
from pathlib import Path
from flask_login import current_user
from sqlalchemy import create_engine, text
from functools import lru_cache
import time
from backend.extensions import cache
from flask_login import current_user

# --- CONFIGURACIÓN BASE ---
base_dir = Path(__file__).resolve().parent.parent
env_path = base_dir / '.env'
load_dotenv(dotenv_path=env_path)

RENDER_DB_URL = os.getenv("DATABASE_URL")

# Detectar si estamos en Postgres
IS_POSTGRES = RENDER_DB_URL is not None and "postgres" in RENDER_DB_URL

DB_DIR = "data"
DB_PATH = os.path.join(DB_DIR, "pivot.db")

api_key = os.getenv("FINNHUB_API_KEY")

if api_key:
    finnhub_client = finnhub.Client(api_key=api_key)
else:
    print("⚠️ ADVERTENCIA: No se encontró FINNHUB_API_KEY en el archivo .env")
    finnhub_client = None 
# --- CLASES ADAPTADORAS (Para compatibilidad SQLite -> Postgres) ---

# --- CLASES ADAPTADORAS MEJORADAS ---

# --- FUNCIÓN MAESTRA DE LIMPIEZA ---
# En backend/data_manager.py

def clear_all_caches():
    """
    Borra la memoria de todas las funciones pesadas.
    """
    try:
        # 1. Borrar datos de Dashboard Principal
        cache.delete_memoized(get_dashboard_metrics)
        cache.delete_memoized(get_transactions_df)
        cache.delete_memoized(get_monthly_summary)
        cache.delete_memoized(get_category_summary)
        
        # 2. Borrar datos de Patrimonio y Cuentas
        cache.delete_memoized(get_net_worth_breakdown)
        cache.delete_memoized(get_stocks_data)
        
        # 3. NUEVO: Borrar datos de Distribución (Funciones internas con guion bajo)
        cache.delete_memoized(_get_fixed_costs_df_cached)
        cache.delete_memoized(_get_savings_goals_df_cached)
        cache.delete_memoized(_get_distribution_rules_cached)
        cache.delete_memoized(_get_income_events_df_cached)
        cache.delete_memoized(_get_full_networth_history_cached)
        capture_daily_snapshot()
        print("🧹 Caché limpiado: Datos frescos listos.")
    except Exception as e:
        print(f"⚠️ Error limpiando caché: {e}")


class PostgresCursorWrapper:
    def __init__(self, original_cursor):
        self.cursor = original_cursor

    def execute(self, sql, params=None):
        # Traducción de sintaxis SQLite (?) a Postgres (%s)
        sql = sql.replace('?', '%s')
        try:
            return self.cursor.execute(sql, params)
        except Exception as e:
            print(f"🔥 Error SQL (PG): {e}\nQuery: {sql}\nParams: {params}")
            raise e

    def executemany(self, sql, params_list):
        sql = sql.replace('?', '%s')
        return self.cursor.executemany(sql, params_list)

    # --- MÉTODOS REQUERIDOS POR PANDAS Y EL SISTEMA ---
    def fetchone(self): return self.cursor.fetchone()
    def fetchall(self): return self.cursor.fetchall()
    def close(self): return self.cursor.close()
    
    # ESTE ES EL QUE FALTABA PARA PANDAS
    @property
    def description(self):
        return self.cursor.description

    @property
    def rowcount(self): return self.cursor.rowcount
    
    @property
    def lastrowid(self):
        try:
            return self.cursor.fetchone()[0]
        except:
            return None

    # Context Manager
    def __enter__(self): return self
    def __exit__(self, exc_type, exc_val, exc_tb): self.close()
    
    # Iteración
    def __iter__(self): return self.cursor.__iter__()
    def __next__(self): return self.cursor.__next__()

class PostgresConnectionWrapper:
    def __init__(self, original_conn):
        self.conn = original_conn

    def cursor(self):
        return PostgresCursorWrapper(self.conn.cursor())

    def commit(self): return self.conn.commit()
    def rollback(self): return self.conn.rollback()
    def close(self): return self.conn.close()
    
    # Context Manager
    def __enter__(self): return self
    def __exit__(self, exc_type, exc_val, exc_tb): self.close()

    # Pandas a veces llama a execute directo en la conexión
    def execute(self, sql, params=None):
        cur = self.cursor()
        try:
            cur.execute(sql, params)
            return cur
        except Exception as e:
            # Si falla, aseguramos cerrar el cursor implícito
            cur.close()
            raise e
        
def check_column_exists(cursor, table_name, column_name):
    """Verifica si una columna existe (Compatible SQLite/Postgres)."""
    if IS_POSTGRES:
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name=%s AND column_name=%s
        """, (table_name, column_name))
        return cursor.fetchone() is not None
    else:
        # SQLite
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = [info[1] for info in cursor.fetchall()]
        return column_name in columns
    
pg_engine = None

if RENDER_DB_URL:
    db_url = RENDER_DB_URL.replace("postgres://", "postgresql+psycopg2://", 1)
    # Pool de conexiones: mantiene 5 conexiones abiertas, recicla cada 1800s
    pg_engine = create_engine(db_url, pool_size=5, max_overflow=10, pool_recycle=1800)

def get_connection():
    if pg_engine:
        # 1. Modo PRODUCCIÓN (PostgreSQL con Pool)
        try:
            # Obtenemos una conexión del pool existente (¡Instantáneo!)
            raw_conn = pg_engine.raw_connection()
            return PostgresConnectionWrapper(raw_conn)
        except Exception as e:
            raise ConnectionError(f"Error conectando a Postgres: {e}")
    else:
        # 2. Modo DESARROLLO LOCAL (SQLite)
        return sqlite3.connect(os.path.join("data", "pivot.db"))
    

def get_uid():
    """Retorna el ID del usuario actual de manera segura."""
    if current_user and current_user.is_authenticated:
        return current_user.id
    return None 


# --- LISTAS DE DETECCIÓN MANUAL (Para forzar tipos correctos) ---
KNOWN_ETFS = [
    'SPY', 'QQQ', 'QTUM', 'VOO', 'IVV', 'DIA', 'IWM', 'GLD', 'SLV', 
    'SOXX', 'SMH', 'ARKK', 'TQQQ', 'SQQQ', 'VTI', 'VEA', 'VWO', 'SCHD', 
    'JEPI', 'XLF', 'XLK', 'XLE', 'XLY', 'XLV', 'XLI', 'XLP', 'XLU', 'XLB'
]

def detect_asset_type(ticker, sector=None):
    """Determina si es Stock, ETF o Cripto."""
    clean = ticker.strip().upper()
    
    # 1. Cripto (Nombres comunes o pares con USD)
    if "BTC" in clean or "ETH" in clean or "SOL" in clean or "-USD" in clean:
        return "CRYPTO_FOREX"
    
    # 2. ETFs (Lista manual)
    if clean in KNOWN_ETFS:
        return "ETF"
        
    # 3. Por Sector (Si Finnhub nos dice que es fondo)
    if sector and isinstance(sector, str):
        sec_low = sector.lower()
        if "etf" in sec_low or "fund" in sec_low:
            return "ETF"
            
    return "Stock"
# --- GESTIÓN DE CUENTAS ---

# Definición robusta con kwargs para evitar errores si faltan argumentos
def add_account(name, acc_type, balance, bank_name="-", credit_limit=0, payment_day=None, cutoff_day=None, interest_rate=0, deferred_balance=0, **kwargs):
    conn = get_connection()
    cursor = conn.cursor()
    uid = get_uid() # Obtener ID del usuario
    try:
        # Calcular orden solo para este usuario
        cursor.execute("SELECT MAX(display_order) FROM accounts WHERE user_id = ?", (uid,))
        res = cursor.fetchone()
        new_order = (res[0] if res[0] is not None else 0) + 1

        cursor.execute("""
            INSERT INTO accounts (user_id, name, type, current_balance, bank_name, credit_limit, payment_day, cutoff_day, interest_rate, display_order, deferred_balance)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (uid, name, acc_type, balance, bank_name, credit_limit, payment_day, cutoff_day, interest_rate, new_order, deferred_balance))
        conn.commit()
        clear_all_caches()
        return True, "Cuenta creada exitosamente."
    except Exception as e:
        return False, f"Error al crear: {str(e)}"
    finally:
        conn.close()

def update_account(account_id, name, acc_type, balance, bank_name, credit_limit, payment_day, cutoff_day, interest_rate=0, deferred_balance=0, **kwargs):
    conn = get_connection()
    cursor = conn.cursor()
    uid = get_uid()
    try:
        # Añadimos "AND user_id = ?" para seguridad: nadie edita lo que no es suyo
        cursor.execute("""
            UPDATE accounts 
            SET name = ?, type = ?, current_balance = ?, bank_name = ?, credit_limit = ?, payment_day = ?, cutoff_day = ?, interest_rate = ?, deferred_balance = ?
            WHERE id = ? AND user_id = ?
        """, (name, acc_type, balance, bank_name, credit_limit, payment_day, cutoff_day, interest_rate, deferred_balance, account_id, uid))
        conn.commit()
        return True, "Cuenta actualizada."
    except Exception as e:
        return False, str(e)
    finally:
        conn.close()

def delete_account(account_id):
    conn = get_connection()
    cursor = conn.cursor()
    uid = get_uid()
    try:
        # Solo borrar si pertenece al usuario
        cursor.execute("DELETE FROM transactions WHERE account_id = ? AND user_id = ?", (account_id, uid))
        cursor.execute("DELETE FROM installments WHERE account_id = ? AND user_id = ?", (account_id, uid))
        cursor.execute("DELETE FROM accounts WHERE id = ? AND user_id = ?", (account_id, uid))
        conn.commit()
        return True, "Cuenta eliminada."
    except Exception as e: return False, str(e)
    finally: conn.close()

def get_accounts_by_category(category_group):
    conn = get_connection()
    uid = get_uid()
    try:
        # Filtramos por usuario
        df = pd.read_sql_query("SELECT * FROM accounts WHERE user_id = ? ORDER BY display_order ASC", conn, params=(uid,))
        if df.empty: return df
        
        df.fillna(0, inplace=True)
        df['bank_name'] = df['bank_name'].replace(0, "-").replace("0", "-")
        
        if category_group == 'Credit':
            df = df[df['type'] == 'Credit']
            # También filtramos installments por usuario
            installments_df = pd.read_sql_query("SELECT * FROM installments WHERE user_id = ?", conn, params=(uid,))
            
            def calc_total_installments(acc_id):
                if installments_df.empty: return 0.0
                my_installs = installments_df[installments_df['account_id'] == acc_id]
                total = 0.0
                for _, row in my_installs.iterrows():
                    if row['total_quotas'] > 0:
                        total_with_int = row['total_amount'] * (1 + (row['interest_rate'] / 100))
                        quota_val = total_with_int / row['total_quotas']
                        remaining = row['total_quotas'] - row['paid_quotas']
                        total += quota_val * remaining
                return total

            df['installments_pending_total'] = df['id'].apply(calc_total_installments)
        else:
            df = df[df['type'] != 'Credit']
            
        df.reset_index(drop=True, inplace=True)
    except: df = pd.DataFrame()
    finally: conn.close()
    return df

def change_account_order(account_id, direction, category_group):
    # Reutiliza get_accounts_by_category que ya filtra por usuario, así que es seguro
    df = get_accounts_by_category(category_group)
    if df.empty: return
    try:
        idx = df.index[df['id'] == account_id].tolist()[0]
    except: return

    swap_idx = None
    if direction == 'up' and idx > 0: swap_idx = idx - 1
    elif direction == 'down' and idx < len(df) - 1: swap_idx = idx + 1
    
    if swap_idx is not None:
        id1, order1 = df.iloc[idx]['id'], df.iloc[idx]['display_order']
        id2, order2 = df.iloc[swap_idx]['id'], df.iloc[swap_idx]['display_order']
        # Validar consistencia
        if order1 == order2: order1, order2 = idx + 1, swap_idx + 1
        
        conn = get_connection()
        uid = get_uid()
        # Update seguro con user_id
        conn.execute("UPDATE accounts SET display_order = ? WHERE id = ? AND user_id = ?", (int(order2), int(id1), uid))
        conn.execute("UPDATE accounts SET display_order = ? WHERE id = ? AND user_id = ?", (int(order1), int(id2), uid))
        conn.commit()
        conn.close()

def get_account_options():
    conn = get_connection()
    uid = get_uid()
    options = []
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, bank_name, type, current_balance, credit_limit FROM accounts WHERE user_id = ? ORDER BY display_order ASC", (uid,))
        data = cursor.fetchall()
        for i, name, bank, atype, balance, limit in data:
            if atype == 'Credit':
                val = float(limit) - float(balance)
                amt_str = f"Disponible: ${val:,.2f}"
            else:
                amt_str = f"Saldo: ${balance:,.2f}"
            options.append({'label': f"{name} - {bank} ({atype})\n{amt_str}", 'value': i})
    except: pass
    
    # Reserva (Usuario específico)
    try: res = get_credit_abono_reserve()
    except: res = 0.0
    options.append({'label': f"Reserva de Abono\nDisponible: ${res:,.2f}", 'value': 'RESERVE'})
    
    conn.close()
    return options


def get_account_type_summary():
    """Resumen de Activos vs Pasivos para el Mini-Dashboard de Cuentas."""
    conn = get_connection()
    uid = get_uid()
    summary = {}
    try:
        # 1. Obtener cuentas del usuario
        df_accounts = pd.read_sql_query("SELECT id, type, current_balance FROM accounts WHERE user_id = ?", conn, params=(uid,))
        
        liquid_assets = df_accounts[df_accounts['type'].isin(['Debit', 'Cash'])]['current_balance'].sum()
        total_liabilities_cards = df_accounts[df_accounts['type'] == 'Credit']['current_balance'].sum()
        
        # 2. Reserva del usuario
        try: reserve_bal = get_credit_abono_reserve()
        except: reserve_bal = 0.0
            
        # 3. IOU (Informal) del usuario
        df_iou = pd.read_sql_query("SELECT type, current_amount FROM iou WHERE status = 'Pending' AND user_id = ?", conn, params=(uid,))
        liabilities_informal = df_iou[df_iou['type'] == 'Payable']['current_amount'].sum() if not df_iou.empty else 0.0
        
        # 4. Obtener detalle de Cuotas (del usuario)
        credit_data = get_credit_summary_data() 
        installments_debt = credit_data['total_installments']

        # Consolidados
        summary['TotalAssets'] = liquid_assets + reserve_bal
        summary['LiquidAssets'] = liquid_assets
        summary['ReserveAssets'] = reserve_bal
        
        total_liabilities = total_liabilities_cards + liabilities_informal
        immediate_debt = max(0, total_liabilities - installments_debt)
        
        summary['TotalLiabilities'] = total_liabilities
        summary['InstallmentsDebt'] = installments_debt
        summary['ImmediateDebt'] = immediate_debt
        
    except Exception as e:
        for k in ['TotalAssets', 'LiquidAssets', 'ReserveAssets', 'TotalLiabilities', 'InstallmentsDebt', 'ImmediateDebt']:
            summary[k] = 0.0
    finally:
        conn.close()
    return summary

# --- EN backend/data_manager.py ---

def batch_update_account_orders(id_list):
    """
    Recibe una lista de IDs [id1, id2, id3...] en el orden deseado
    y actualiza el campo display_order en la base de datos.
    """
    conn = get_connection()
    uid = get_uid()
    try:
        cursor = conn.cursor()
        # Iteramos y actualizamos el orden según la posición en la lista
        for index, acc_id in enumerate(id_list):
            cursor.execute(
                "UPDATE accounts SET display_order = ? WHERE id = ? AND user_id = ?", 
                (index + 1, acc_id, uid)
            )
        conn.commit()
        return True, "Orden guardado."
    except Exception as e:
        return False, str(e)
    finally:
        conn.close()

def get_debit_category_summary():
    """Obtiene la suma de transacciones por categoría y tipo (Expense/Income) 
       solo para cuentas de Débito/Efectivo."""
    conn = get_connection()
    try:
        # 1. Obtener IDs de cuentas Debit y Cash
        debit_ids = pd.read_sql_query("SELECT id FROM accounts WHERE type IN ('Debit', 'Cash')", conn)['id'].tolist()
        
        if not debit_ids:
            return pd.DataFrame()
            
        # 2. Convertir la lista de IDs a string para la cláusula SQL IN
        id_list_str = '(' + ', '.join(map(str, debit_ids)) + ')'
        
        query = f"""
            SELECT category, type, SUM(amount) as total_amount
            FROM transactions 
            WHERE account_id IN {id_list_str}
            GROUP BY category, type
        """
        df = pd.read_sql_query(query, conn)
        return df
    except Exception as e:
        print(f"Error getting debit category summary: {e}")
        return pd.DataFrame()
    finally:
        conn.close()

# data_manager.py


def get_debit_bank_summary():
    """Saldo por banco (Débito/Cash) del usuario."""
    conn = get_connection()
    uid = get_uid()
    try:
        # CORRECCIÓN PG: HAVING SUM(...) > 0 en vez de HAVING total_balance > 0
        df = pd.read_sql_query("""
            SELECT bank_name, SUM(current_balance) as total_balance
            FROM accounts
            WHERE type IN ('Debit', 'Cash') AND user_id = ?
            GROUP BY bank_name
            HAVING SUM(current_balance) > 0
        """, conn, params=(uid,))
        return df
    finally: conn.close()

def calculate_installment_value(amount, rate, total_quotas):
    """
    Calcula el valor de una cuota individual usando la misma lógica para todo el sistema.
    Maneja Tasa 0 correctamente.
    """
    if total_quotas == 0: return 0.0
    
    if rate > 0:
        # Fórmula de Amortización (PMT)
        i = rate / 12 / 100
        n = total_quotas
        denominator = ((1 + i) ** n) - 1
        if denominator != 0:
            numerator = i * ((1 + i) ** n)
            q_val = amount * (numerator / denominator)
            return q_val
    
    # Si Tasa es 0 o cálculo falla
    return amount / total_quotas


def get_credit_summary_data():
    """
    Métricas de Crédito corregidas para usar la fórmula exacta de cuotas.
    """
    conn = get_connection()
    uid = get_uid()
    summary = {'total_limit': 0.0, 'total_debt': 0.0, 'total_installments': 0.0}
    try:
        # 1. Totales de Tarjetas
        df = pd.read_sql_query("SELECT id, credit_limit, current_balance FROM accounts WHERE type = 'Credit' AND user_id = ?", conn, params=(uid,))
        
        if df.empty: return summary

        summary['total_limit'] = df['credit_limit'].sum()
        summary['total_debt'] = df['current_balance'].sum()
        
        # 2. Cálculo Preciso de Cuotas Pendientes
        installments_df = pd.read_sql_query("SELECT * FROM installments WHERE user_id = ?", conn, params=(uid,))
        total_pending_value = 0.0
        
        # Iteramos y calculamos usando la función unificada
        for _, inst_row in installments_df.iterrows():
            tq = inst_row['total_quotas']
            pq = inst_row['paid_quotas']
            
            if tq > 0 and pq < tq:
                # Usamos la función helper para que coincida con el frontend
                q_val = calculate_installment_value(inst_row['total_amount'], inst_row['interest_rate'], tq)
                
                remaining_quotas = tq - pq
                total_pending_value += q_val * remaining_quotas
        
        summary['total_installments'] = total_pending_value
        
    finally:
        conn.close()
    return summary

def get_asset_type_summary():
    """Calcula el saldo total agrupado por el tipo de cuenta (Debit, Cash)."""
    conn = get_connection()
    try:
        # CORRECCIÓN PG: HAVING SUM(...) > 0
        query = """
            SELECT type, SUM(current_balance) as total_balance
            FROM accounts
            WHERE type IN ('Debit', 'Cash')
            GROUP BY type
            HAVING SUM(current_balance) > 0
        """
        df = pd.read_sql_query(query, conn)
        return df
    except Exception as e:
        print(f"Error getting asset type summary: {e}")
        return pd.DataFrame()
    finally:
        conn.close()
# --- FINANCIAMIENTOS (INSTALLMENTS) ---
# En backend/data_manager.py

# --- FINANCIAMIENTOS (INSTALLMENTS) ---

def add_installment(account_id, name, amount, rate, total_q, paid_q, pay_day):
    conn = get_connection()
    cursor = conn.cursor()
    uid = get_uid() # <--- IMPORTANTE: Obtenemos el usuario
    try:
        cursor.execute("""
            INSERT INTO installments (user_id, account_id, name, total_amount, interest_rate, total_quotas, paid_quotas, payment_day)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (uid, account_id, name, amount, rate, total_q, paid_q, pay_day))
        conn.commit()
        return True, "Financiamiento agregado."
    except Exception as e:
        return False, str(e)
    finally:
        conn.close()

def update_installment(inst_id, name, amount, rate, total_q, paid_q, pay_day):
    conn = get_connection()
    cursor = conn.cursor()
    uid = get_uid()
    try:
        # Agregamos AND user_id = ? para seguridad
        cursor.execute("""
            UPDATE installments 
            SET name = ?, total_amount = ?, interest_rate = ?, total_quotas = ?, paid_quotas = ?, payment_day = ?
            WHERE id = ? AND user_id = ?
        """, (name, amount, rate, total_q, paid_q, pay_day, inst_id, uid))
        conn.commit()
        return True, "Financiamiento actualizado."
    except Exception as e:
        return False, str(e)
    finally:
        conn.close()

def get_installments(account_id):
    conn = get_connection()
    uid = get_uid()
    try:
        # Filtramos también por usuario para que nadie vea datos ajenos
        df = pd.read_sql_query("SELECT * FROM installments WHERE account_id = ? AND user_id = ?", conn, params=(account_id, uid))
    except: df = pd.DataFrame()
    conn.close()
    return df

def delete_installment(installment_id):
    conn = get_connection()
    cursor = conn.cursor()
    uid = get_uid()
    try:
        cursor.execute("DELETE FROM installments WHERE id = ? AND user_id = ?", (installment_id, uid))
        conn.commit()
        return True, "Eliminado."
    except Exception as e: return False, str(e)
    finally: conn.close()
# --- TRANSACCIONES Y ANALYTICS ---
# backend/data_manager.py

@cache.memoize(timeout=60)
def get_dashboard_metrics(user_id, selected_month_str=None):
    """
    Calcula Ingresos y Gastos del mes directamente en SQL.
    Mucho más rápido que procesar Pandas.
    """
    conn = get_connection()
    uid = get_uid()
    
    try:
        # 1. Definir fechas de inicio y fin del mes
        if not selected_month_str:
            today = date.today()
            start_date = date(today.year, today.month, 1).strftime('%Y-%m-%d')
            # Truco para fin de mes: Primer día del mes siguiente - 1 día, o simple lógica de string
            # Para SQL simple, basta con filtrar por string 'YYYY-MM'
            month_filter = today.strftime('%Y-%m')
        else:
            month_filter = selected_month_str

        # 2. Obtener categorías excluidas (para no sumar transferencias)
        excluded = get_excluded_categories_list()
        if excluded:
            placeholders = ','.join([f"'{x}'" for x in excluded])
            exclude_clause = f"AND category NOT IN ({placeholders})"
        else:
            exclude_clause = ""

        # 3. QUERY OPTIMIZADA
        # Suma condicional en una sola consulta
        query = f"""
            SELECT 
                SUM(CASE WHEN type = 'Income' THEN amount ELSE 0 END) as total_income,
                SUM(CASE WHEN type = 'Expense' THEN amount ELSE 0 END) as total_expense
            FROM transactions 
            WHERE user_id = %s 
              AND TO_CHAR(date::DATE, 'YYYY-MM') = %s
              {exclude_clause}
        """
        
        # Ejecutar (usamos cursor directo para velocidad, sin Pandas)
        cursor = conn.cursor()
        cursor.execute(query, (uid, month_filter))
        res = cursor.fetchone()
        
        income = res[0] if res and res[0] else 0.0
        expense = res[1] if res and res[1] else 0.0
        
        return income, expense

    except Exception as e:
        print(f"Error optimizado metrics: {e}")
        return 0.0, 0.0
    finally:
        conn.close()


def _check_sufficient_funds(cursor, account_id, amount, user_id):
    """
    Verifica si la cuenta tiene fondos (o crédito) suficiente.
    Retorna: (True/False, Mensaje de error)
    """
    cursor.execute("SELECT type, current_balance, credit_limit, name FROM accounts WHERE id = ? AND user_id = ?", (account_id, user_id))
    res = cursor.fetchone()
    
    if not res: 
        return False, "Cuenta no encontrada."
    
    acc_type, current_balance, credit_limit, acc_name = res
    
    # CASO 1: TARJETA DE CRÉDITO
    # Disponible = Límite - Deuda Actual
    if acc_type == 'Credit':
        available = credit_limit - current_balance
        if amount > available:
            return False, f"Límite excedido en {acc_name}. Disp: ${available:,.2f}"
            
    # CASO 2: DÉBITO / EFECTIVO
    # Disponible = Saldo Actual
    else:
        if amount > current_balance:
            return False, f"Fondos insuficientes en {acc_name}. Disp: ${current_balance:,.2f}"
            
    return True, "OK"

# backend/data_manager.py

def add_transaction(date, name, amount, category, trans_type, account_id, subcategory=None):
    conn = get_connection()
    cursor = conn.cursor()
    uid = get_uid()
    try:
        # 1. Definir ID para la Base de Datos (Postgres necesita NULL si no es un número)
        db_account_id = None if account_id == 'RESERVE' else account_id

        # 2. VALIDACIÓN DE FONDOS
        # Si es 'RESERVE', validamos contra la tabla de reserva
        if trans_type == 'Expense':
            if account_id == 'RESERVE':
                # Validar saldo en reserva
                current_reserve = get_credit_abono_reserve()
                if amount > current_reserve:
                    return False, f"Fondos insuficientes en Reserva. Disp: ${current_reserve:,.2f}"
            else:
                # Validar saldo en cuenta normal
                has_funds, error_msg = _check_sufficient_funds(cursor, account_id, amount, uid)
                if not has_funds: return False, error_msg

        # 3. INSERTAR LA TRANSACCIÓN (Usamos db_account_id que es None o Número)
        cursor.execute("""
            INSERT INTO transactions (user_id, date, name, amount, category, type, account_id, subcategory) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (uid, date, name, amount, category, trans_type, db_account_id, subcategory))
        
        # 4. ACTUALIZAR SALDO (Aquí usamos el account_id ORIGINAL: 'RESERVE')
        # Esto asegura que entre al IF correcto en _adjust_account_balance
        _adjust_account_balance(cursor, account_id, amount, trans_type, is_reversal=False, user_id=uid)
        
        conn.commit()
        clear_all_caches()
        return True, "Registrado."
    except Exception as e: return False, str(e)
    finally: conn.close()

@cache.memoize(timeout=60)
def get_transactions_df(user_id, start_date=None, end_date=None):
    conn = get_connection()
    uid = user_id
    try:
        # Query base
        sql = """
            SELECT t.*, a.name as account_name 
            FROM transactions t 
            LEFT JOIN accounts a ON t.account_id = a.id
            WHERE t.user_id = %s 
        """
        params = [uid]

        # FILTRO DINÁMICO DE FECHAS (Optimización Clave)
        if start_date and end_date:
            sql += " AND t.date BETWEEN %s AND %s"
            params.extend([start_date, end_date])
        
        sql += " ORDER BY t.date DESC"

        # Nota: Si usas el wrapper que convierte ? a %s, ajusta aquí si es necesario
        df = pd.read_sql_query(sql, conn, params=params)

        if not df.empty:
            df['account_name'] = df['account_name'].fillna('Reserva de Abono')

    except Exception as e:
        print(f"Error get_transactions_df: {e}")
        df = pd.DataFrame()
    finally:
        conn.close()
    return df


def get_net_worth():
    conn = get_connection()
    try:
        # 1. CÁLCULO DE CUENTAS BANCARIAS Y CRÉDITO (EXISTENTE)
        df_accounts = pd.read_sql_query("SELECT type, current_balance FROM accounts", conn)
        
        # Activos Líquidos (Débito/Cash)
        assets_liquid = df_accounts[df_accounts['type'] != 'Credit']['current_balance'].sum()
        # Pasivos Formales (Tarjetas de Crédito)
        liabilities_formal = df_accounts[df_accounts['type'] == 'Credit']['current_balance'].sum()

        # 2. CÁLCULO DE DEUDAS INFORMALES (NUEVO)
        # Solo consideramos las cuentas Pendientes ('Pending')
        df_iou = pd.read_sql_query("SELECT type, current_amount FROM iou WHERE status = 'Pending'", conn)

        assets_informal = 0
        liabilities_informal = 0
        
        if not df_iou.empty:
            # Deudas por Cobrar (Activo)
            assets_informal = df_iou[df_iou['type'] == 'Receivable']['current_amount'].sum()
            # Deudas por Pagar (Pasivo)
            liabilities_informal = df_iou[df_iou['type'] == 'Payable']['current_amount'].sum()

        # 3. PATRIMONIO NETO TOTAL
        # Patrimonio Neto = (Activos Líquidos + Activos Informales) - (Pasivos Formales + Pasivos Informales)
        total_assets = assets_liquid + assets_informal
        total_liabilities = liabilities_formal + liabilities_informal
        
        return total_assets - total_liabilities
        
    except Exception as e:
        print(f"Error al calcular patrimonio neto: {e}")
        return 0
    finally:
        conn.close()

# backend/data_manager.py

# backend/data_manager.py
@cache.memoize(timeout=120)
def get_monthly_summary(user_id):
    """Flujo de caja mensual AGRUPADO POR SQL."""
    conn = get_connection()
    uid = get_uid()
    try:
        # Excluir categorías internas
        excluded = get_excluded_categories_list()
        excl_clause = ""
        if excluded:
            safe_excl = ','.join([f"'{x}'" for x in excluded]) # Simplificado para el ejemplo
            excl_clause = f"AND category NOT IN ({safe_excl})"

        query = f"""
            SELECT 
                TO_CHAR(date::DATE, 'YYYY-MM') as "Month",
                type, 
                SUM(amount) as amount
            FROM transactions
            WHERE user_id = %s {excl_clause}
            GROUP BY 1, 2
            ORDER BY 1 ASC
        """
        return pd.read_sql_query(query, conn, params=(uid,))
    finally:
        conn.close()



@cache.memoize(timeout=120)
def get_category_summary(user_id):
    """Gastos por categoría AGRUPADOS POR SQL."""
    conn = get_connection()
    uid = get_uid()
    try:
        excluded = get_excluded_categories_list()
        excl_clause = ""
        if excluded:
            safe_excl = ','.join([f"'{x}'" for x in excluded])
            excl_clause = f"AND category NOT IN ({safe_excl})"

        query = f"""
            SELECT category, SUM(amount) as amount
            FROM transactions
            WHERE user_id = %s 
              AND type = 'Expense'
              {excl_clause}
            GROUP BY category
            ORDER BY amount DESC
        """
        return pd.read_sql_query(query, conn, params=(uid,))
    finally:
        conn.close()


def add_iou(name, amount, iou_type, due_date, person_name=None, description=None):
    conn = get_connection()
    uid = get_uid()
    try:
        conn.execute("""
            INSERT INTO iou (user_id, name, amount, type, current_amount, date_created, due_date, person_name, description)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (uid, name, amount, iou_type, amount, date.today().strftime('%Y-%m-%d'), due_date, person_name, description))
        conn.commit()
        return True, "Registrado."
    except Exception as e: return False, str(e)
    finally: conn.close()

# backend/data_manager.py

def get_iou_df():
    conn = get_connection()
    uid = get_uid()
    try:
        df = pd.read_sql_query("""
            SELECT * FROM iou 
            WHERE user_id = ? AND status = 'Pending' AND current_amount > 0 
            ORDER BY type ASC, date_created DESC
        """, conn, params=(uid,))
        df['type_display'] = df['type'].apply(lambda x: "Por Cobrar" if x == 'Receivable' else "Por Pagar")
        return df
    finally: conn.close()


def delete_iou(iou_id):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        # Eliminación física, ya que son cuentas informales
        cursor.execute("DELETE FROM iou WHERE id = ?", (iou_id,))
        conn.commit()
        return True, "Elemento eliminado."
    except Exception as e:
        return False, f"Error al eliminar: {str(e)}"
    finally:
        conn.close()

def get_iou_by_id(iou_id):
    """Obtiene los detalles de una cuenta pendiente por su ID."""
    conn = get_connection()
    try:
        df = pd.read_sql_query("SELECT * FROM iou WHERE id = ?", conn, params=(iou_id,))
        if not df.empty:
            return df.iloc[0].to_dict()
        return None
    except:
        return None
    finally:
        conn.close()
# backend/data_manager.py (Función update_iou)

def update_iou(iou_id, name, new_original_amount, iou_type, due_date, person_name, description, new_current_amount, status):
    """Actualiza una cuenta pendiente existente."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        # 🚨 VALIDACIÓN CLAVE: El saldo pendiente no puede exceder el monto original.
        if new_current_amount > new_original_amount + 0.01:
             return False, f"Error: El saldo pendiente (${new_current_amount:,.2f}) no puede ser mayor que el monto original (${new_original_amount:,.2f})."

        # 🚨 ACTUALIZACIÓN: Se permite actualizar el 'amount' (original) y el 'current_amount' (pendiente)
        cursor.execute("""
            UPDATE iou SET 
                name = ?, amount = ?, type = ?, due_date = ?, 
                person_name = ?, description = ?, current_amount = ?, status = ?
            WHERE id = ?
        """, (name, new_original_amount, iou_type, due_date, person_name, description, new_current_amount, status, iou_id))
        conn.commit()
        return True, "Cuenta pendiente actualizada exitosamente."
    except Exception as e:
        return False, f"Error al actualizar: {str(e)}"
    finally:
        conn.close()
# data_manager.py

def get_account_name_summary():
    """Saldo por nombre de cuenta del usuario."""
    conn = get_connection()
    uid = get_uid()
    try:
        # CORRECCIÓN PG: HAVING SUM(...) > 0
        df = pd.read_sql_query("""
            SELECT name, SUM(current_balance) as total_balance
            FROM accounts
            WHERE type IN ('Debit', 'Cash') AND user_id = ?
            GROUP BY name
            HAVING SUM(current_balance) > 0
        """, conn, params=(uid,))
        return df
    finally: conn.close()

# data_manager.py - Colocar junto a add_transaction y get_transactions_df

def get_transaction_by_id(trans_id):
    conn = get_connection()
    uid = get_uid()
    try:
        df = pd.read_sql_query("""
            SELECT * FROM transactions WHERE id = ? AND user_id = ?
        """, conn, params=(trans_id, uid))
        
        if not df.empty: 
            data = df.iloc[0].to_dict()
            
            # --- CORRECCIÓN VITAL ---
            # Si account_id es None, significa que es la cuenta 'RESERVE'
            if data.get('account_id') is None or pd.isna(data.get('account_id')):
                data['account_id'] = 'RESERVE'
                
            return data
        return None
    finally: conn.close()



# backend/data_manager.py

# backend/data_manager.py

def _adjust_account_balance(cursor, account_id, amount, trans_type, is_reversal=False, user_id=None):
    if user_id is None: return 

    # --- CASO ESPECIAL: RESERVA DE ABONO ---
    # Aquí recibimos 'RESERVE' gracias al fix anterior
    if account_id == 'RESERVE':
        print(f"DEBUG: Intentando actualizar RESERVA. Monto: {amount}, Tipo: {trans_type}")
        
        # 1. Verificar si existe la fila
        cursor.execute("SELECT balance FROM abono_reserve WHERE user_id = ?", (user_id,))
        res = cursor.fetchone()
        
        # 2. AUTO-CREACIÓN: Si no existe, la creamos con saldo 0 para poder sumarle
        if not res:
            print("DEBUG: No existía fila de reserva, creando una nueva...")
            cursor.execute("INSERT INTO abono_reserve (user_id, balance) VALUES (?, 0.0)", (user_id,))
            current_balance = 0.0
        else:
            current_balance = res[0]

        # 3. Calcular cambio
        factor = -1 if is_reversal else 1
        # En Reserva: Ingreso SUMA, Gasto RESTA
        change = (amount * factor) if trans_type == 'Income' else (amount * factor * -1)
        
        # 4. Actualizar
        print(f"DEBUG: Aplicando cambio de {change} a la reserva.")
        cursor.execute("UPDATE abono_reserve SET balance = balance + ? WHERE user_id = ?", (change, user_id))
        return

    # --- CASO NORMAL: CUENTAS BANCARIAS Y TARJETAS ---
    # (El resto de la función se queda igual, solo asegúrate de no borrarla)
    cursor.execute("SELECT type, current_balance FROM accounts WHERE id = ? AND user_id = ?", (account_id, user_id))
    res = cursor.fetchone()
    if not res: 
        print(f"DEBUG: Cuenta {account_id} no encontrada.")
        return 
    
    acc_type, current = res
    factor = -1 if is_reversal else 1
    
    change = 0.0

    if acc_type == 'Credit':
        if trans_type == 'Expense':
            change = amount * factor      
        else: 
            change = amount * factor * -1 
    else:
        if trans_type == 'Expense':
            change = amount * factor * -1 
        else:
            change = amount * factor      
        
    cursor.execute("UPDATE accounts SET current_balance = current_balance + ? WHERE id = ? AND user_id = ?", (change, account_id, user_id))
# backend/data_manager.py

def delete_transaction(trans_id):
    conn = get_connection()
    cursor = conn.cursor()
    uid = get_uid()
    try:
        # 1. Obtener los detalles de la transacción ANTES de borrarla
        # (Necesitamos saber el monto y la cuenta para devolver el dinero)
        trans = get_transaction_by_id(trans_id) 
        
        if not trans: 
            return False, "Transacción no encontrada."
        
        # 2. Revertir el saldo (Devolver el dinero a la cuenta)
        # Nota: Pasamos is_reversal=True
        _adjust_account_balance(
            cursor, 
            trans['account_id'], 
            trans['amount'], 
            trans['type'], 
            is_reversal=True, 
            user_id=uid
        )
        
        # 3. Eliminar el registro definitivamente
        cursor.execute("DELETE FROM transactions WHERE id = ? AND user_id = ?", (trans_id, uid))
        
        conn.commit()
        clear_all_caches()
        return True, "Transacción eliminada y saldo corregido."
    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally: conn.close()

# data_manager.py

# ... (Colocar junto a get_credit_summary_data) ...

def get_abono_balance():
    """Obtiene el balance de la cuenta dedicada a abonar pagos de tarjeta."""
    conn = get_connection()
    try:
        # Buscamos una cuenta con un nombre específico (ejemplo: "Abono Tarjeta")
        df = pd.read_sql_query("SELECT current_balance FROM accounts WHERE name = 'Abono Tarjeta' LIMIT 1", conn)
        return df['current_balance'].iloc[0] if not df.empty else 0.0
    except Exception as e:
        print(f"Error getting abono balance: {e}")
        return 0.0
    finally:
        conn.close()

# data_manager.py

# ... (Al final del archivo) ...


def get_credit_abono_reserve():
    """Obtiene la reserva del usuario actual."""
    setup_abono_reserve() # Aseguramos que la tabla esté bien
    conn = get_connection()
    uid = get_uid()
    try:
        cur = conn.cursor()
        # Buscamos POR USER_ID, no por ID fijo
        cur.execute("SELECT balance FROM abono_reserve WHERE user_id = ?", (uid,))
        res = cur.fetchone()
        return res[0] if res else 0.0
    finally: conn.close()



def update_credit_abono_reserve(amount):
    """Actualiza la reserva del usuario actual (INSERT O UPDATE)."""
    setup_abono_reserve()
    conn = get_connection()
    uid = get_uid()
    try:
        cursor = conn.cursor()
        
        # Verificar si ya existe fila para este usuario
        cursor.execute("SELECT id FROM abono_reserve WHERE user_id = ?", (uid,))
        row = cursor.fetchone()
        
        if row:
            # Actualizar
            cursor.execute("UPDATE abono_reserve SET balance = ? WHERE user_id = ?", (amount, uid))
        else:
            # Insertar nuevo
            cursor.execute("INSERT INTO abono_reserve (user_id, balance) VALUES (?, ?)", (uid, amount))
            
        conn.commit()
        return True, "Reserva de abono actualizada."
    except Exception as e:
        return False, str(e)
    finally:
        conn.close()

def update_credit_abono_reserve(amount):
    """Actualiza la reserva del usuario actual (INSERT O UPDATE)."""
    setup_abono_reserve()
    conn = get_connection()
    uid = get_uid()
    try:
        cursor = conn.cursor()
        
        # Verificar si ya existe fila para este usuario
        cursor.execute("SELECT id FROM abono_reserve WHERE user_id = ?", (uid,))
        row = cursor.fetchone()
        
        if row:
            # Actualizar
            cursor.execute("UPDATE abono_reserve SET balance = ? WHERE user_id = ?", (amount, uid))
        else:
            # Insertar nuevo
            cursor.execute("INSERT INTO abono_reserve (user_id, balance) VALUES (?, ?)", (uid, amount))
            
        conn.commit()
        return True, "Reserva de abono actualizada."
    except Exception as e:
        return False, str(e)
    finally:
        conn.close()



def setup_abono_reserve():
    conn = get_connection()
    cursor = conn.cursor()
    
    id_type = "SERIAL PRIMARY KEY" if IS_POSTGRES else "INTEGER PRIMARY KEY AUTOINCREMENT"
    
    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS abono_reserve (
            id {id_type},
            user_id INTEGER,
            balance REAL DEFAULT 0.0
        )
    """)
    
    if not check_column_exists(cursor, 'abono_reserve', 'user_id'):
        print("⚠️ Migrando tabla abono_reserve: Agregando user_id...")
        cursor.execute("ALTER TABLE abono_reserve ADD COLUMN user_id INTEGER")
        cursor.execute("UPDATE abono_reserve SET user_id = 1 WHERE id = 1")
    
    conn.commit()
    conn.close()

# ... (Al final del archivo, junto a las funciones de resumen de crédito) ...
# backend/data_manager.py

def get_informal_summary():
    """
    Calcula el total de deudas informales (Payable) y cobros informales (Receivable) 
    a partir de la tabla 'iou' con estado 'Pending' Y saldo positivo.
    Retorna: (total_debt_i, total_collectible_i) ambos como valores absolutos.
    """
    conn = get_connection()
    try:
        # 🚨 CORRECCIÓN CRÍTICA: Añadir 'AND current_amount > 0' para coincidir con la tabla
        df_iou = pd.read_sql_query("""
            SELECT type, current_amount 
            FROM iou 
            WHERE status = 'Pending' AND current_amount > 0
        """, conn)

        if df_iou.empty:
            return 0.0, 0.0
            
        # Deudas por Pagar (Pasivo)
        payables = df_iou[df_iou['type'] == 'Payable']['current_amount'].sum()
        # Deudas por Cobrar (Activo)
        receivables = df_iou[df_iou['type'] == 'Receivable']['current_amount'].sum()

        # Retornamos los valores absolutos
        return abs(payables), abs(receivables)
        
    except Exception as e:
        print(f"Error getting informal summary: {e}")
        return 0.0, 0.0
    finally:
        conn.close()

def get_full_debt_summary():
    """Resumen consolidado de deuda del usuario."""
    uid = get_uid()
    # Reutilizamos las funciones que ya filtran
    df_iou = get_iou_df()
    
    payables = df_iou[df_iou['type'] == 'Payable']['current_amount'].sum()
    receivables = df_iou[df_iou['type'] == 'Receivable']['current_amount'].sum()
    
    # Exigible TC
    cred_sum = get_credit_summary_data()
    reserve = get_credit_abono_reserve()
    
    exigible_gross = cred_sum['total_debt'] - cred_sum['total_installments']
    credit_exigible_net = max(0, exigible_gross - reserve)
    
    total_gross_debt = payables + credit_exigible_net
    net_exposure = total_gross_debt - receivables
    informal_net_balance = receivables - payables

    return {
        'informal_debt': abs(payables),
        'informal_collectible': abs(receivables),
        'credit_exigible_net': credit_exigible_net,
        'total_gross_debt': total_gross_debt,
        'net_exposure': net_exposure,
        'informal_net_balance': informal_net_balance
    }
def get_net_exigible_credit_debt():
    """Calcula el monto exigible neto (sin cuotas y restando la reserva de abono)."""
    # Se asume que get_credit_summary_data() y get_credit_abono_reserve() ya existen
    summary = get_credit_summary_data() 
    abono_reserve = get_credit_abono_reserve()
    
    debt = summary['total_debt']
    inst_debt = summary['total_installments']
    
    # Exigible Bruto
    exigible_debt_gross = debt - inst_debt
    if exigible_debt_gross < 0: exigible_debt_gross = 0
    
    # Exigible NETO (Restando la reserva de abono)
    exigible_debt_net = exigible_debt_gross - abono_reserve
    if exigible_debt_net < 0: exigible_debt_net = 0 
    
    return exigible_debt_net

# backend/data_manager.py

# ... (Al final del archivo) ...

# backend/data_manager.py

# backend/data_manager.py
# backend/data_manager.py

from datetime import datetime, timedelta # Asegúrate de tener estos imports

# ... (otras funciones) ...

# --- 1. GESTIÓN DE TABLA CACHÉ (Versión Blindada) ---
def create_market_cache_table():
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("PRAGMA table_info(market_cache)")
    columns = [info[1] for info in cursor.fetchall()]
    
    # AGREGAR 'company_name' a la validación para recrear la tabla si falta
    if columns and 'company_name' not in columns:
        print("⚠️ Actualizando estructura de tabla market_cache (Adding company_name)...")
        cursor.execute("DROP TABLE market_cache")
        columns = [] 

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS market_cache (
        ticker TEXT PRIMARY KEY,
        company_name TEXT,  -- <--- NUEVA COLUMNA
        price REAL, day_change REAL, day_change_pct REAL,
        day_high REAL, day_low REAL, fiftyTwo_high REAL, fiftyTwo_low REAL,
        market_cap REAL, 
        shares_outstanding REAL, 
        pe_ratio REAL, 
        peg_ratio REAL, 
        dividend_yield REAL, 
        beta REAL,
        sector TEXT, country TEXT, summary TEXT,
        news TEXT, sentiment TEXT,
        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    conn.commit()
    conn.close()
# backend/data_manage
# backend/data_manager.py
# backend/data_manager.py

# ... (debajo de KNOWN_ETFS y detect_asset_type) ...

def clean_ticker_display(raw_ticker):
    """
    Convierte 'BINANCE:BTCUSDT' en 'BTC' y 'COINBASE:ETH-USD' en 'ETH'.
    También limpia tickers de acciones si es necesario.
    """
    if not raw_ticker: return ""
    
    clean = str(raw_ticker).upper()
    
    # 1. Quitar Prefijo del Exchange (BINANCE:, COINBASE:, etc)
    if ":" in clean:
        clean = clean.split(":")[1]
        
    # 2. Limpiar Sufijos de Cripto/Forex para dejar solo el símbolo base
    # Orden importa: USDT primero para que no quede la T
    suffixes = ["USDT", "-USD", "USD", "BUSD", "USDC"]
    
    for s in suffixes:
        if clean.endswith(s) and len(clean) > len(s): # Asegurar que no borremos el ticker si es solo "USD"
            clean = clean.replace(s, "")
            break
            
    return clean

@cache.memoize(timeout=300)
def get_stocks_data(user_id, force_refresh=False):
    """
    Obtiene el portafolio del usuario actual combinando:
    1. Datos privados (investments: shares, avg_price) -> Filtrado por user_id
    2. Datos globales (market_cache: price, news) -> Sin filtrar (compartido)
    """
    conn = get_connection()
    uid = user_id # ID del usuario actual
    
    try:
        # 1. Obtener los tickers que posee ESTE usuario
        df_investments = pd.read_sql_query("SELECT ticker FROM investments WHERE user_id = ?", conn, params=(uid,))
        
        if df_investments.empty:
            return []

        my_tickers = df_investments['ticker'].unique().tolist()
        
        # 2. Lógica de Actualización de Caché (GLOBAL)
        # Verificamos si tenemos datos en market_cache, independientemente de quién los pidió antes
        tickers_to_fetch = []
        
        if force_refresh:
            tickers_to_fetch = my_tickers
        else:
            # Consultamos qué tickers ya tienen datos válidos (usamos 'beta' como testigo)
            if my_tickers:
                placeholders = ','.join(['?'] * len(my_tickers))
                query_check = f"SELECT ticker, beta FROM market_cache WHERE ticker IN ({placeholders})"
                try:
                    cached = pd.read_sql_query(query_check, conn, params=my_tickers)
                    # Si beta es nulo, asumimos que falta info financiera y recargamos
                    valid_cached = cached[cached['beta'].notnull()]['ticker'].tolist()
                    tickers_to_fetch = [t for t in my_tickers if t not in valid_cached]
                except:
                    tickers_to_fetch = my_tickers

        # 3. Consultar API Finnhub (Solo para lo que falta o si se forzó)
        if tickers_to_fetch and finnhub_client:
            print(f"🔄 Finnhub Updating: {tickers_to_fetch}")
            cursor = conn.cursor()
            
            for t in tickers_to_fetch:
                try:
                    # A. Precio en vivo
                    q = finnhub_client.quote(t)
                    if q['c'] == 0: continue 
                    
                    # B. Perfil de empresa
                    try: p = finnhub_client.company_profile2(symbol=t)
                    except: p = {}
                    real_name = p.get('name', t)
                    
                    # C. Métricas financieras
                    try: 
                        metrics_res = finnhub_client.company_basic_financials(t, 'all')
                        m = metrics_res.get('metric', {})
                    except: m = {}

                    # D. Noticias
                    try: 
                        _today = datetime.now().strftime('%Y-%m-%d')
                        news = finnhub_client.company_news(t, _from=_today, to=_today)[:3]
                    except: news = []

                    # INSERT OR REPLACE en la tabla GLOBAL (market_cache)
                    # No usamos user_id aquí porque el precio de Apple es igual para todos
                    cursor.execute("""
                    INSERT OR REPLACE INTO market_cache (
                        ticker, company_name, price, day_change, day_change_pct, day_high, day_low, 
                        fiftyTwo_high, fiftyTwo_low, 
                        market_cap, pe_ratio, dividend_yield, beta,
                        sector, country, summary, news, sentiment, last_updated
                    ) 
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?, datetime('now','localtime'))
                    """, (
                        t, real_name,
                        q.get('c', 0), q.get('d', 0), q.get('dp', 0), q.get('h', 0), q.get('l', 0),
                        m.get('52WeekHigh', 0), m.get('52WeekLow', 0), 
                        p.get('marketCapitalization', 0), 
                        m.get('pfcfShareTTM', 0) if m.get('peBasicExclExtraTTM') is None else m.get('peBasicExclExtraTTM', 0),
                        m.get('dividendYieldIndicatedAnnual', 0), m.get('beta', 0),
                        p.get('finnhubIndustry', 'N/A'), p.get('country', 'N/A'), p.get('currency', 'USD'), 
                        json.dumps(news), json.dumps({})
                    ))
                    conn.commit()
                    time.sleep(0.2) # Pequeña pausa para no saturar API
                except Exception as e: 
                    print(f"❌ Error API {t}: {e}")

        # 4. LEER DATOS COMBINADOS (User + Global)
        # Unimos las inversiones DEL USUARIO con el caché GLOBAL
        query = """
        SELECT i.*, 
               c.company_name, 
               c.price as current_price, c.day_change, c.day_change_pct, c.sector, 
               c.market_cap, c.day_high, c.day_low, c.news,
               c.fiftytwo_high as "fiftyTwo_high", c.fiftytwo_low as "fiftyTwo_low",
               c.pe_ratio, c.dividend_yield, c.beta, c.country
        FROM investments i 
        LEFT JOIN market_cache c ON i.ticker = c.ticker
        WHERE i.user_id = ?
        """
        df = pd.read_sql_query(query, conn, params=(uid,))
        
        results = []
        for _, row in df.iterrows():
            # Cálculos de valor
            curr = row['current_price'] if pd.notnull(row['current_price']) and row['current_price'] > 0 else row['avg_price']
            mkt_val = row['shares'] * curr
            gain = mkt_val - (row['shares'] * row['avg_price'])
            
            # Limpieza de textos
            ticker_clean = clean_ticker_display(row['ticker'])
            real_name_db = row['company_name'] if pd.notnull(row['company_name']) else ticker_clean
            
            try: news_data = json.loads(row['news']) if row['news'] else []
            except: news_data = []

            results.append({
                'id': row['id'],
                'ticker': row['ticker'],            # Raw: BINANCE:BTCUSDT
                'display_ticker': ticker_clean,     # Clean: BTC
                'real_name': real_name_db,          # Name: Bitcoin
                'name': real_name_db,
                'asset_type': row['asset_type'],
                'shares': row['shares'],
                'avg_price': row['avg_price'],
                'current_price': curr,
                'market_value': mkt_val,
                'total_gain': gain,
                'total_gain_pct': (gain / (row['shares']*row['avg_price']) * 100) if row['avg_price'] > 0 else 0,
                
                # Datos de Mercado (Globales)
                'day_change': row['day_change'] or 0, 
                'day_change_pct': row['day_change_pct'] or 0,
                'day_high': row['day_high'] or 0, 'day_low': row['day_low'] or 0,
                'fiftyTwo_high': row['fiftyTwo_high'] or 0, 'fiftyTwo_low': row['fiftyTwo_low'] or 0,
                'pe_ratio': row['pe_ratio'] or 0, 
                'market_cap': row['market_cap'] or 0,
                'dividend_yield': row['dividend_yield'] or 0, 
                'beta': row['beta'] or 0, 
                'sector': row['sector'] or 'N/A', 
                'country': row['country'] or 'N/A', 
                'summary': '', 
                'news': news_data, 
                'sentiment': {}
            })
            
        return results
        
    except Exception as e:
        print(f"Error en get_stocks_data: {e}")
        return []
    finally:
        conn.close()


def get_data_timestamp():
    """Devuelve la fecha más reciente convertida a la hora local del sistema."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        
        # VERIFICACIÓN COMPATIBLE DE EXISTENCIA DE TABLA
        table_exists = False
        if IS_POSTGRES:
            cursor.execute("SELECT to_regclass('market_cache')")
            table_exists = cursor.fetchone()[0] is not None
        else:
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='market_cache'")
            table_exists = cursor.fetchone() is not None

        if not table_exists: 
            return "Nunca"

        cursor.execute("SELECT MAX(last_updated) FROM market_cache")
        res = cursor.fetchone()
        
        if res and res[0]:
            try:
                # 1. Obtener string limpio (sin microsegundos)
                raw_ts = str(res[0]).split('.')[0]
                
                # 2. Convertir a objeto Datetime
                dt_obj = datetime.strptime(raw_ts, '%Y-%m-%d %H:%M:%S')
                
                # 3. Asignar origen UTC (La base de datos guarda en UTC)
                dt_utc = dt_obj.replace(tzinfo=timezone.utc)
                
                # 4. CONVERTIR A HORA LOCAL DEL SISTEMA
                # .astimezone(None) usa la configuración de tu computadora
                dt_local = dt_utc.astimezone(None)
                
                return dt_local.strftime('%d/%m %H:%M')
            except Exception as e:
                # Fallback por si falla la conversión
                print(f"Error timezone: {e}")
                return str(res[0])
        return "Sin datos"
    except Exception as e:
        return "Error"
    finally:
        conn.close()

@cache.memoize(timeout=60)
def get_net_worth_breakdown(user_id, force_refresh=False):
    conn = get_connection()
    uid = user_id
    details = {'net_worth': 0.0, 'assets': {'total': 0.0}, 'liabilities': {'total': 0.0}}
    try:
        # Cuentas
        df_acc = pd.read_sql_query("SELECT type, current_balance FROM accounts WHERE user_id = ?", conn, params=(uid,))
        liquid = df_acc[df_acc['type'].isin(['Debit', 'Cash'])]['current_balance'].sum()
        credit = df_acc[df_acc['type'] == 'Credit']['current_balance'].sum()
        
        # Reserva
        res = get_credit_abono_reserve()
        
        # IOU
        df_iou = pd.read_sql_query("SELECT type, current_amount FROM iou WHERE user_id = ? AND status='Pending'", conn, params=(uid,))
        iou_rec = df_iou[df_iou['type'] == 'Receivable']['current_amount'].sum() if not df_iou.empty else 0
        iou_pay = df_iou[df_iou['type'] == 'Payable']['current_amount'].sum() if not df_iou.empty else 0
        
        # Inversiones
        stocks = get_stocks_data(uid, force_refresh)
        inv_val = sum(s['market_value'] for s in stocks)
        
        assets = liquid + res + iou_rec + inv_val
        liabs = credit + iou_pay
        
        details['net_worth'] = assets - liabs
        details['assets'] = {'total': assets, 'liquid': liquid + res, 'receivables': iou_rec, 'investments': inv_val}
        details['liabilities'] = {'total': liabs, 'credit_cards': credit, 'payables': iou_pay}
    finally: conn.close()
    return details




# data_manager.py

# --- SUBCATEGORÍAS ---
def add_custom_subcategory(name, parent):
    conn = get_connection()
    uid = get_uid()
    try:
        conn.execute("INSERT INTO subcategories (user_id, name, parent_category) VALUES (?, ?, ?)", (uid, name, parent))
        conn.commit()
        return True, "Creada."
    except: return False, "Error."
    finally: conn.close()



def get_subcategories_by_parent(parent):
    conn = get_connection()
    uid = get_uid()
    try:
        df = pd.read_sql_query("SELECT name FROM subcategories WHERE user_id = ? AND parent_category = ?", conn, params=(uid, parent))
        return [{'label': r['name'], 'value': r['name']} for _, r in df.iterrows()]
    except: return []
    finally: conn.close()

# --- MODIFICAR ESTAS FUNCIONES EXISTENTES PARA INCLUIR 'subcategory' --

def update_transaction(trans_id, new_date, new_name, new_amount, new_category, new_type, new_account_id, new_subcategory=None):
    conn = get_connection()
    cursor = conn.cursor()
    uid = get_uid()
    try:
        # Verificar propiedad y obtener datos viejos
        old_trans = get_transaction_by_id(trans_id)
        if not old_trans: return False, "No encontrado."

        # IMPORTANTE: get_transaction_by_id ya debe devolver 'RESERVE' si es None (ver punto 3)
        old_acc_id = old_trans['account_id'] 

        # 1. Reversar saldo anterior (usando el ID lógico, ej: 'RESERVE')
        _adjust_account_balance(cursor, old_acc_id, old_trans['amount'], old_trans['type'], is_reversal=True, user_id=uid)
        
        # 2. Definir ID para SQL (Null si es Reserve)
        db_new_account_id = None if new_account_id == 'RESERVE' else new_account_id

        # 3. Update SQL
        cursor.execute("""
            UPDATE transactions 
            SET date = ?, name = ?, amount = ?, category = ?, type = ?, account_id = ?, subcategory = ?
            WHERE id = ? AND user_id = ?
        """, (new_date, new_name, new_amount, new_category, new_type, db_new_account_id, new_subcategory, trans_id, uid))

        # 4. Aplicar nuevo saldo (Usando ID lógico new_account_id)
        _adjust_account_balance(cursor, new_account_id, new_amount, new_type, is_reversal=False, user_id=uid)
        
        conn.commit()
        clear_all_caches()
        return True, "Actualizado."
    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally: conn.close()

# data_manager.py (Añadir estas funciones)

def get_all_categories_options():
    conn = get_connection()
    uid = get_uid()
    try:
        df = pd.read_sql_query("SELECT name FROM categories WHERE user_id = ? ORDER BY name ASC", conn, params=(uid,))
        return [{'label': r['name'], 'value': r['name']} for _, r in df.iterrows()]
    except: return []
    finally: conn.close()



def add_custom_category(name):
    conn = get_connection()
    uid = get_uid()
    try:
        conn.execute("INSERT INTO categories (user_id, name) VALUES (?, ?)", (uid, name))
        conn.commit()
        return True, "Creada."
    except: return False, "Error."
    finally: conn.close()
# backend/data_manager.p

# --- FUNCIONES DE PERFIL Y SEGURIDAD ---

# --- EN backend/data_manager.py ---

def update_user_profile_data(old_password_input, new_name, new_email, new_password=None):
    """
    Actualiza perfil verificando primero la contraseña antigua.
    Permite cambiar Nombre, Email y (opcionalmente) Contraseña.
    """
    conn = get_connection()
    uid = get_uid()
    try:
        cursor = conn.cursor()
        
        # 1. SEGURIDAD: Obtener el hash actual de la base de datos
        cursor.execute("SELECT password_hash FROM users WHERE id = ?", (uid,))
        res = cursor.fetchone()
        
        if not res:
            return False, "Usuario no encontrado."
            
        current_db_hash = res[0]
        
        # 2. VERIFICAR: La contraseña antigua debe coincidir
        if not check_password_hash(current_db_hash, old_password_input):
            return False, "La contraseña actual es incorrecta."
        
        # 3. ACTUALIZAR DATOS BÁSICOS (Nombre y Email)
        # Verificamos si el email cambió para no causar conflicto si ya existe otro igual
        if new_email:
            # Opcional: Verificar si el email ya lo usa otro usuario (si tu DB tiene unique constraint)
            cursor.execute("SELECT id FROM users WHERE email = ? AND id != ?", (new_email, uid))
            if cursor.fetchone():
                return False, "Ese correo electrónico ya está en uso."
        
        cursor.execute("""
            UPDATE users 
            SET display_name = ?, email = ? 
            WHERE id = ?
        """, (new_name, new_email, uid))
            
        # 4. ACTUALIZAR CONTRASEÑA (Solo si se escribió una nueva)
        if new_password:
            new_hashed_pw = generate_password_hash(new_password, method='pbkdf2:sha256')
            cursor.execute("UPDATE users SET password_hash = ? WHERE id = ?", (new_hashed_pw, uid))
            
        conn.commit()
        return True, "Perfil actualizado correctamente."
        
    except Exception as e:
        return False, f"Error: {str(e)}"
    finally:
        conn.close()

def import_historical_data(df):
    """Recibe un DataFrame con columnas 'Date' y 'Net_Worth' y lo guarda."""
    conn = get_connection()
    uid = get_uid()
    try:
        cursor = conn.cursor()
        
        # Limpiamos datos previos importados para evitar duplicados masivos 
        # (Opcional: podrías decidir no borrar si quieres cargas incrementales)
        cursor.execute("DELETE FROM historical_net_worth WHERE user_id = ?", (uid,))
        
        count = 0
        for _, row in df.iterrows():
            # Asumimos formato YYYY-MM-DD
            d_val = pd.to_datetime(row['Date']).strftime('%Y-%m-%d')
            nw_val = float(row['Net_Worth'])
            
            cursor.execute("INSERT INTO historical_net_worth (user_id, date, net_worth) VALUES (?, ?, ?)", 
                           (uid, d_val, nw_val))
            count += 1
            
        conn.commit()
        return True, f"Se importaron {count} registros históricos."
    except Exception as e:
        return False, f"Error DB: {str(e)}"
    finally:
        conn.close()

# backend/data_manager.py

# --- OPTIMIZACIÓN HISTORIAL PATRIMONIO ---

@cache.memoize(timeout=300)
def _get_full_networth_history_cached(user_id):
    conn = get_connection()
    try:
        # 1. Obtener Histórico CONGELADO...
        df_db = pd.read_sql_query(
            "SELECT date, net_worth FROM historical_net_worth WHERE user_id = ? ORDER BY date ASC", 
            conn, params=(user_id,)
        )
        
        if not df_db.empty:
            df_db['date'] = pd.to_datetime(df_db['date']).dt.date

        # 2. Calcular el Valor EN VIVO de Hoy
        # --- CORRECCIÓN AQUÍ: Pasar user_id ---
        nw_data = get_net_worth_breakdown(user_id, force_refresh=False) 
        current_val = nw_data['net_worth']
        today_date = date.today()

        # 3. Integrar "Hoy" al DataFrame
        # Si ya existe un registro de hoy en DB (porque se guardó snapshot hace rato),
        # lo sobrescribimos con el valor en vivo para el gráfico.
        row_today = pd.DataFrame([{'date': today_date, 'net_worth': current_val}])
        
        if df_db.empty:
            df_final = row_today
        else:
            # Eliminar si ya existe hoy para poner la versión más fresca
            df_db = df_db[df_db['date'] < today_date]
            df_final = pd.concat([df_db, row_today], ignore_index=True)

        # 4. RELLENO DE HUECOS (Forward Fill) - LA PARTE CLAVE
        # Creamos un índice con TODOS los días desde el inicio hasta hoy
        min_date = df_final['date'].min()
        idx = pd.date_range(min_date, today_date)
        
        # Indexamos por fecha
        df_final = df_final.set_index('date')
        
        # Reindexamos para crear las filas vacías de los días que no entraste
        df_final = df_final.reindex(idx.date)
        
        # ffill(): Copia el valor anterior hacia adelante en los huecos
        df_final['net_worth'] = df_final['net_worth'].ffill()
        
        # Reset index para devolver formato normal
        df_final = df_final.reset_index().rename(columns={'index': 'date'})
        
        # Calcular variación diaria (net_change) sobre la serie ya rellena
        df_final['net_change'] = df_final['net_worth'].diff().fillna(0)
        
        return df_final

    except Exception as e:
        print(f"Error calculando historial ffill: {e}")
        return pd.DataFrame()
    finally:
        conn.close()

    

# --- EN backend/data_manager.py ---

# --- EN backend/data_manager.py ---

def capture_daily_snapshot():
    conn = get_connection()
    try:
        # 1. Obtener UID PRIMERO
        uid = get_uid()
        if not uid: return # Seguridad

        # 2. Obtener el valor real de HOY (Pasando el UID)
        data = get_net_worth_breakdown(uid, force_refresh=False) # <--- CORRECCIÓN
        current_nw = data['net_worth']
        
        date_str = date.today().strftime('%Y-%m-%d')
        
        cursor = conn.cursor()
        
        # 2. Verificar si ya existe registro de hoy
        cursor.execute("SELECT id FROM historical_net_worth WHERE user_id = ? AND date = ?", (uid, date_str))
        row = cursor.fetchone()
        
        if row:
            # ACTUALIZAR: El día no ha acabado, seguimos ajustando el valor de hoy
            cursor.execute("UPDATE historical_net_worth SET net_worth = ? WHERE id = ?", (current_nw, row[0]))
        else:
            # INSERTAR: Primer movimiento del día
            cursor.execute("INSERT INTO historical_net_worth (user_id, date, net_worth) VALUES (?, ?, ?)", (uid, date_str, current_nw))
            
        conn.commit()
        
        # 3. Importante: Limpiar caché del historial para que el gráfico se actualice
        # Usamos delete_memoized directamente sobre la función interna
        try:
            cache.delete_memoized(_get_full_networth_history_cached)
        except:
            pass
            
    except Exception as e:
        print(f"⚠️ Error en auto-snapshot: {e}")
    finally:
        conn.close()


# --- EN backend/data_manager.py ---

def get_historical_networth_trend(start_date=None, end_date=None):
    """
    Función LIGERA: Solo filtra el DataFrame que ya está en memoria.
    CORREGIDA: Maneja correctamente la comparación entre Timestamp y datetime.date.
    """
    uid = get_uid()
    
    # 1. Llamada instantánea al Caché
    df = _get_full_networth_history_cached(uid)
    
    if df.empty: return df
    
    # 2. Filtrado Rápido en Memoria
    # El DataFrame 'df' viene con la columna 'date' como objetos datetime.date (por la lógica del ffill)
    # Por lo tanto, debemos convertir start_date y end_date a .date() antes de comparar.
    
    if start_date:
        # pd.to_datetime convierte string a Timestamp, y .date() lo pasa al formato compatible
        s_date = pd.to_datetime(start_date).date()
        df = df[df['date'] >= s_date]
    
    if end_date:
        e_date = pd.to_datetime(end_date).date()
        df = df[df['date'] <= e_date]
        
    return df

def _get_price_finnhub(ticker_symbol, avg_price_fallback=0):
    """
    Obtiene precio actual, cierre anterior, nombre y sector usando Finnhub.
    Retorna: (current_price, prev_close, company_name, sector)
    """
    if not finnhub_client:
        return avg_price_fallback, avg_price_fallback, ticker_symbol, 'N/A'

    clean_ticker = str(ticker_symbol).strip().upper()
    
    try:
        quote = finnhub_client.quote(clean_ticker)
        
        current_price = float(quote['c'])
        prev_close = float(quote['pc'])
        
        if current_price == 0:
            return avg_price_fallback, avg_price_fallback, clean_ticker, 'N/A'
            
        name = clean_ticker
        sector = 'N/A'
        try:
            profile = finnhub_client.company_profile2(symbol=clean_ticker)
            if profile:
                if 'name' in profile:
                    name = profile['name']
                if 'finnhubIndustry' in profile:
                    sector = profile['finnhubIndustry']
        except: pass

        return current_price, prev_close, name, sector # <-- MODIFICADO RETURN

    except Exception as e:
        print(f"Error Finnhub para {clean_ticker}: {e}")
        return avg_price_fallback, avg_price_fallback, clean_ticker, 'N/A'



# backend/data_manager.py (NUEVA FUNCIÓN)

def get_asset_type_breakdown(stocks_list):
    """Returns data for a pie chart broken down by the primary asset type (Stock, ETF, Crypto, Other)."""
    stocks = stocks_list
    
    if not stocks:
        return pd.DataFrame()
    
    df = pd.DataFrame(stocks)
    
    # Mapeamos el 'asset_type' final a un nombre legible para el gráfico
    df['Display_Type'] = df['asset_type'].apply(lambda x: 
        'Fondos (ETF)' if x == 'ETF' else (
        'Cripto/Forex' if x == 'CRYPTO_FOREX' else (
        'Acciones (Stocks)' if x == 'Stock' else 'Otros Activos'))
    )

    df_asset_type = df.groupby('Display_Type')['market_value'].sum().reset_index().rename(columns={'Display_Type': 'name', 'market_value': 'value'})
    
    return df_asset_type
# backend/data_manager.py (MODIFICADO para aceptar la lista de stocks)

# backend/data_manager.py (MODIFICADO para garantizar el retorno de todas las claves)

# backend/data_manager.py (MODIFICADO para garantizar el retorno de todas las claves)

def get_portfolio_summary_data(stocks_list): 
    """Calculates overall portfolio metrics: total value, day change, total gain."""
    stocks = stocks_list
    
    # Base dictionary guaranteed to be returned, initialized to 0.0
    result = {
        'market_value': 0.0, 'day_gain_usd': 0.0, 
        'day_pct': 0.0,         # <-- Usar la clave corta
        'total_gain_usd': 0.0, 
        'total_pct': 0.0
    }
    
    if not stocks:
        return result
        
    total_market_value = 0.0
    total_day_gain = 0.0
    total_total_gain = 0.0
    total_total_cost = 0.0
    
    try:
        for s in stocks:
            total_market_value += s['market_value']
            total_total_gain += s['total_gain']
            total_total_cost += s['avg_price'] * s['shares']
            
            day_change_pct = s['day_change_pct']
            
            # Calculate Day Gain in USD
            if (1 + day_change_pct/100) != 0:
                prev_val = s['market_value'] / (1 + day_change_pct/100)
                day_gain_usd = s['market_value'] - prev_val
                total_day_gain += day_gain_usd
        
        # Calculate Total Percentage Metrics
        prev_close_value = total_market_value - total_day_gain
        day_gain_pct = (total_day_gain / prev_close_value * 100) if prev_close_value != 0 else 0
        total_gain_pct = (total_total_gain / total_total_cost * 100) if total_total_cost != 0 else 0

        # Assign results back to the dictionary
        result['market_value'] = total_market_value
        result['day_gain_usd'] = total_day_gain
        result['day_pct'] = day_gain_pct     # <-- Asignar al nombre corto
        result['total_gain_usd'] = total_total_gain
        result['total_pct'] = total_gain_pct
        
    except Exception as e:
        # If any error occurs during processing (e.g., data type error), 
        # log it and return the default zeroed dictionary.
        print(f"Error processing portfolio summary data: {e}")
        
    return result



def get_portfolio_breakdown(stocks_list): # <-- ACEPTA LA LISTA DE CACHÉ
    """Returns data for pie charts: per stock and per industry."""
    stocks = stocks_list # Usa la lista pasada por el Store/Cache
    
    if not stocks:
        return pd.DataFrame(), pd.DataFrame() # Empty DFs
    
    df = pd.DataFrame(stocks)
    
    # 1. Breakdown by Stock
    df_stock = df[['ticker', 'market_value']].rename(columns={'ticker': 'name', 'market_value': 'value'})
    
    # 2. Breakdown by Industry (Sector)
    # Rellenamos 'N/A' si el sector no se pudo obtener, para que no falle el groupby
    df['sector'] = df['sector'].fillna('Sin Sector') 
    df_industry = df.groupby('sector')['market_value'].sum().reset_index().rename(columns={'sector': 'name', 'market_value': 'value'})
    
    return df_stock, df_industry


# La función debe aceptar total_investment como argumento
# backend/data_manager.py

def add_stock(ticker, shares, total_investment, asset_type="Stock", account_id=None):
    conn = get_connection()
    cursor = conn.cursor()
    uid = get_uid()  # 1. Obtenemos el ID
    
    # --- AUTO-DETECTAR TIPO AL GUARDAR ---
    detected = detect_asset_type(ticker)
    if detected != "Stock":
        asset_type = detected
    # -------------------------------------
        
    avg_price = total_investment / shares if shares > 0 else 0.0
    
    try:
        # Calcular orden solo para este usuario
        cursor.execute("SELECT MAX(display_order) FROM investments WHERE user_id = ?", (uid,))
        res = cursor.fetchone()
        new_order = (res[0] if res[0] is not None else 0) + 1

        # 2. CORRECCIÓN AQUÍ: Agregamos user_id al INSERT y a los VALUES
        cursor.execute("""
            INSERT INTO investments (user_id, ticker, shares, avg_price, total_investment, asset_type, account_id, display_order)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (uid, ticker.upper(), shares, avg_price, total_investment, asset_type, account_id, new_order))
        
        conn.commit()
        clear_all_caches()
        return True, f"Agregado: {clean_ticker_display(ticker)} ({asset_type})"
    except Exception as e:
        return False, str(e)
    finally:
        conn.close()

# Ejecutar una vez para limpiar basura de pruebas anteriores

def get_investment_detail(asset_id):
    # Reutilizamos get_stocks_data porque ya hace todo el trabajo sucio
    all_data = get_stocks_data(force_refresh=False)
    for asset in all_data:
        if asset['id'] == asset_id:
            # 🚨 ELIMINAR O COMENTAR ESTAS LÍNEAS QUE CAUSABAN EL ERROR 🚨
            # asset['name'] = clean_ticker_display(asset['ticker']) 
            # asset['ticker'] = clean_ticker_display(asset['ticker']) 
            
            # get_stocks_data YA devuelve 'display_ticker' (limpio) y 'ticker' (real).
            # Devolvemos el objeto intacto para tener ambos datos.
            return asset
    return None
def update_investment(inv_id, new_shares, new_total_investment):
    """Actualiza las shares y el total_investment, recalculando el avg_price."""
    conn = get_connection()
    cursor = conn.cursor()
    
    # 1. CÁLCULO CRÍTICO: El nuevo costo promedio se calcula directamente con la nueva inversión total
    new_avg_price = new_total_investment / new_shares if new_shares > 0 else 0.0
    
    try:
        # 2. Actualizar la DB con los 3 valores proporcionados por el usuario/cálculo
        cursor.execute("""
            UPDATE investments 
            SET shares = ?, total_investment = ?, avg_price = ?
            WHERE id = ?
        """, (new_shares, new_total_investment, new_avg_price, inv_id))
        
        conn.commit()
        clear_all_caches()
        # 🚨 MENSAJE CORREGIDO: Devolver el nuevo costo promedio para confirmar el cambio.
        return True, f"Posición actualizada. Nuevo Costo Promedio: ${new_avg_price:,.2f}"
    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally:
        conn.close()

# ... (Mantener funciones delete_investment, change_investment_order) ...
def delete_investment(inv_id):
    conn = get_connection()
    uid = get_uid()
    try:
        conn.execute("DELETE FROM investments WHERE id = ? AND user_id = ?", (inv_id, uid))
        conn.commit()
        return True, "Eliminado."
    except Exception as e: return False, str(e)
    finally: conn.close()


def get_stock_historical_data(ticker, time_period='1Y'):
    """
    Obtiene datos históricos (cierre ajustado) para un ticker y periodo.
    time_period: '1D', '1W', '1M', '3M', 'YTD', '1Y', '5Y'
    """
    if not finnhub_client:
        return pd.DataFrame()

    clean_ticker = str(ticker).strip().upper()
    today = int(time.time())

    # 1. Determinar intervalo y resolución (res)
    if time_period in ['1D', '1W']:
        # Resolución en minutos para periodos cortos
        res = '5' if time_period == '1D' else '30' 
        
        if time_period == '1D':
            # Simular 1 día hábil (asumimos 8 horas = 480 minutos)
            # En realidad, Finnhub usa la hora UNIX. Vamos 24 horas atrás
            start_time = today - (24 * 3600)
        else: # 1W
            start_time = today - (7 * 24 * 3600)
            
    else:
        res = 'D' # Diario para periodos largos
        # 2. Determinar tiempo de inicio (from)
        if time_period == '1M':
            start_time = today - (30 * 24 * 3600)
        elif time_period == '3M':
            start_time = today - (90 * 24 * 3600)
        elif time_period == '1Y':
            start_time = today - (365 * 24 * 3600)
        elif time_period == '5Y':
            start_time = today - (5 * 365 * 24 * 3600)
        elif time_period == 'YTD':
            # Inicio del año
            jan_1 = date(date.today().year, 1, 1)
            start_time = int(time.mktime(jan_1.timetuple()))
        else: # Default
            return pd.DataFrame()
            
    try:
        # Llamada a la API
        response = finnhub_client.stock_candles(clean_ticker, res, start_time, today)

        if response and response['s'] == 'ok':
            # 'c' = close price, 't' = timestamp (seconds)
            df = pd.DataFrame({
                'date': pd.to_datetime(response['t'], unit='s'),
                'price': response['c']
            })
            # Filtrar si la fecha está antes del rango (puede pasar con Finnhub)
            df = df[df['date'] >= pd.to_datetime(start_time, unit='s')]
            return df.set_index('date')
            
    except Exception as e:
        print(f"Error fetching historical data for {clean_ticker}: {e}")
        
    return pd.DataFrame()

def is_ticker_valid(ticker_symbol):
    """
    Checks if a ticker is valid by attempting to fetch its current price quote.
    Returns True if valid (price > 0), False otherwise.
    """
    if not finnhub_client:
        print("⚠️ ADVERTENCIA: Cliente Finnhub no inicializado.")
        # Permitir la adición si la API no está disponible (modo offline/demo)
        return True 

    clean_ticker = str(ticker_symbol).strip().upper()
    
    try:
        # Usamos el endpoint de cotización (quote) que es rápido y barato
        quote = finnhub_client.quote(clean_ticker)
        
        # 'c' es el precio de cierre actual. Si es > 0, es probable que sea válido.
        current_price = float(quote.get('c', 0))
        
        # Si el precio es 0, Finnhub generalmente indica que el ticker no existe o es inválido.
        return current_price > 0 

    except Exception as e:
        # Esto captura errores de red o errores de la API para un ticker no soportado
        print(f"Error de validación del ticker {clean_ticker}: {e}")
        return False


# backend/data_manager.py (NUEVAS FUNCIONES A AÑADIR)

# --- GESTIÓN DE VENTAS Y GANANCIAS REALIZADAS ---

# backend/data_manager.py (Nuevas Funciones)

def add_realized_pl_adjustment(ticker, realized_pl):
    """Agrega ajuste manual para el usuario actual."""
    conn = get_connection()
    uid = get_uid()
    try:
        conn.execute("""
            INSERT INTO pl_adjustments (user_id, date, ticker, realized_pl, description)
            VALUES (?, ?, ?, ?, 'Ajuste manual')
        """, (uid, date.today().strftime('%Y-%m-%d'), ticker.upper(), realized_pl))
        conn.commit()
        return True, "Registrado."
    except Exception as e: return False, str(e)
    finally: conn.close()


def get_pl_adjustments_df():
    """Ajustes manuales FILTRADOS por usuario."""
    conn = get_connection()
    uid = get_uid()
    try:
        return pd.read_sql_query("SELECT * FROM pl_adjustments WHERE user_id = ?", conn, params=(uid,))
    finally: conn.close()



def get_investments_for_sale_dropdown():
    """Retorna las opciones de ticker para vender (solo si shares > 0)."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT ticker, shares FROM investments WHERE shares > 0 ORDER BY ticker ASC")
        data = cursor.fetchall()
        
        return [{'label': f"{ticker} ({shares} un.)", 'value': ticker} for ticker, shares in data]
    except:
        return []
    finally:
        conn.close()


# backend/data_manager.py (Nueva Función)

def undo_investment_transaction(trade_id):
    """Anula una transacción verificando que pertenezca al usuario."""
    conn = get_connection()
    cursor = conn.cursor()
    uid = get_uid()
    
    try:
        # 1. Obtener datos SOLO si pertenece al usuario
        df_trade = pd.read_sql_query("SELECT * FROM investment_transactions WHERE id = ? AND user_id = ?", conn, params=(trade_id, uid))
        if df_trade.empty: return False, "Transacción no encontrada o acceso denegado."
            
        trade = df_trade.iloc[0]
        ticker = trade['ticker']
        t_type = trade['type']
        shares_delta = trade['shares']
        price = trade['price']
        
        # 2. Obtener posición actual
        cursor.execute("SELECT shares, avg_price, total_investment FROM investments WHERE ticker = ? AND user_id = ?", (ticker, uid))
        pos = cursor.fetchone()
        
        # Si la posición ya no existe (ej. vendió todo), la recreamos si es reversión de venta
        shares_current = pos[0] if pos else 0.0
        total_inv_current = pos[2] if pos else 0.0
        avg_price_current = pos[1] if pos else 0.0

        # 3. Lógica de Reversión
        if t_type == 'SELL':
            # Devolver acciones y costo
            new_shares = shares_current + shares_delta
            cost_restored = shares_delta * trade['avg_cost_at_trade']
            new_total_inv = total_inv_current + cost_restored
        elif t_type == 'BUY':
            # Quitar acciones y costo
            new_shares = shares_current - shares_delta
            cost_removed = shares_delta * price
            new_total_inv = total_inv_current - cost_removed
            if new_shares < -0.0001: return False, "Saldo negativo resultante."

        new_avg = new_total_inv / new_shares if new_shares > 0 else 0.0

        # 4. Update o Insert en Investments
        if pos:
            cursor.execute("UPDATE investments SET shares=?, avg_price=?, total_investment=? WHERE ticker=? AND user_id=?", (new_shares, new_avg, new_total_inv, ticker, uid))
        else:
            # Si se había borrado la posición, la revivimos
            # Nota: Necesitamos un display_order, usamos 0 por defecto
            cursor.execute("INSERT INTO investments (user_id, ticker, shares, avg_price, total_investment, asset_type) VALUES (?,?,?,?,?, 'Stock')", (uid, ticker, new_shares, new_avg, new_total_inv))

        # 5. Borrar del historial
        cursor.execute("DELETE FROM investment_transactions WHERE id = ?", (trade_id,))
        conn.commit()
        return True, "Revertido."
    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally: conn.close()

# backend/data_manager.py (Nuevas Funciones Requeridas)


def get_adjustment_id_by_ticker(ticker_display):
    """Busca ID de ajuste filtrando por usuario y limpiando tickers."""
    conn = get_connection()
    uid = get_uid()
    try:
        df = pd.read_sql_query("SELECT id, realized_pl, ticker FROM pl_adjustments WHERE user_id = ?", conn, params=(uid,))
        if df.empty: return None, None
        
        # Comparación flexible (limpiando el ticker de la DB para comparar con el visual)
        df['ticker_clean'] = df['ticker'].apply(clean_ticker_display)
        match = df[df['ticker_clean'] == ticker_display]
        
        if not match.empty:
            return match.iloc[0]['id'], match.iloc[0]['realized_pl']
        return None, None
    finally: conn.close()


def update_pl_adjustment(adj_id, new_pl, new_ticker):
    """Actualiza un ajuste solo si pertenece al usuario."""
    conn = get_connection()
    uid = get_uid()
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE pl_adjustments SET realized_pl=?, ticker=? WHERE id=? AND user_id=?", (new_pl, new_ticker.upper(), adj_id, uid))
        conn.commit()
        return True, "Actualizado."
    except Exception as e: return False, str(e)
    finally: conn.close()

def get_total_realized_pl():
    """Suma P/L de Ventas + Ajustes SOLO del usuario."""
    conn = get_connection()
    uid = get_uid()
    try:
        cursor = conn.cursor()
        # 1. Ventas
        cursor.execute("SELECT SUM(realized_pl) FROM investment_transactions WHERE type = 'SELL' AND user_id = ?", (uid,))
        sales_pl = cursor.fetchone()[0] or 0.0
        
        # 2. Ajustes
        cursor.execute("SELECT SUM(realized_pl) FROM pl_adjustments WHERE user_id = ?", (uid,))
        adj_pl = cursor.fetchone()[0] or 0.0
        
        return sales_pl + adj_pl
    finally: conn.close()
def get_investment_by_ticker(ticker):
    """Obtiene los datos de un activo específico (shares y avg_price) para el formulario de venta."""
    conn = get_connection()
    try:
        df = pd.read_sql_query("SELECT shares, avg_price, id FROM investments WHERE ticker = ?", conn, params=(ticker,))
        if not df.empty:
            return df.iloc[0].to_dict()
        return None
    except:
        return None
    finally:
        conn.close()


def get_investment_by_id(inv_id):
    """Obtiene los datos de un activo específico por ID para la precarga del modal."""
    conn = get_connection()
    try:
        df = pd.read_sql_query("SELECT ticker, shares, total_investment FROM investments WHERE id = ?", conn, params=(inv_id,))
        if not df.empty:
            return df.iloc[0].to_dict()
        return None
    finally:
        conn.close()

# backend/data_manager.py (Funciones de Inversión - Modificadas)

# ... (Las funciones auxiliares get_investment_by_ticker, get_simulator_ticker_data, etc., se mantienen) ...

def add_buy(ticker, shares_bought, buy_price):
    """Registra una compra y actualiza la posición del usuario."""
    conn = get_connection()
    cursor = conn.cursor()
    uid = get_uid() # <--- ID DEL USUARIO
    date_bought = date.today().strftime('%Y-%m-%d')
    
    try:
        # 1. Buscar si el usuario YA tiene este activo
        cursor.execute("SELECT shares, avg_price, total_investment FROM investments WHERE ticker = ? AND user_id = ?", (ticker, uid))
        pos_data = cursor.fetchone()
        
        total_transaction = shares_bought * buy_price
        
        if not pos_data or pos_data[0] == 0:
            # Nueva posición para este usuario
            # Usamos la función add_stock que ya actualizamos previamente (asegúrate de que add_stock use user_id)
            add_stock(ticker, shares_bought, total_transaction)
            avg_cost_at_trade = buy_price 
        else:
            # Actualizar posición existente del usuario
            shares_current, avg_cost_current, total_inv_current = pos_data
            
            new_total_inv = total_inv_current + total_transaction
            new_shares_total = shares_current + shares_bought
            new_avg_price = new_total_inv / new_shares_total
            avg_cost_at_trade = new_avg_price 
            
            cursor.execute("""
                UPDATE investments 
                SET shares = ?, avg_price = ?, total_investment = ?
                WHERE ticker = ? AND user_id = ?
            """, (new_shares_total, new_avg_price, new_total_inv, ticker, uid))
            
        # 2. Registrar en Historial (Con user_id)
        cursor.execute("""
            INSERT INTO investment_transactions (user_id, date, ticker, type, shares, price, total_transaction, avg_cost_at_trade, realized_pl)
            VALUES (?, ?, ?, 'BUY', ?, ?, ?, ?, 0.0)
        """, (uid, date_bought, ticker, shares_bought, buy_price, total_transaction, avg_cost_at_trade))
        
        conn.commit()
        clear_all_caches()
        return True, f"Compra registrada."
    except Exception as e:
        conn.rollback()
        return False, f"Error DB: {str(e)}"
    finally:
        conn.close()


def add_sale(ticker, shares_sold, sale_price):
    """Registra una venta y calcula P/L para el usuario."""
    conn = get_connection()
    cursor = conn.cursor()
    uid = get_uid()
    date_sold = date.today().strftime('%Y-%m-%d')
    
    try:
        # 1. Verificar propiedad del activo
        cursor.execute("SELECT shares, avg_price, total_investment FROM investments WHERE ticker = ? AND user_id = ?", (ticker, uid))
        pos = cursor.fetchone()
        
        if not pos or pos[0] < shares_sold:
            return False, "Unidades insuficientes."
            
        shares_current, avg_cost, total_inv = pos
        
        # 2. Calcular P/L
        realized_pl = (sale_price - avg_cost) * shares_sold
        total_transaction = shares_sold * sale_price
        
        # 3. Registrar Historial (Con user_id)
        cursor.execute("""
            INSERT INTO investment_transactions (user_id, date, ticker, type, shares, price, total_transaction, avg_cost_at_trade, realized_pl)
            VALUES (?, ?, ?, 'SELL', ?, ?, ?, ?, ?)
        """, (uid, date_sold, ticker, shares_sold, sale_price, total_transaction, avg_cost, realized_pl))
        
        # 4. Actualizar posición (Reducir shares y total_investment proporcionalmente)
        new_shares = shares_current - shares_sold
        # El costo promedio NO cambia en una venta, solo el total invertido baja
        new_total_investment = avg_cost * new_shares 
        
        cursor.execute("""
            UPDATE investments SET shares = ?, total_investment = ? WHERE ticker = ? AND user_id = ?
        """, (new_shares, new_total_investment, ticker, uid))
        
        conn.commit()
        clear_all_caches()
        return True, f"Venta registrada. P&L: ${realized_pl:,.2f}"
    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally:
        conn.close()




def delete_sale(sale_id):
    """
    Anula una transacción de venta: elimina el registro y devuelve las acciones al portafolio.
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        # 1. Obtener los datos de la venta a anular
        df_sale = pd.read_sql_query("SELECT ticker, shares, type FROM investment_transactions WHERE id = ?", conn, params=(sale_id,))
        if df_sale.empty or df_sale.iloc[0]['type'] != 'SELL':
            return False, "Venta no encontrada o no es una venta."
            
        sale = df_sale.iloc[0]
        ticker = sale['ticker']
        shares_to_restore = sale['shares']
        
        # 2. Restaurar las unidades en la tabla 'investments'
        # Nota: Asumimos que el costo promedio NO cambia al anular una venta
        cursor.execute("""
            UPDATE investments SET shares = shares + ? WHERE ticker = ?
        """, (shares_to_restore, ticker))
        
        # 3. Eliminar el registro de la venta
        cursor.execute("DELETE FROM investment_transactions WHERE id = ?", (sale_id,))
        
        conn.commit()
        return True, f"Venta de {ticker} anulada. {shares_to_restore} unidades restauradas."
        
    except Exception as e:
        conn.rollback()
        return False, f"Error al anular venta: {str(e)}"
    finally:
        conn.close()


def get_investment_transactions_df(transaction_type=None):
    """Historial de compras/ventas FILTRADO por usuario."""
    conn = get_connection()
    uid = get_uid()
    try:
        base_query = "SELECT * FROM investment_transactions WHERE user_id = ?"
        params = [uid]
        
        if transaction_type in ['BUY', 'SELL']:
             base_query += " AND type = ?"
             params.append(transaction_type)
             
        base_query += " ORDER BY date DESC, id DESC"
            
        df = pd.read_sql_query(base_query, conn, params=params)
        df['date'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d')
        return df
    except: return pd.DataFrame()
    finally: conn.close()




# Modificación al setup de la base de datos (database.py)
# ----------------------------------------------------------------------

# NOTE: Debes asegurarte de que tu archivo `database.py` contenga la nueva tabla
# sales_history y actualizar el archivo `index.py` para usar el nuevo
# `investments.py` como contenedor principal.

# TABLA sales_history:
"""
CREATE TABLE IF NOT EXISTS sales_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    ticker TEXT NOT NULL,
    shares_sold REAL NOT NULL,
    sale_price REAL NOT NULL,
    avg_cost REAL NOT NULL,
    realized_pl REAL NOT NULL,
    sale_value REAL NOT NULL
);
"""

# backend/data_manager.py (Nueva función para el Simulador)

# En backend/data_manager.py


def get_simulator_ticker_data(ticker):
    """
    Retrieves DB data (shares, avg_price) and current price (live API call) 
    for a single ticker required by the simulator.
    """
    conn = get_connection()
    try:
        # 1. Get DB data
        df_db = pd.read_sql_query("SELECT shares, avg_price FROM investments WHERE ticker = ?", conn, params=(ticker,))
        if df_db.empty or df_db.iloc[0]['shares'] <= 0:
            return None 

        db_row = df_db.iloc[0]
        avg_price = db_row['avg_price']
        shares_available = db_row['shares']

        # 2. Get Live Price (Assumes _get_price_finnhub is correctly defined with 4 returns)
        # Requerimos el precio actual
        current_price, _, _, _ = _get_price_finnhub(ticker, avg_price) 
        
        if current_price == 0:
            return None # Invalid ticker or price failed to load
            
        return {
            'shares_available': shares_available,
            'avg_cost': avg_price,
            'current_price': current_price
        }

    except Exception as e:
        print(f"Error fetching simulator data for {ticker}: {e}")
        return None
    finally:
        conn.close()


# backend/data_manager.py (Agregar esta función)

# backend/data_manager.py (get_total_historical_investment_cost)

def get_total_historical_investment_cost():
    """
    Calcula el Costo de Adquisición Total (el capital invertido)
    Costo Total = Costo Activos Vivos + Costo de Activos Vendidos.
    """
    conn = get_connection()
    
    try:
        # 1. Costo Total de Activos Vivos (total_investment)
        cursor = conn.cursor()
        cursor.execute("SELECT SUM(total_investment) FROM investments")
        cost_live_assets = cursor.fetchone()[0] or 0.0
        
        # 2. Costo (Inversión Inicial) de las Ventas Cerradas
        cursor.execute("SELECT SUM(shares * avg_cost_at_trade) FROM investment_transactions WHERE type = 'SELL'")
        cost_sold_assets = cursor.fetchone()[0] or 0.0

        total_cost_acquisition = cost_live_assets + cost_sold_assets
        
        return total_cost_acquisition
        
    except Exception as e:
        print(f"Error calculating total historical cost: {e}")
        return 0.0
    finally:
        conn.close()

# backend/data_manager.py (Nueva Función)
# backend/data_manager.py

# backend/data_manager.py

# backend/data_manager.py

def make_iou_payment(iou_id, payment_amount, account_id=None):
    """
    Registra un abono/pago parcial a una cuenta IOU y actualiza el saldo.
    Retorna 4 VALORES: (success, msg, new_amount, new_status)
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    # Valores por defecto para evitar errores en el return si falla antes
    current_amount = 0.0
    current_status = "Pending"

    try:
        # 1. Obtener datos de la IOU
        iou = get_iou_by_id(iou_id)
        if not iou: 
            return False, "Cuenta no encontrada.", 0.0, "Pending"
        
        current_amount = iou['current_amount']
        current_status = iou['status']
        iou_type = iou['type']
        
        # 2. Validación de Monto
        if payment_amount > current_amount + 0.01:
            return False, f"Monto excede saldo pendiente (${current_amount:,.2f}).", current_amount, current_status
        
        # 3. Calcular nuevo saldo
        new_amount = current_amount - payment_amount
        new_status = 'Pending'
        
        if new_amount <= 0.01: 
            new_amount = 0.0
            new_status = 'Paid'
        elif new_amount < current_amount:
            new_status = 'Partial'

        # 4. Actualizar IOU
        cursor.execute("UPDATE iou SET current_amount = ?, status = ? WHERE id = ?", (new_amount, new_status, iou_id))
        
        msg = f"Abono de ${payment_amount:,.2f} registrado."

        # 5. Registrar Transacción (Si hay cuenta)
        if account_id:
            date_today = date.today().strftime('%Y-%m-%d')
            trans_name = f"Abono IOU: {iou.get('name', 'N/A')}"
            trans_type = 'Income' if iou_type == 'Receivable' else 'Expense'

            # Manejo de Reserva vs Cuenta Normal
            db_acc_id = None if account_id == 'RESERVE' else account_id
            
            cursor.execute("""
                INSERT INTO transactions (date, name, amount, category, type, account_id) 
                VALUES (?, ?, ?, ?, ?, ?)
            """, (date_today, trans_name, payment_amount, 'Deudas/Cobros', trans_type, db_acc_id))

            _adjust_account_balance(cursor, account_id, payment_amount, trans_type, is_reversal=False)
            msg += " Movimiento registrado en cuenta."

        conn.commit()
        # ✅ ESTE ES EL RETORNO CLAVE DE 4 VALORES
        return True, msg, new_amount, new_status
        
    except Exception as e:
        conn.rollback()
        print(f"Error en make_iou_payment: {e}")
        # ✅ EL BLOQUE DE ERROR TAMBIÉN DEBE RETORNAR 4 VALORES
        return False, f"Error: {str(e)}", current_amount, current_status
    finally:
        conn.close()

# backend/data_manager.py (AGREGAR AL FINAL)

# backend/data_manager.py

def process_card_payment(card_id, amount, source_id=None):
    """
    Procesa el pago de una tarjeta de crédito.
    - card_id: ID de la tarjeta a pagar.
    - amount: Monto a pagar.
    - source_id: (Opcional) ID de la cuenta origen o "RESERVE". Si es None, es pago externo.
    """
    conn = get_connection()
    cursor = conn.cursor()
    date_today = date.today().strftime('%Y-%m-%d')
    
    try:
        # 1. Validar Tarjeta
        cursor.execute("SELECT name, current_balance FROM accounts WHERE id = ?", (card_id,))
        res = cursor.fetchone()
        if not res: return False, "Tarjeta no encontrada."
        card_name, current_debt = res
        
        source_name = "Origen Externo" # Valor por defecto si no se selecciona cuenta
        
        # 2. Manejo del Origen de Fondos (SOLO SI SE SELECCIONÓ UNO)
        if source_id:
            if source_id == "RESERVE":
                # A. PAGO DESDE RESERVA
                cursor.execute("SELECT balance FROM abono_reserve WHERE id = 1")
                res_res = cursor.fetchone()
                reserve_bal = res_res[0] if res_res else 0.0
                
                if amount > reserve_bal + 0.01:
                    return False, f"Saldo insuficiente en Reserva (${reserve_bal:,.2f})."
                
                new_reserve = reserve_bal - amount
                cursor.execute("UPDATE abono_reserve SET balance = ? WHERE id = 1", (new_reserve,))
                source_name = "Reserva de Abono"
                
            else:
                # B. PAGO DESDE CUENTA BANCARIA
                cursor.execute("SELECT name, current_balance, type FROM accounts WHERE id = ?", (source_id,))
                res_acc = cursor.fetchone()
                if not res_acc: return False, "Cuenta de origen no encontrada."
                acc_name, acc_bal, acc_type = res_acc
                
                if amount > acc_bal + 0.01:
                    return False, f"Saldo insuficiente en {acc_name} (${acc_bal:,.2f})."
                
                # Registrar GASTO en la cuenta de origen
                _adjust_account_balance(cursor, source_id, amount, 'Expense', is_reversal=False)
                
                # Registrar transacción de salida
                cursor.execute("""
                    INSERT INTO transactions (date, name, amount, category, type, account_id) 
                    VALUES (?, ?, ?, ?, 'Expense', ?)
                """, (date_today, f"Pago a {card_name}", amount, "Transferencia/Pago", source_id))
                
                source_name = acc_name

        # 3. APLICAR PAGO A LA TARJETA (Siempre ocurre)
        _adjust_account_balance(cursor, card_id, amount, 'Income', is_reversal=False)
        
        # Registrar transacción de entrada en la tarjeta
        cursor.execute("""
            INSERT INTO transactions (date, name, amount, category, type, account_id) 
            VALUES (?, ?, ?, ?, 'Income', ?)
        """, (date_today, f"Pago desde {source_name}", amount, "Transferencia/Pago", card_id))
        
        conn.commit()
        return True, f"Pago de ${amount:,.2f} aplicado ({source_name})."
        
    except Exception as e:
        conn.rollback()
        return False, f"Error al procesar pago: {str(e)}"
    finally:
        conn.close()

# backend/data_manager.py

def add_transfer(date_val, name, amount, source_acc_id, dest_acc_id):
    conn = get_connection()
    cursor = conn.cursor()
    uid = get_uid()

    try:
        # --- VALIDACIÓN DE FONDOS EN ORIGEN (NUEVO) ---
        has_funds, error_msg = _check_sufficient_funds(cursor, source_acc_id, amount, uid)
        if not has_funds:
            return False, error_msg
        # ----------------------------------------------

        # Obtener nombres (solo para el texto del registro)
        cursor.execute("SELECT name FROM accounts WHERE id = ? AND user_id = ?", (source_acc_id, uid))
        res_src = cursor.fetchone()
        src_name = res_src[0] if res_src else "Cuenta Origen"

        cursor.execute("SELECT name FROM accounts WHERE id = ? AND user_id = ?", (dest_acc_id, uid))
        res_dest = cursor.fetchone()
        dest_name = res_dest[0] if res_dest else "Cuenta Destino"

        user_detail = f": {name}" if name and name != "-" else ""

        # 1. RETIRO (Expense)
        trans_name_out = f"Transferencia a {dest_name}{user_detail}"
        cursor.execute("""
            INSERT INTO transactions (user_id, date, name, amount, category, type, account_id, subcategory)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (uid, date_val, trans_name_out, amount, "Transferencia", "Expense", source_acc_id, "Movimiento Interno"))

        _adjust_account_balance(cursor, source_acc_id, amount, "Expense", is_reversal=False, user_id=uid)

        # 2. DEPÓSITO (Income)
        trans_name_in = f"Transferencia desde {src_name}{user_detail}"
        cursor.execute("""
            INSERT INTO transactions (user_id, date, name, amount, category, type, account_id, subcategory)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (uid, date_val, trans_name_in, amount, "Transferencia", "Income", dest_acc_id, "Movimiento Interno"))

        _adjust_account_balance(cursor, dest_acc_id, amount, "Income", is_reversal=False, user_id=uid)

        conn.commit()
        clear_all_caches()
        return True, "Transferencia realizada con éxito."
        
    except Exception as e:
        conn.rollback()
        return False, f"Error en transferencia: {e}"
    finally:
        conn.close()


def create_fixed_costs_table():
    conn = get_connection()
    cursor = conn.cursor()
    
    # Definir sintaxis ID según DB
    id_type = "SERIAL PRIMARY KEY" if IS_POSTGRES else "INTEGER PRIMARY KEY AUTOINCREMENT"
    
    cursor.execute(f"""
    CREATE TABLE IF NOT EXISTS fixed_costs (
        id {id_type},
        user_id INTEGER,
        name TEXT NOT NULL,
        amount REAL NOT NULL, 
        frequency INTEGER DEFAULT 1, 
        current_allocation REAL DEFAULT 0.0,
        due_day INTEGER,
        description TEXT,
        is_percentage INTEGER DEFAULT 0,
        min_amount REAL DEFAULT 0.0,
        target_account_id INTEGER
    )
    """)
    conn.commit()
    conn.close()
# 1. CREAR TABLA
def create_savings_table():
    conn = get_connection()
    cursor = conn.cursor()
    
    # Determinar tipo de ID según la base de datos
    id_type = "SERIAL PRIMARY KEY" if IS_POSTGRES else "INTEGER PRIMARY KEY AUTOINCREMENT"
    
    try:
        cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS savings_goals (
            id {id_type},
            user_id INTEGER,
            name TEXT NOT NULL,
            target_amount REAL NOT NULL, 
            current_saved REAL DEFAULT 0.0,
            target_date TEXT, -- YYYY-MM-DD
            icon TEXT,        -- Para futuro (ej. 'car-front', 'plane')
            display_order INTEGER DEFAULT 0,
            target_account_id INTEGER,       -- Agregado para evitar migraciones fallidas
            contribution_mode TEXT DEFAULT 'Date',
            fixed_contribution REAL DEFAULT 0.0,
            percentage_contribution REAL DEFAULT 0.0
        )
        """)
        conn.commit()
    except Exception as e:
        print(f"Error creando tabla savings_goals: {e}")
    finally:
        conn.close()
from werkzeug.security import generate_password_hash, check_password_hash

# EJECUTAR AL IMPORTAR (Justo debajo de check_and_update_users_table)

def get_user_stabilizer_salary():
    """Recupera el salario base específico del estabilizador."""
    conn = get_connection()
    uid = get_uid()
    try:
        cur = conn.cursor()
        cur.execute("SELECT stabilizer_base_salary FROM users WHERE id = ?", (uid,))
        res = cur.fetchone()
        return res[0] if res else 0.0
    finally: conn.close()

def update_user_stabilizer_salary(amount):
    """Guarda el salario base del estabilizador."""
    conn = get_connection()
    uid = get_uid()
    try:
        conn.execute("UPDATE users SET stabilizer_base_salary = ? WHERE id = ?", (amount, uid))
        conn.commit()
        return True
    except: return False
    finally: conn.close()

# 2. AGREGA estas funciones 'Getter' para Inversión y GF
def get_user_inv_fund_account():
    """Obtiene el ID de la cuenta de inversión guardada."""
    conn = get_connection()
    uid = get_uid()
    try:
        cur = conn.cursor()
        cur.execute("SELECT inv_fund_account_id FROM users WHERE id = ?", (uid,))
        res = cur.fetchone()
        return res[0] if res else None
    finally: conn.close()

def get_user_gf_fund_account():
    """Obtiene el ID de la cuenta Guilt Free guardada."""
    conn = get_connection()
    uid = get_uid()
    try:
        cur = conn.cursor()
        cur.execute("SELECT gf_fund_account_id FROM users WHERE id = ?", (uid,))
        res = cur.fetchone()
        return res[0] if res else None
    finally: conn.close()

# 3. AGREGA estas funciones para gestionar el 'Last Total Income'
def get_user_last_income():
    """Recupera el último ingreso ingresado por el usuario."""
    conn = get_connection()
    uid = get_uid()
    try:
        cur = conn.cursor()
        cur.execute("SELECT last_total_income FROM users WHERE id = ?", (uid,))
        res = cur.fetchone()
        return res[0] if res else 0.0
    finally: conn.close()

def update_user_last_income(amount):
    """Guarda el ingreso actual para la próxima vez."""
    conn = get_connection()
    uid = get_uid()
    try:
        conn.execute("UPDATE users SET last_total_income = ? WHERE id = ?", (amount, uid))
        conn.commit()
        return True
    except: return False
    finally: conn.close()
# Ejecuta la migración al importar

def get_all_users_detailed():
    """Retorna lista completa con nuevos campos."""
    conn = get_connection()
    try:
        # Traemos todo excepto el hash del password
        df = pd.read_sql_query("""
            SELECT id, username, email, display_name, created_at, last_login 
            FROM users ORDER BY id ASC
        """, conn)
        return df.to_dict('records')
    finally:
        conn.close()

def admin_update_user_details(user_id, email, display_name):
    """Actualiza email y display_name."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE users SET email = ?, display_name = ? WHERE id = ?
        """, (email, display_name, user_id))
        conn.commit()
        return True, "Datos actualizados."
    except Exception as e:
        return False, f"Error: {str(e)}"
    finally:
        conn.close()

def admin_reset_password(user_id, new_password):
    """Restablece la contraseña de un usuario."""
    conn = get_connection()
    try:
        hashed_pw = generate_password_hash(new_password, method='pbkdf2:sha256')
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET password_hash = ? WHERE id = ?", (hashed_pw, user_id))
        conn.commit()
        return True, "Contraseña restablecida."
    except Exception as e:
        return False, f"Error: {str(e)}"
    finally:
        conn.close()

def update_last_login(user_id):
    """Actualiza la fecha de último login (Llamar desde login.py)."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET last_login = datetime('now', 'localtime') WHERE id = ?", (user_id,))
        conn.commit()
    except: pass
    finally: conn.close()



# backend/data_manager.py

# En backend/data_manager.py

def register_user(username, password, email, display_name=None):
    conn = get_connection()
    cursor = conn.cursor()
    
    clean_username = username.strip().lower() if username else ""
    clean_email = email.strip().lower() if email else "" 
    clean_display = display_name.strip() if display_name else clean_username.capitalize()
    
    try:
        if not clean_username: return False, "El nombre de usuario es obligatorio."

        cursor.execute("SELECT id FROM users WHERE username = ?", (clean_username,))
        if cursor.fetchone(): return False, "El usuario ya existe."

        hashed_pw = generate_password_hash(password.strip(), method='pbkdf2:sha256')
        
        cursor.execute("""
            INSERT INTO users (username, password_hash, email, display_name, created_at) 
            VALUES (?, ?, ?, ?, date('now'))
        """, (clean_username, hashed_pw, clean_email, clean_display))
        
        new_uid = cursor.lastrowid
        
        # --- CATEGORÍAS POR DEFECTO (Las que pediste) ---
        # 0 = Visible, 1 = Oculta (Sistema)
        default_cats = [
            ('Libres', 0),
            ('Costos Fijos', 0),
            ('Ahorro', 0),
            ('Deuda/Cobro', 0),  # La pediste visible o sistema? (0 visible)
            ('Salario', 0),
            ('Inversion', 0),
            # Categorías técnicas necesarias para que el sistema no falle
            ('Transferencia', 1),    
            ('Transferencia/Pago', 1)
        ]
        
        # Insertamos una por una para evitar problemas de drivers con executemany en algunos entornos
        for name, is_excl in default_cats:
            # Usamos INSERT ... ON CONFLICT DO NOTHING para Postgres (o IGNORE en SQLite)
            # Como Python no sabe cuál DB es, hacemos un try-except interno simple
            try:
                cursor.execute(
                    "INSERT INTO categories (name, user_id, is_excluded) VALUES (?, ?, ?)", 
                    (name, new_uid, is_excl)
                )
            except Exception as e:
                # Si falla por duplicado (aunque con el fix de DB no debería), lo ignoramos y seguimos
                print(f"Nota al crear categoría '{name}': {e}")
                pass
        
        conn.commit()
        return True, "Usuario registrado."
    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally:
        conn.close()


def get_excluded_categories_list():
    """Retorna una lista de nombres de categorías que deben excluirse de los gráficos."""
    conn = get_connection()
    uid = get_uid()
    try:
        # Seleccionamos las marcadas como excluidas en la DB
        df = pd.read_sql_query("SELECT name FROM categories WHERE user_id = ? AND is_excluded = 1", conn, params=(uid,))
        if not df.empty:
            return df['name'].tolist()
        return []
    except:
        return []
    finally:
        conn.close()

# --- FUNCIONES DE ADMINISTRADOR ---

def get_all_users():
    """Retorna una lista de diccionarios con todos los usuarios (sin passwords)."""
    conn = get_connection()
    try:
        # Traemos ID, Username y Email. Omitimos el hash del password por seguridad.
        df = pd.read_sql_query("SELECT id, username, email FROM users ORDER BY id ASC", conn)
        return df.to_dict('records')
    except Exception as e:
        print(f"Error fetching users: {e}")
        return []
    finally:
        conn.close()

def admin_delete_user(user_id_to_delete):
    """
    Elimina un usuario y TODOS sus datos asociados (Cascada manual).
    Retorna (Success, Message).
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    # Protección para no borrar al admin principal (asumiendo ID 1 o username 'admin')
    # Aquí validamos por ID, asumiendo que el admin siempre es el ID 1 o validarlo en frontend
    if str(user_id_to_delete) == "1": 
        return False, "No se puede eliminar al usuario Admin principal."

    try:
        # 1. Borrar Transacciones
        cursor.execute("DELETE FROM transactions WHERE user_id = ?", (user_id_to_delete,))
        # 2. Borrar Inversiones e historial
        cursor.execute("DELETE FROM investments WHERE user_id = ?", (user_id_to_delete,))
        cursor.execute("DELETE FROM investment_transactions WHERE user_id = ?", (user_id_to_delete,))
        cursor.execute("DELETE FROM pl_adjustments WHERE user_id = ?", (user_id_to_delete,))
        # 3. Borrar Cuentas, Cuotas, IOU
        cursor.execute("DELETE FROM accounts WHERE user_id = ?", (user_id_to_delete,))
        cursor.execute("DELETE FROM installments WHERE user_id = ?", (user_id_to_delete,))
        cursor.execute("DELETE FROM iou WHERE user_id = ?", (user_id_to_delete,))
        # 4. Borrar Categorias y Subcategorias personalizadas
        cursor.execute("DELETE FROM categories WHERE user_id = ?", (user_id_to_delete,))
        cursor.execute("DELETE FROM subcategories WHERE user_id = ?", (user_id_to_delete,))
        # 5. Borrar Reservas
        cursor.execute("DELETE FROM abono_reserve WHERE user_id = ?", (user_id_to_delete,))
        
        # 6. Finalmente, borrar el Usuario
        cursor.execute("DELETE FROM users WHERE id = ?", (user_id_to_delete,))
        
        conn.commit()
        return True, f"Usuario ID {user_id_to_delete} y todos sus datos eliminados."
        
    except Exception as e:
        conn.rollback()
        return False, f"Error al eliminar usuario: {str(e)}"
    finally:
        conn.close()

# backend/data_manager.py


# backend/data_manager.py

# backend/data_manager.py

def add_fixed_cost(name, amount, frequency, due_day=1, current_allocation=0.0, is_percentage=0, min_amount=0.0):
    conn = get_connection()
    uid = get_uid()
    try:
        conn.execute("""
            INSERT INTO fixed_costs (user_id, name, amount, frequency, current_allocation, due_day, is_percentage, min_amount)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (uid, name, amount, frequency, current_allocation, due_day, is_percentage, min_amount))
        conn.commit()
        clear_all_caches()
        return True, "Costo agregado."
    except Exception as e: return False, str(e)
    finally: conn.close()

def update_fixed_cost(fc_id, name, amount, frequency, due_day, current_allocation, is_percentage, min_amount):
    conn = get_connection()
    uid = get_uid()
    try:
        conn.execute("""
            UPDATE fixed_costs 
            SET name=?, amount=?, frequency=?, due_day=?, current_allocation=?, is_percentage=?, min_amount=?
            WHERE id=? AND user_id=?
        """, (name, amount, frequency, due_day, current_allocation, is_percentage, min_amount, fc_id, uid))
        conn.commit()
        clear_all_caches()
        return True, "Actualizado."
    except Exception as e: return False, str(e)
    finally: conn.close()

# --- OPTIMIZACIÓN COSTOS FIJOS ---

@cache.memoize(timeout=300)
def _get_fixed_costs_df_cached(user_id):
    """Función interna que SÍ usa caché porque recibe user_id explícito."""
    conn = get_connection()
    try:
        df = pd.read_sql_query("SELECT * FROM fixed_costs WHERE user_id = ?", conn, params=(user_id,))
        if not df.empty:
            df['monthly_cost'] = df['amount'] / df['frequency']
        return df
    except: return pd.DataFrame()
    finally: conn.close()

def get_fixed_costs_df():
    """Función pública que obtiene el ID y llama a la versión cacheada."""
    uid = get_uid()
    return _get_fixed_costs_df_cached(uid)

def delete_fixed_cost(fc_id):
    conn = get_connection()
    uid = get_uid()
    try:
        conn.execute("DELETE FROM fixed_costs WHERE id=? AND user_id=?", (fc_id, uid))
        conn.commit()
        clear_all_caches()
        return True, "Eliminado."
    except Exception as e: return False, str(e)
    finally: conn.close()

def update_fixed_cost_allocation(fc_id, new_allocation):
    """Actualiza cuánto dinero hay apartado para este costo específico."""
    conn = get_connection()
    uid = get_uid()
    try:
        conn.execute("UPDATE fixed_costs SET current_allocation = ? WHERE id = ? AND user_id = ?", (new_allocation, fc_id, uid))
        conn.commit()
        clear_all_caches()
        return True, "Saldo actualizado."
    except Exception as e: return False, str(e)
    finally: conn.close()

def get_user_distribution_accounts():
    """Retorna un dict con TODAS las cuentas por defecto del usuario."""
    conn = get_connection()
    uid = get_uid()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT fc_fund_account_id, sv_fund_account_id, inv_fund_account_id, gf_fund_account_id, income_account_id 
            FROM users WHERE id = ?
        """, (uid,))
        res = cursor.fetchone()
        if res:
            return {
                'FC': res[0],
                'SV': res[1],
                'INV': res[2],
                'GF': res[3],
                'SOURCE': res[4]
            }
        return {'FC': None, 'SV': None, 'INV': None, 'GF': None, 'SOURCE': None}
    finally:
        conn.close()
        
def update_user_inv_fund_account(account_id):
    conn = get_connection()
    uid = get_uid()
    try:
        conn.execute("UPDATE users SET inv_fund_account_id = ? WHERE id = ?", (account_id, uid))
        conn.commit()
        return True
    finally: conn.close()

def update_user_gf_fund_account(account_id):
    conn = get_connection()
    uid = get_uid()
    try:
        conn.execute("UPDATE users SET gf_fund_account_id = ? WHERE id = ?", (account_id, uid))
        conn.commit()
        return True
    finally: conn.close()

def update_user_income_account(account_id):
    conn = get_connection()
    uid = get_uid()
    try:
        conn.execute("UPDATE users SET income_account_id = ? WHERE id = ?", (account_id, uid))
        conn.commit()
        return True
    finally: conn.close()

def get_user_fc_fund_account():
    """Obtiene el ID de la cuenta de fondos guardada para el usuario actual."""
    conn = get_connection()
    uid = get_uid()
    try:
        cur = conn.cursor()
        cur.execute("SELECT fc_fund_account_id FROM users WHERE id = ?", (uid,))
        res = cur.fetchone()
        return res[0] if res else None
    finally: conn.close()

def update_user_fc_fund_account(account_id):
    """Guarda la preferencia de cuenta de fondos."""
    conn = get_connection()
    uid = get_uid()
    try:
        conn.execute("UPDATE users SET fc_fund_account_id = ? WHERE id = ?", (account_id, uid))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error guardando preferencia: {e}")
        return False
    finally: conn.close()

def get_distribution_rule_by_id(rule_id):
    """Obtiene una regla específica para editarla."""
    conn = get_connection()
    uid = get_uid()
    try:
        df = pd.read_sql_query("SELECT * FROM distribution_rules WHERE id=? AND user_id=?", conn, params=(rule_id, uid))
        if not df.empty:
            return df.iloc[0].to_dict()
        return None
    finally: conn.close()

def update_distribution_rule(rule_id, name, alloc_type, value):
    """Actualiza una regla existente."""
    conn = get_connection()
    uid = get_uid()
    try:
        conn.execute("""
            UPDATE distribution_rules
            SET name=?, allocation_type=?, value=?
            WHERE id=? AND user_id=?
        """, (name, alloc_type, value, rule_id, uid))
        conn.commit()
        clear_all_caches()
        return True, "Regla actualizada."
    except Exception as e: return False, str(e)
    finally: conn.close()
# 3. FUNCIONES CRUD PARA SAVINGS
# MODIFICAR: add_saving_goal
def add_saving_goal(name, target_amount, current_saved, target_date=None, 
                    mode='Date', fixed_val=0.0, pct_val=0.0):
    conn = get_connection()
    uid = get_uid()
    try:
        conn.execute("""
            INSERT INTO savings_goals (user_id, name, target_amount, current_saved, target_date, 
                                       contribution_mode, fixed_contribution, percentage_contribution)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (uid, name, target_amount, current_saved, target_date, mode, fixed_val, pct_val))
        conn.commit()
        clear_all_caches()
        return True, "Meta creada."
    except Exception as e: return False, str(e)
    finally: conn.close()

# MODIFICAR: update_saving_goal
def update_saving_goal(goal_id, name, target_amount, current_saved, target_date,
                       mode, fixed_val, pct_val):
    conn = get_connection()
    uid = get_uid()
    try:
        conn.execute("""
            UPDATE savings_goals 
            SET name=?, target_amount=?, current_saved=?, target_date=?,
                contribution_mode=?, fixed_contribution=?, percentage_contribution=?
            WHERE id=? AND user_id=?
        """, (name, target_amount, current_saved, target_date, mode, fixed_val, pct_val, goal_id, uid))
        conn.commit()
        clear_all_caches()
        return True, "Meta actualizada."
    except Exception as e: return False, str(e)
    finally: conn.close()

def delete_saving_goal(goal_id):
    conn = get_connection()
    uid = get_uid()
    try:
        conn.execute("DELETE FROM savings_goals WHERE id=? AND user_id=?", (goal_id, uid))
        conn.commit()
        clear_all_caches()  
        return True, "Meta eliminada."
    except Exception as e: return False, str(e)
    finally: conn.close()

# --- OPTIMIZACIÓN METAS DE AHORRO ---

@cache.memoize(timeout=300)
def _get_savings_goals_df_cached(user_id):
    conn = get_connection()
    try:
        return pd.read_sql_query("SELECT * FROM savings_goals WHERE user_id = ?", conn, params=(user_id,))
    finally: conn.close()

def get_savings_goals_df():
    uid = get_uid()
    return _get_savings_goals_df_cached(uid)
# Preferencia de cuenta para Savings
# backend/data_manager.py

def get_user_sv_fund_account():
    """Obtiene el ID de la cuenta de ahorros guardada para el usuario."""
    conn = get_connection()
    uid = get_uid()
    try:
        cur = conn.cursor()
        cur.execute("SELECT sv_fund_account_id FROM users WHERE id = ?", (uid,))
        res = cur.fetchone()
        return res[0] if res else None
    except: return None
    finally: conn.close()

def update_user_sv_fund_account(account_id):
    """Guarda la preferencia de cuenta de ahorros."""
    conn = get_connection()
    uid = get_uid()
    try:
        conn.execute("UPDATE users SET sv_fund_account_id = ? WHERE id = ?", (account_id, uid))
        conn.commit()
        return True
    except: return False
    finally: conn.close()

def update_user_sv_fund_account(account_id):
    conn = get_connection()
    uid = get_uid()
    try:
        conn.execute("UPDATE users SET sv_fund_account_id = ? WHERE id = ?", (account_id, uid))
        conn.commit()
        return True
    except: return False
    finally: conn.close()

# backend/data_manager.py

def add_distribution_rule(cat_type, name, alloc_type, value, target_acc):
    conn = get_connection()
    uid = get_uid()
    try:
        conn.execute("""
            INSERT INTO distribution_rules (user_id, category_type, name, allocation_type, value, target_account_id)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (uid, cat_type, name, alloc_type, value, target_acc))
        conn.commit()
        clear_all_caches()
        return True, "Regla agregada."
    
    except Exception as e: return False, str(e)
    finally: conn.close()

def delete_distribution_rule(rule_id):
    conn = get_connection()
    uid = get_uid()
    try:
        conn.execute("DELETE FROM distribution_rules WHERE id=? AND user_id=?", (rule_id, uid))
        conn.commit()
        clear_all_caches()
        return True, "Eliminado."
    except Exception as e: return False, str(e)
    finally: conn.close()

# --- OPTIMIZACIÓN REGLAS DE DISTRIBUCIÓN ---

@cache.memoize(timeout=300)
def _get_distribution_rules_cached(user_id, cat_type):
    conn = get_connection()
    try:
        return pd.read_sql_query("SELECT * FROM distribution_rules WHERE user_id=? AND category_type=?", conn, params=(user_id, cat_type))
    finally: conn.close()

def get_distribution_rules(cat_type):
    uid = get_uid()
    return _get_distribution_rules_cached(uid, cat_type)
# --- ACTUALIZAR PREFERENCIA DE CUENTA EN TABLAS EXISTENTES ---

def update_item_target_account(table_name, item_id, account_id):
    """Guarda la cuenta destino para un costo fijo o meta de ahorro."""
    conn = get_connection()
    uid = get_uid()
    try:
        # table_name debe ser 'fixed_costs' o 'savings_goals' (validado por lógica interna)
        if table_name not in ['fixed_costs', 'savings_goals']: return False
        
        query = f"UPDATE {table_name} SET target_account_id = ? WHERE id = ? AND user_id = ?"
        conn.execute(query, (account_id, item_id, uid))
        conn.commit()
        return True
    except: return False
    finally: conn.close()


# --- LA FUNCIÓN MAESTRA: DISTRIBUIR ---

def execute_distribution_process(income_total, source_account_id, distribution_data):
    """
    Ejecuta el reparto masivo.
    distribution_data: Lista de dicts { 'type': 'FC'/'SV'/'INV'/'GF', 'id': db_id, 'amount': $$, 'target_acc': acc_id, 'name': str }
    """
    conn = get_connection()
    cursor = conn.cursor()
    uid = get_uid()
    date_val = date.today().strftime('%Y-%m-%d')
    
    try:
        # 1. Validar Fondos en Origen
        total_needed = sum(d['amount'] for d in distribution_data)
        has_funds, msg = _check_sufficient_funds(cursor, source_account_id, total_needed, uid)
        if not has_funds: return False, msg

        logs = []

        for item in distribution_data:
            amount = item['amount']
            if amount <= 0: continue
            
            target_acc = item.get('target_acc')
            name = item['name']
            itype = item['type']
            iid = item['id']

            # A. TRANSFERENCIA DE DINERO (Si hay cuenta destino y es diferente a origen)
            if target_acc and str(target_acc) != str(source_account_id):
                # Usamos la lógica de transferencia manual pero paso a paso para que sea atómico
                # Retiro Origen
                cursor.execute("""
                    INSERT INTO transactions (user_id, date, name, amount, category, type, account_id, subcategory)
                    VALUES (?, ?, ?, ?, 'Transferencia', 'Expense', ?, 'Reparto Ingresos')
                """, (uid, date_val, f"Reparto: {name}", amount, source_account_id))
                _adjust_account_balance(cursor, source_account_id, amount, 'Expense', False, uid)
                
                # Ingreso Destino
                cursor.execute("""
                    INSERT INTO transactions (user_id, date, name, amount, category, type, account_id, subcategory)
                    VALUES (?, ?, ?, ?, 'Transferencia', 'Income', ?, 'Reparto Ingresos')
                """, (uid, date_val, f"Recibido: {name}", amount, target_acc))
                _adjust_account_balance(cursor, target_acc, amount, 'Income', False, uid)
            
            elif not target_acc:
                # Si no hay cuenta destino, solo se descuenta del origen como Gasto (Ya se pagó o salió)
                # Opcional: Depende de como quiera el usuario. Asumiremos que si no hay destino, se queda en la cuenta origen
                # pero se marca "lógicamente". 
                pass 

            # B. ACTUALIZACIÓN LÓGICA (Apartados)
            if itype == 'FC': # Fixed Costs
                # Usamos COALESCE(current_allocation, 0) para evitar errores si el campo es NULL
                cursor.execute("""
                    UPDATE fixed_costs 
                    SET current_allocation = COALESCE(current_allocation, 0) + ? 
                    WHERE id=? AND user_id=?
                """, (amount, iid, uid))
                
            elif itype == 'SV': # Savings
                cursor.execute("""
                    UPDATE savings_goals 
                    SET current_saved = COALESCE(current_saved, 0) + ? 
                    WHERE id=? AND user_id=?
                """, (amount, iid, uid))
            
            logs.append(f"{name}: ${amount:,.2f}")

        conn.commit()
        return True, f"Reparto exitoso de ${total_needed:,.2f}"
        
    except Exception as e:
        conn.rollback()
        return False, f"Error en distribución: {e}"
    finally:
        conn.close()

# --- EN backend/data_manager.py ---

# 1. Función auxiliar para verificar/crear la subcategoría
def _ensure_subcategory_exists(category_name, subcategory_name, user_id):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        # Verificar si existe la subcategoría para ese usuario y categoría padre
        cursor.execute("""
            SELECT id FROM subcategories 
            WHERE user_id = ? AND name = ? AND parent_category = ?
        """, (user_id, subcategory_name, category_name))
        
        if not cursor.fetchone():
            # Si no existe, crearla
            cursor.execute("""
                INSERT INTO subcategories (user_id, name, parent_category) 
                VALUES (?, ?, ?)
            """, (user_id, subcategory_name, category_name))
            conn.commit()
    except Exception as e:
        print(f"Error asegurando subcategoría: {e}")
    finally:
        conn.close()

# 2. Función Principal: Pagar Costo Fijo
def pay_fixed_cost_balance(fc_id, amount, account_id):
    """
    Registra el pago de un Costo Fijo:
    1. Crea transacción de Gasto (Cat: Costos Fijos, Subcat: Nombre del FC).
    2. Descuenta el monto pagado del 'current_allocation' del Costo Fijo.
    """
    conn = get_connection()
    cursor = conn.cursor()
    uid = get_uid()
    date_val = date.today().strftime('%Y-%m-%d')
    
    try:
        # A. Obtener datos del Costo Fijo
        cursor.execute("SELECT name, current_allocation FROM fixed_costs WHERE id = ? AND user_id = ?", (fc_id, uid))
        fc = cursor.fetchone()
        if not fc: return False, "Costo fijo no encontrado."
        
        fc_name = fc[0]
        
        # B. Validar Fondos en la cuenta real
        has_funds, msg = _check_sufficient_funds(cursor, account_id, amount, uid)
        if not has_funds: return False, msg

        # C. Asegurar que exista la Subcategoría (Nombre del FC) dentro de 'Costos Fijos'
        # Nota: Hacemos esto fuera de la transacción principal o dentro, aquí usamos la lógica auxiliar
        _ensure_subcategory_exists("Costos Fijos", fc_name, uid)

        # D. Registrar la Transacción (Gasto Real)
        cursor.execute("""
            INSERT INTO transactions (user_id, date, name, amount, category, type, account_id, subcategory)
            VALUES (?, ?, ?, ?, 'Costos Fijos', 'Expense', ?, ?)
        """, (uid, date_val, f"Pago: {fc_name}", amount, account_id, fc_name))
        
        # E. Actualizar Saldo Real de la Cuenta Bancaria
        _adjust_account_balance(cursor, account_id, amount, 'Expense', is_reversal=False, user_id=uid)
        
        # F. Descontar del "Apartado Virtual" (Allocation) del Costo Fijo
        # Usamos MAX(0, ...) para que no quede negativo si pagas de más por alguna razón, 
        # o puedes quitar el MAX si permites saldos negativos.
        cursor.execute("""
            UPDATE fixed_costs 
            SET current_allocation = current_allocation - ? 
            WHERE id = ? AND user_id = ?
        """, (amount, fc_id, uid))

        conn.commit()
        clear_all_caches()
        return True, f"Pago de {fc_name} registrado exitosamente."
        
    except Exception as e:
        conn.rollback()
        return False, f"Error al pagar costo fijo: {str(e)}"
    finally:
        conn.close()

# --- EN backend/data_manager.py ---

def process_savings_withdrawal(goal_id, amount, account_id, is_transfer=False, 
                               dest_acc_id=None, category=None, subcategory=None, note=None):
    """
    Procesa el retiro de una meta de ahorro.
    1. Si es Transferencia: Mueve saldo entre cuentas.
    2. Si es Gasto: Crea una transacción de gasto con categoría/subcategoría.
    3. En ambos casos: Descuenta el monto de 'current_saved' en la meta.
    """
    conn = get_connection()
    cursor = conn.cursor()
    uid = get_uid()
    date_val = date.today().strftime('%Y-%m-%d')
    
    try:
        # A. Obtener info de la meta
        cursor.execute("SELECT name, current_saved FROM savings_goals WHERE id = ? AND user_id = ?", (goal_id, uid))
        res = cursor.fetchone()
        if not res: return False, "Meta no encontrada."
        goal_name, current_saved = res
        
        # Validación básica (opcional, se puede permitir quedar en negativo si se desea)
        # if amount > current_saved: return False, "El monto excede lo ahorrado."

        # B. PROCESAR EL MOVIMIENTO DE DINERO
        if is_transfer:
            # Opción 1: Transferencia entre cuentas
            if not dest_acc_id: return False, "Falta cuenta destino."
            
            # Reutilizamos la lógica de transferencia (pero paso a paso para mantener la transacción abierta)
            # Retiro Origen
            cursor.execute("""
                INSERT INTO transactions (user_id, date, name, amount, category, type, account_id, subcategory)
                VALUES (?, ?, ?, ?, 'Transferencia', 'Expense', ?, 'Retiro de Ahorro')
            """, (uid, date_val, f"Retiro Meta: {goal_name}", amount, account_id))
            _adjust_account_balance(cursor, account_id, amount, 'Expense', False, uid)
            
            # Ingreso Destino
            cursor.execute("""
                INSERT INTO transactions (user_id, date, name, amount, category, type, account_id, subcategory)
                VALUES (?, ?, ?, ?, 'Transferencia', 'Income', ?, 'Retiro de Ahorro')
            """, (uid, date_val, f"Ingreso Meta: {goal_name}", amount, dest_acc_id))
            _adjust_account_balance(cursor, dest_acc_id, amount, 'Income', False, uid)
            
            action_msg = "Transferencia realizada"

        else:
            # Opción 2: Gasto (Compra real)
            if not category: return False, "Falta categoría."
            
            # Verificar subcategoría si se seleccionó una
            if subcategory:
                _ensure_subcategory_exists(category, subcategory, uid)
            
            trans_name = f"{goal_name}: {note}" if note else f"Gasto de Meta: {goal_name}"
            
            cursor.execute("""
                INSERT INTO transactions (user_id, date, name, amount, category, type, account_id, subcategory)
                VALUES (?, ?, ?, ?, ?, 'Expense', ?, ?)
            """, (uid, date_val, trans_name, amount, category, account_id, subcategory))
            
            _adjust_account_balance(cursor, account_id, amount, 'Expense', False, uid)
            action_msg = "Gasto registrado"

        # C. ACTUALIZAR LA META (Restar lo gastado/movido)
        # Usamos MAX(0, ...) para evitar negativos si prefieres, o lo dejas libre.
        cursor.execute("""
            UPDATE savings_goals 
            SET current_saved = current_saved - ?
            WHERE id = ? AND user_id = ?
        """, (amount, goal_id, uid))
        
        conn.commit()
        return True, f"{action_msg} y meta actualizada."

    except Exception as e:
        conn.rollback()
        return False, f"Error: {str(e)}"
    finally:
        conn.close()

# 2. Preferencia de Cuenta Estabilizadora
def get_user_stabilizer_account():
    conn = get_connection()
    uid = get_uid()
    try:
        cur = conn.cursor()
        cur.execute("SELECT stabilizer_account_id FROM users WHERE id = ?", (uid,))
        res = cur.fetchone()
        return res[0] if res else None
    finally: conn.close()

def update_user_stabilizer_account(acc_id):
    conn = get_connection()
    uid = get_uid()
    try:
        conn.execute("UPDATE users SET stabilizer_account_id = ? WHERE id = ?", (acc_id, uid))
        conn.commit()
        return True
    finally: conn.close()

# 3. CRUD Eventos
def add_income_event(name, amount, date_val):
    conn = get_connection()
    uid = get_uid()
    try:
        conn.execute("INSERT INTO income_events (user_id, name, amount, event_date) VALUES (?, ?, ?, ?)", 
                     (uid, name, amount, date_val))
        conn.commit()
        clear_all_caches()
        return True, "Evento agregado."
    except Exception as e: return False, str(e)
    finally: conn.close()

def delete_income_event(event_id):
    conn = get_connection()
    uid = get_uid()
    try:
        conn.execute("DELETE FROM income_events WHERE id = ? AND user_id = ?", (event_id, uid))
        conn.commit()
        clear_all_caches()
        return True, "Eliminado."
    except: return False, "Error"
    finally: conn.close()

# --- OPTIMIZACIÓN ESTABILIZADOR ---

@cache.memoize(timeout=300)
def _get_income_events_df_cached(user_id):
    conn = get_connection()
    try:
        return pd.read_sql_query("SELECT * FROM income_events WHERE user_id = ? ORDER BY event_date ASC", conn, params=(user_id,))
    finally: conn.close()

def get_income_events_df():
    uid = get_uid()
    return _get_income_events_df_cached(uid)
# En backend/data_manager.py

def get_income_event_by_id(event_id):
    """Obtiene un evento específico para cargarlo en el modal de edición."""
    conn = get_connection()
    uid = get_uid()
    try:
        # Buscamos por ID y Usuario para seguridad
        df = pd.read_sql_query("SELECT * FROM income_events WHERE id = ? AND user_id = ?", conn, params=(event_id, uid))
        if not df.empty:
            return df.iloc[0].to_dict()
        return None
    finally: conn.close()

def update_income_event(event_id, name, amount, date_val):
    """Actualiza un evento existente."""
    conn = get_connection()
    uid = get_uid()
    try:
        conn.execute("""
            UPDATE income_events 
            SET name = ?, amount = ?, event_date = ?
            WHERE id = ? AND user_id = ?
        """, (name, amount, date_val, event_id, uid))
        conn.commit()
        clear_all_caches()
        return True, "Evento actualizado."
    except Exception as e: return False, str(e)
    finally: conn.close()
# 4. Lógica de Simulación (El corazón del sistema)
# --- EN backend/data_manager.py ---

# --- EN backend/data_manager.py ---

import calendar
from dateutil.relativedelta import relativedelta # Asegúrate de tener dateutil o usa lógica nativa

# En backend/data_manager.py

# En backend/data_manager.py

def calculate_stabilizer_projection(base_salary_monthly, current_stabilizer_balance, frequency='monthly'):
    """
    Proyecta usando la lógica de "Mínimo Sostenible" (Cuello de botella).
    Calcula el máximo retiro posible que asegura que el saldo NUNCA baje de cero
    en ningún punto del futuro.
    """
    events_df = get_income_events_df()
    
    # 1. CÁLCULO DE TOTALES E IDEALES
    total_bonuses = events_df['amount'].sum() if not events_df.empty else 0
    annual_base_salary = base_salary_monthly * 12
    total_annual_income = annual_base_salary + total_bonuses
    
    if frequency == 'biweekly':
        periods_count = 24
        lbl_freq = "Q"
    else:
        periods_count = 12
        lbl_freq = "Mes"

    # Meta Ideal (Si tuviéramos todo el dinero hoy en la mano)
    total_per_period_ideal = total_annual_income / periods_count
    supplement_ideal = total_per_period_ideal - (base_salary_monthly / (2 if frequency == 'biweekly' else 1))
    supplement_ideal = max(0, supplement_ideal)

    # 2. GENERAR TIMELINE (Igual que siempre)
    today = date.today()
    timeline = []
    curr_date = today
    
    if frequency == 'biweekly':
        if curr_date.day <= 15:
            start_date = date(curr_date.year, curr_date.month, 15)
        else:
            last_day = calendar.monthrange(curr_date.year, curr_date.month)[1]
            start_date = date(curr_date.year, curr_date.month, last_day)
    else:
        last_day = calendar.monthrange(curr_date.year, curr_date.month)[1]
        start_date = date(curr_date.year, curr_date.month, last_day)

    temp_date = start_date
    for i in range(periods_count):
        period_end_date = temp_date
        
        # Labels
        if frequency == 'biweekly':
            is_first_half = (period_end_date.day <= 15)
            q_label = "Q1" if is_first_half else "Q2"
            month_label = calendar.month_name[period_end_date.month][:3]
            label = f"{month_label} {q_label}"
            
            if is_first_half:
                last_d = calendar.monthrange(period_end_date.year, period_end_date.month)[1]
                temp_date = date(period_end_date.year, period_end_date.month, last_d)
            else:
                next_m = period_end_date + relativedelta(months=1)
                temp_date = date(next_m.year, next_m.month, 15)
        else:
            month_label = calendar.month_name[period_end_date.month][:3]
            label = f"{month_label} {str(period_end_date.year)[2:]}"
            temp_date = period_end_date + relativedelta(months=1)
            last_d = calendar.monthrange(temp_date.year, temp_date.month)[1]
            temp_date = date(temp_date.year, temp_date.month, last_d)

        # Inflows
        period_inflow = 0
        if not events_df.empty:
            for _, ev in events_df.iterrows():
                ev_d = datetime.strptime(ev['event_date'], '%Y-%m-%d').date()
                if ev_d.month == period_end_date.month and ev_d.year == period_end_date.year:
                    if frequency == 'monthly':
                        period_inflow += ev['amount']
                    else:
                        is_ev_first_half = ev_d.day <= 15
                        is_period_first_half = period_end_date.day <= 15
                        if is_ev_first_half == is_period_first_half:
                            period_inflow += ev['amount']

        timeline.append({'label': label, 'inflow': period_inflow})

    # 3. ALGORITMO DE SOSTENIBILIDAD (EL CORAZÓN DEL CÁLCULO)
    # Buscamos el "Mínimo Sostenible". 
    # Calculamos cuánto podríamos retirar si quisiéramos llegar a CADA punto 'i' con saldo 0.
    # El menor de esos valores es nuestro límite seguro hoy.
    
    max_sustainable_withdrawal = float('inf')
    cumulative_inflow = 0
    bottleneck_period = None
    
    for i, p in enumerate(timeline):
        cumulative_inflow += p['inflow']
        
        # Fórmula: (Saldo Inicial + Entradas hasta hoy) / (Periodos hasta hoy)
        limit_at_this_point = (current_stabilizer_balance + cumulative_inflow) / (i + 1)
        
        if limit_at_this_point < max_sustainable_withdrawal:
            max_sustainable_withdrawal = limit_at_this_point
            bottleneck_period = p['label']

    # El retiro real es el menor entre el Ideal (461) y el Sostenible (207)
    # Nunca retiramos más del ideal, pero bajamos si la sostenibilidad lo exige.
    suggested_withdrawal = min(supplement_ideal, max_sustainable_withdrawal)
    suggested_withdrawal = max(0, suggested_withdrawal) # Nunca negativo

    # 4. PROYECCIÓN FINAL
    final_projection = []
    current_bal = current_stabilizer_balance
    
    for p in timeline:
        # Proyectamos usando el retiro sugerido calculado arriba
        next_bal = current_bal + p['inflow'] - suggested_withdrawal
        
        # Corrección visual pequeña: evitamos -0.00
        if abs(next_bal) < 0.01: next_bal = 0.0
        
        final_projection.append({
            'Month': p['label'],
            'Balance': next_bal,
            'Inflow': p['inflow'],
            'Outflow': suggested_withdrawal
        })
        current_bal = next_bal

    # is_capped: True si estamos retirando MENOS del ideal (ej. retirando 207 en vez de 461)
    is_capped = suggested_withdrawal < (supplement_ideal - 0.01)

    return {
        'total_annual_income': total_annual_income,
        'supplement_ideal': supplement_ideal,       # Meta (461)
        'suggested_withdrawal': suggested_withdrawal, # Real Hoy (207)
        'projection': pd.DataFrame(final_projection),
        'is_capped': is_capped, # Bandera para mostrar advertencia
        'bottleneck_period': bottleneck_period # Para decir "hasta Marzo"
    }
# 5. Ejecutar el Retiro (Mover dinero de Caja Chica -> Cuenta Principal)
def execute_stabilizer_withdrawal(amount, source_acc_id, dest_acc_id):
    conn = get_connection()
    cursor = conn.cursor()
    uid = get_uid()
    date_val = date.today().strftime('%Y-%m-%d')
    try:
        # Validación
        has_funds, msg = _check_sufficient_funds(cursor, source_acc_id, amount, uid)
        if not has_funds: return False, msg
        
        # Transacción de Salida (Caja Chica)
        cursor.execute("""
            INSERT INTO transactions (user_id, date, name, amount, category, type, account_id, subcategory)
            VALUES (?, ?, 'Retiro Estabilizador', ?, 'Transferencia', 'Expense', ?, 'Sueldo Saludable')
        """, (uid, date_val, amount, source_acc_id))
        _adjust_account_balance(cursor, source_acc_id, amount, 'Expense', False, uid)
        
        # Transacción de Entrada (Cuenta Principal / Gasto Corriente)
        if dest_acc_id:
             cursor.execute("""
                INSERT INTO transactions (user_id, date, name, amount, category, type, account_id, subcategory)
                VALUES (?, ?, 'Ingreso Estabilizador', ?, 'Transferencia', 'Income', ?, 'Sueldo Saludable')
            """, (uid, date_val, amount, dest_acc_id))
             _adjust_account_balance(cursor, dest_acc_id, amount, 'Income', False, uid)
             
        conn.commit()
        return True, "Suplemento transferido con éxito."
    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally: conn.close()

# --- AGREGAR AL FINAL DE backend/data_manager.py ---

def manual_price_refresh():
    """
    Fuerza la actualización de precios y retorna el estado de la conexión.
    Retorna: (Success: bool, Message: str)
    """
    if not finnhub_client:
        return False, "Error: API Key no configurada en .env"

    conn = get_connection()
    uid = get_uid()
    
    try:
        # 1. Obtener tickers del usuario
        df = pd.read_sql_query("SELECT DISTINCT ticker FROM investments WHERE user_id = ?", conn, params=(uid,))
        tickers = df['ticker'].tolist()
        
        if not tickers:
            return True, "No tienes activos para actualizar."

        # 2. Intentar actualizar (Capturando errores de red)
        success_count = 0
        errors = []
        
        cursor = conn.cursor()
        for t in tickers:
            try:
                # Llamada a la API
                q = finnhub_client.quote(t)
                
                # Validación básica de respuesta
                if q['c'] == 0 and q['d'] is None:
                    # A veces devuelve 0 si el ticker está mal, pero no es error de red
                    continue 

                # Guardar en Caché Global
                cursor.execute("""
                UPDATE market_cache 
                SET price=%s, day_change=%s, day_change_pct=%s, day_high=%s, day_low=%s, last_updated=CURRENT_TIMESTAMP
                WHERE ticker=%s
            """, (q['c'], q['d'], q['dp'], q['h'], q['l'], t))
                
                # Si no existía (ej. se borró el caché), insertamos lo básico
                if cursor.rowcount == 0:
                    cursor.execute("""
                    INSERT INTO market_cache (ticker, price, day_change, day_change_pct, last_updated)
                    VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP)
                    """, (t, q['c'], q['d'], q['dp']))
                
                success_count += 1
                time.sleep(0.1) # Respetar límites de API
                
            except Exception as e:
                errors.append(f"{t}: {str(e)}")

        conn.commit()
        
        # 3. Evaluar resultados
        if success_count == len(tickers):
            clear_all_caches()
            return True, f"Precios actualizados ({success_count}/{len(tickers)})."
        elif success_count > 0:
            clear_all_caches()
            return True, f"Actualización parcial. Fallaron {len(errors)} activos."
        else:
            # Si fallaron todos, probablemente es error de conexión o límite de API
            error_detail = errors[0] if errors else "Sin respuesta"
            return False, f"Fallo de conexión con el Mercado. ({error_detail})"

    except Exception as e:
        return False, f"Error interno: {str(e)}"
    finally:
        conn.close()