import sqlite3
import pandas as pd
import os
from datetime import date, datetime
import calendar
import finnhub
import time
import json
from dotenv import load_dotenv
from pathlib import Path
from flask_login import current_user  


base_dir = Path(__file__).resolve().parent.parent
env_path = base_dir / '.env'
load_dotenv(dotenv_path=env_path)

DB_DIR = "data"
DB_PATH = os.path.join(DB_DIR, "pivot.db")

api_key = os.getenv("FINNHUB_API_KEY")

if api_key:
    finnhub_client = finnhub.Client(api_key=api_key)
else:
    print("⚠️ ADVERTENCIA: No se encontró FINNHUB_API_KEY en el archivo .env")
    finnhub_client = None 

def get_connection():
    return sqlite3.connect(DB_PATH)

def get_uid():
    """Retorna el ID del usuario actual de manera segura."""
    if current_user and current_user.is_authenticated:
        return current_user.id
    return 1 # Fallback al Admin (ID 1) si algo falla, para no romper en pruebas


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
        df = pd.read_sql_query("""
            SELECT bank_name, SUM(current_balance) as total_balance
            FROM accounts
            WHERE type IN ('Debit', 'Cash') AND user_id = ?
            GROUP BY bank_name
            HAVING total_balance > 0
        """, conn, params=(uid,))
        return df
    finally: conn.close()


# data_manager.py

def get_credit_summary_data():
    """Métricas de Crédito (Límite, Deuda, Cuotas) filtradas por usuario."""
    conn = get_connection()
    uid = get_uid()
    summary = {'total_limit': 0.0, 'total_debt': 0.0, 'total_installments': 0.0}
    try:
        # Solo tarjetas del usuario
        df = pd.read_sql_query("SELECT id, credit_limit, current_balance FROM accounts WHERE type = 'Credit' AND user_id = ?", conn, params=(uid,))
        
        if df.empty: return summary

        summary['total_limit'] = df['credit_limit'].sum()
        summary['total_debt'] = df['current_balance'].sum()
        
        # Solo cuotas del usuario
        installments_df = pd.read_sql_query("SELECT * FROM installments WHERE user_id = ?", conn, params=(uid,))
        total_pending = 0.0
        
        for _, row in df.iterrows():
            acc_id = row['id']
            my_installs = installments_df[installments_df['account_id'] == acc_id]
            
            for _, inst_row in my_installs.iterrows():
                if inst_row['total_quotas'] > 0:
                    total_with_int = inst_row['total_amount'] * (1 + (inst_row['interest_rate'] / 100))
                    quota_val = total_with_int / inst_row['total_quotas']
                    remaining = inst_row['total_quotas'] - inst_row['paid_quotas']
                    total_pending += quota_val * remaining
        
        summary['total_installments'] = total_pending
        
    finally:
        conn.close()
    return summary



def get_asset_type_summary():
    """Calcula el saldo total agrupado por el tipo de cuenta (Debit, Cash)."""
    conn = get_connection()
    try:
        query = """
            SELECT type, SUM(current_balance) as total_balance
            FROM accounts
            WHERE type IN ('Debit', 'Cash')
            GROUP BY type
            HAVING total_balance > 0
        """
        df = pd.read_sql_query(query, conn)
        return df
    except Exception as e:
        print(f"Error getting asset type summary: {e}")
        return pd.DataFrame()
    finally:
        conn.close()


# --- FINANCIAMIENTOS (INSTALLMENTS) ---
def add_installment(account_id, name, amount, rate, total_q, paid_q, pay_day):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO installments (account_id, name, total_amount, interest_rate, total_quotas, paid_quotas, payment_day)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (account_id, name, amount, rate, total_q, paid_q, pay_day))
        conn.commit()
        return True, "Financiamiento agregado."
    except Exception as e:
        return False, str(e)
    finally:
        conn.close()

def update_installment(inst_id, name, amount, rate, total_q, paid_q, pay_day):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            UPDATE installments 
            SET name = ?, total_amount = ?, interest_rate = ?, total_quotas = ?, paid_quotas = ?, payment_day = ?
            WHERE id = ?
        """, (name, amount, rate, total_q, paid_q, pay_day, inst_id))
        conn.commit()
        return True, "Financiamiento actualizado."
    except Exception as e:
        return False, str(e)
    finally:
        conn.close()

def get_installments(account_id):
    conn = get_connection()
    try:
        df = pd.read_sql_query("SELECT * FROM installments WHERE account_id = ?", conn, params=(account_id,))
    except: df = pd.DataFrame()
    conn.close()
    return df

def delete_installment(installment_id):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM installments WHERE id = ?", (installment_id,))
        conn.commit()
        return True, "Eliminado."
    except Exception as e: return False, str(e)
    finally: conn.close()

# --- TRANSACCIONES Y ANALYTICS ---
def add_transaction(date, name, amount, category, trans_type, account_id, subcategory=None):
    conn = get_connection()
    cursor = conn.cursor()
    uid = get_uid()
    try:
        # Insertar con user_id
        cursor.execute("""
            INSERT INTO transactions (user_id, date, name, amount, category, type, account_id, subcategory) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (uid, date, name, amount, category, trans_type, account_id, subcategory))
        
        # Ajuste de saldo (validando que la cuenta sea del usuario)
        _adjust_account_balance(cursor, account_id, amount, trans_type, is_reversal=False, user_id=uid)
        
        conn.commit()
        return True, "Registrado."
    except Exception as e: return False, str(e)
    finally: conn.close()

def get_transactions_df():
    conn = get_connection()
    uid = get_uid()
    try:
        # Solo transacciones del usuario
        df = pd.read_sql_query("""
            SELECT t.*, a.name as account_name 
            FROM transactions t 
            LEFT JOIN accounts a ON t.account_id = a.id 
            WHERE t.user_id = ? 
            ORDER BY t.date DESC
        """, conn, params=(uid,))
    except: df = pd.DataFrame()
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

def get_monthly_summary():
    """Flujo de caja mensual del usuario."""
    df = get_transactions_df() # Esta función ya filtra por usuario internamente
    if df.empty: return pd.DataFrame()
    df['date'] = pd.to_datetime(df['date'])
    df['Month'] = df['date'].dt.strftime('%Y-%m')
    return df.groupby(['Month', 'type'])['amount'].sum().reset_index()


def get_category_summary():
    """Gastos por categoría del usuario."""
    df = get_transactions_df()
    if df.empty: return pd.DataFrame()
    return df[df['type'] == 'Expense'].groupby('category')['amount'].sum().reset_index()


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
        df = pd.read_sql_query("""
            SELECT name, SUM(current_balance) as total_balance
            FROM accounts
            WHERE type IN ('Debit', 'Cash') AND user_id = ?
            GROUP BY name
            HAVING total_balance > 0
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
        if not df.empty: return df.iloc[0].to_dict()
        return None
    finally: conn.close()



# backend/data_manager.py

def _adjust_account_balance(cursor, account_id, amount, trans_type, is_reversal=False, user_id=None):
    if user_id is None: return 

    # Caso Reserva
    if account_id == 'RESERVE':
        cursor.execute("SELECT balance FROM abono_reserve WHERE user_id = ?", (user_id,))
        res = cursor.fetchone()
        if not res: 
            cursor.execute("INSERT INTO abono_reserve (user_id, balance) VALUES (?, 0.0)", (user_id,))
            current = 0.0
        else: current = res[0]
        
        mult = -1 if is_reversal else 1
        change = (amount * mult) if trans_type == 'Income' else (amount * mult * -1)
        cursor.execute("UPDATE abono_reserve SET balance = ? WHERE user_id = ?", (current + change, user_id))
        return

    # Caso Cuenta Normal
    cursor.execute("SELECT type, current_balance FROM accounts WHERE id = ? AND user_id = ?", (account_id, user_id))
    res = cursor.fetchone()
    if not res: return
    
    acc_type, current = res
    mult = -1 if is_reversal else 1
    
    if acc_type == 'Credit':
        # Gasto SUMA deuda, Ingreso RESTA
        change = (amount * mult) if trans_type == 'Expense' else (amount * mult * -1)
    else:
        # Gasto RESTA saldo, Ingreso SUMA
        change = (amount * mult * -1) if trans_type == 'Expense' else (amount * mult)
        
    cursor.execute("UPDATE accounts SET current_balance = current_balance + ? WHERE id = ? AND user_id = ?", (change, account_id, user_id))



def delete_transaction(trans_id):
    conn = get_connection()
    cursor = conn.cursor()
    uid = get_uid()
    try:
        trans = get_transaction_by_id(trans_id) # Esta función ya filtra por usuario internamente
        if not trans: return False, "No encontrado."
        
        _adjust_account_balance(cursor, trans['account_id'], trans['amount'], trans['type'], is_reversal=True, user_id=uid)
        
        cursor.execute("DELETE FROM transactions WHERE id = ? AND user_id = ?", (trans_id, uid))
        conn.commit()
        return True, "Eliminado."
    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally: conn.close()



def update_transaction(trans_id, new_date, new_name, new_amount, new_category, new_type, new_account_id, new_subcategory=None):
    conn = get_connection()
    cursor = conn.cursor()
    uid = get_uid()
    try:
        # Verificar propiedad
        old_trans = get_transaction_by_id(trans_id)
        if not old_trans: return False, "No encontrado."

        _adjust_account_balance(cursor, old_trans['account_id'], old_trans['amount'], old_trans['type'], is_reversal=True, user_id=uid)
        
        cursor.execute("""
            UPDATE transactions 
            SET date = ?, name = ?, amount = ?, category = ?, type = ?, account_id = ?, subcategory = ?
            WHERE id = ? AND user_id = ?
        """, (new_date, new_name, new_amount, new_category, new_type, new_account_id, new_subcategory, trans_id, uid))

        _adjust_account_balance(cursor, new_account_id, new_amount, new_type, is_reversal=False, user_id=uid)
        conn.commit()
        return True, "Actualizado."
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
    conn = get_connection()
    uid = get_uid()
    try:
        cur = conn.cursor()
        cur.execute("SELECT balance FROM abono_reserve WHERE user_id = ?", (uid,))
        res = cur.fetchone()
        return res[0] if res else 0.0
    finally: conn.close()


def update_credit_abono_reserve(amount):
    """Actualiza (reemplaza) el saldo de la reserva de abono."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        
        # 1. Asegura que la tabla exista (solo si no se inicializó en init_db)
        setup_abono_reserve() 
        
        # 2. Inserta o reemplaza el valor único con ID=1
        cursor.execute("INSERT OR REPLACE INTO abono_reserve (id, balance) VALUES (1, ?)", (amount,))
        conn.commit()
        return True, "Reserva de abono actualizada."
    except Exception as e:
        return False, str(e)
    finally:
        conn.close()

def setup_abono_reserve():
    """Crea la tabla abono_reserve si no existe e inicializa el saldo."""
    conn = get_connection()
    cursor = conn.cursor()
    # Usamos CREATE TABLE IF NOT EXISTS para que funcione si init_db() no se ejecutó aún con esta tabla
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS abono_reserve (
            id INTEGER PRIMARY KEY,
            balance REAL DEFAULT 0.0
        )
    """)
    # Asegurarse de que siempre haya una fila con ID 1
    cursor.execute("INSERT OR IGNORE INTO abono_reserve (id, balance) VALUES (1, 0.0)")
    conn.commit()
    conn.close()

# data_manager.py

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

def get_stocks_data(force_refresh=False):
    """
    Obtiene el portafolio del usuario actual combinando:
    1. Datos privados (investments: shares, avg_price) -> Filtrado por user_id
    2. Datos globales (market_cache: price, news) -> Sin filtrar (compartido)
    """
    conn = get_connection()
    uid = get_uid() # ID del usuario actual
    
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
               c.fiftyTwo_high, c.fiftyTwo_low, 
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
    """Devuelve la fecha más reciente de actualización."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        # Verificamos si la tabla existe primero para evitar errores
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='market_cache'")
        if not cursor.fetchone(): return "Nunca"

        cursor.execute("SELECT MAX(last_updated) FROM market_cache")
        res = cursor.fetchone()
        
        if res and res[0]:
            # Formateamos la fecha para que sea legible (YYYY-MM-DD HH:MM)
            dt = datetime.strptime(res[0], '%Y-%m-%d %H:%M:%S')
            return dt.strftime('%d/%m %H:%M')
        return "Sin datos"
    except Exception as e:
        return "Error"
    finally:
        conn.close()
# backend/data_manager.py

def get_net_worth_breakdown(force_refresh=False):
    conn = get_connection()
    uid = get_uid()
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
        stocks = get_stocks_data(force_refresh)
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

# --- MODIFICAR ESTAS FUNCIONES EXISTENTES PARA INCLUIR 'subcategory' ---

# Firma nueva: agregar argumento 'subcategory'
def add_transaction(date, name, amount, category, t_type, account_id, subcategory=None):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        # Incluir subcategory en el INSERT
        cursor.execute("""
            INSERT INTO transactions (date, name, amount, category, type, account_id, subcategory) 
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (date, name, amount, category, t_type, account_id, subcategory))
        
        # ... (Lógica de actualización de saldo de cuenta se mantiene igual) ...
        _adjust_account_balance(cursor, account_id, amount, t_type, is_reversal=False)
        
        conn.commit()
        return True, "Registrado."
    except Exception as e: return False, str(e)
    finally: conn.close()

def update_transaction(trans_id, new_date, new_name, new_amount, new_category, new_type, new_account_id, new_subcategory=None):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        old_trans = get_transaction_by_id(trans_id)
        if not old_trans: return False, "Original no encontrada."

        # 1. Reversar saldo anterior
        _adjust_account_balance(cursor, old_trans['account_id'], old_trans['amount'], old_trans['type'], is_reversal=True)
        
        # 2. Update con subcategory
        cursor.execute("""
            UPDATE transactions 
            SET date = ?, name = ?, amount = ?, category = ?, type = ?, account_id = ?, subcategory = ?
            WHERE id = ?
        """, (new_date, new_name, new_amount, new_category, new_type, new_account_id, new_subcategory, trans_id))

        # 3. Aplicar nuevo saldo
        _adjust_account_balance(cursor, new_account_id, new_amount, new_type, is_reversal=False)
        
        conn.commit()
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

# ... (otras funciones) ...

def get_historical_networth_trend(start_date=None, end_date=None):
    """Historial de patrimonio filtrado por usuario."""
    conn = get_connection()
    uid = get_uid()
    try:
        # Patrimonio actual del usuario
        current_nw = get_net_worth_breakdown()['net_worth']
        today = date.today()
        
        # Transacciones del usuario
        df_trans = pd.read_sql_query("SELECT date, amount, type FROM transactions WHERE user_id = ?", conn, params=(uid,))
        
        if df_trans.empty: return pd.DataFrame()
            
        df_trans['date'] = pd.to_datetime(df_trans['date']).dt.date
        min_db_date = df_trans['date'].min()
        
        req_start = date.fromisoformat(start_date) if start_date else min_db_date
        req_end = date.fromisoformat(end_date) if end_date else today
        
        calc_start = min(req_start, min_db_date)
        calc_end = max(req_end, today)
        
        daily_changes = df_trans.groupby(['date', 'type'])['amount'].sum().unstack(fill_value=0)
        if 'Income' not in daily_changes.columns: daily_changes['Income'] = 0
        if 'Expense' not in daily_changes.columns: daily_changes['Expense'] = 0
        
        daily_changes['net_change'] = daily_changes['Income'] - daily_changes['Expense']
        
        full_idx = pd.date_range(start=calc_start, end=calc_end).date
        df_history = pd.DataFrame(index=full_idx)
        df_history.index.name = 'date'
        
        df_history = df_history.join(daily_changes['net_change']).fillna(0)
        df_history = df_history.sort_index(ascending=False)
        
        cumulative_changes = df_history['net_change'].cumsum()
        df_history['net_worth'] = current_nw - cumulative_changes + df_history['net_change']
        
        df_history = df_history.sort_index().reset_index()
        mask = (df_history['date'] >= req_start) & (df_history['date'] <= req_end)
        return df_history.loc[mask]

    finally:
        conn.close()


# backend/data_manager.p
# 
# y
# backend/data_manager.py

# backend/data_manager.py (MODIFICADO)

# --- GESTIÓN DE INVERSIONES (STOCKS) ---

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
# backend/data_manager.py (Nueva función add_buy)

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

def add_transfer(date_val, name, amount, source_acc_id, dest_acc_id):
    """
    Registra una transferencia interna como dos movimientos:
    1. Gasto (Expense) en la cuenta origen.
    2. Ingreso (Income) en la cuenta destino.
    Usa la categoría 'Transferencia' y ajusta saldos automáticamente.
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        # 1. Obtener nombres de las cuentas para que el registro se vea bonito
        cursor.execute("SELECT name FROM accounts WHERE id = ?", (source_acc_id,))
        res_src = cursor.fetchone()
        src_name = res_src[0] if res_src else "Cuenta Origen"

        cursor.execute("SELECT name FROM accounts WHERE id = ?", (dest_acc_id,))
        res_dest = cursor.fetchone()
        dest_name = res_dest[0] if res_dest else "Cuenta Destino"

        # Detalle adicional si el usuario escribió algo
        user_detail = f": {name}" if name and name != "-" else ""

        # ---------------------------------------------------------
        # PASO A: RETIRO DEL ORIGEN (Expense)
        # ---------------------------------------------------------
        trans_name_out = f"Transferencia a {dest_name}{user_detail}"
        
        cursor.execute("""
            INSERT INTO transactions (date, name, amount, category, type, account_id, subcategory)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (date_val, trans_name_out, amount, "Transferencia", "Expense", source_acc_id, "Movimiento Interno"))

        # Actualizar Saldo Origen (Resta)
        _adjust_account_balance(cursor, source_acc_id, amount, "Expense", is_reversal=False)

        # ---------------------------------------------------------
        # PASO B: DEPÓSITO AL DESTINO (Income)
        # ---------------------------------------------------------
        trans_name_in = f"Transferencia desde {src_name}{user_detail}"
        
        cursor.execute("""
            INSERT INTO transactions (date, name, amount, category, type, account_id, subcategory)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (date_val, trans_name_in, amount, "Transferencia", "Income", dest_acc_id, "Movimiento Interno"))

        # Actualizar Saldo Destino (Suma)
        _adjust_account_balance(cursor, dest_acc_id, amount, "Income", is_reversal=False)

        conn.commit()
        return True, "Transferencia realizada con éxito."
        
    except Exception as e:
        conn.rollback() # Deshacer cambios si algo falla a la mitad
        print(f"Error en add_transfer: {e}")
        return False, f"Error en transferencia: {e}"
    finally:
        conn.close()

# backend/data_manager.py (AGREGAR AL FINAL)

from werkzeug.security import generate_password_hash
# backend/data_manager.py

def register_user(username, password, email):
    """
    Crea un nuevo usuario con normalización de datos:
    - Username: Sin espacios y en minúsculas (Case Insensitive).
    - Password: Sin espacios laterales, pero Case Sensitive.
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    # --- 1. NORMALIZACIÓN DE DATOS (TRIM Y LOWER) ---
    # Convertimos a minúsculas para que "Prueba" y "prueba" sean lo mismo
    clean_username = username.strip().lower()
    clean_email = email.strip().lower()
    
    # La contraseña solo se limpia de espacios, pero SE RESPETA el Case (Mayús/Minús)
    clean_password = password.strip()
    
    try:
        # 2. Verificar si el usuario ya existe (buscando por el normalizado)
        cursor.execute("SELECT id FROM users WHERE username = ?", (clean_username,))
        if cursor.fetchone():
            return False, "El nombre de usuario ya existe."

        # 3. Crear el usuario (Hasheando la contraseña limpia)
        hashed_pw = generate_password_hash(clean_password, method='pbkdf2:sha256')
        
        cursor.execute("""
            INSERT INTO users (username, password_hash, email) 
            VALUES (?, ?, ?)
        """, (clean_username, hashed_pw, clean_email))
        
        new_user_id = cursor.lastrowid
        
        # 4. Crear Categorías por Defecto
        defaults = [
            ('Costos Fijos', new_user_id), 
            ('Libres (Guilt Free)', new_user_id), 
            ('Inversión', new_user_id), 
            ('Ahorro', new_user_id), 
            ('Deudas/Cobros', new_user_id), 
            ('Ingresos', new_user_id)
        ]
        cursor.executemany("INSERT INTO categories (name, user_id) VALUES (?, ?)", defaults)
        
        conn.commit()
        return True, "Usuario registrado exitosamente."
        
    except Exception as e:
        conn.rollback()
        return False, f"Error al registrar: {str(e)}"
    finally:
        conn.close()