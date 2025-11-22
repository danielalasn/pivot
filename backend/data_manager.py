import sqlite3
import pandas as pd
import os
from datetime import date, timedelta
import calendar
import finnhub # NUEVA LIBRERÍA
import time

from dotenv import load_dotenv # IMPORTAR ESTO

# backend/data_manager.py

import sqlite3
import pandas as pd
import os
from datetime import date
import finnhub
from dotenv import load_dotenv 
from pathlib import Path # 

# --- CARGA ROBUSTA DE ENV ---
# Esto busca el archivo .env en la carpeta RAÍZ del proyecto,
# subiendo un nivel desde donde está este archivo (backend/)
base_dir = Path(__file__).resolve().parent.parent
env_path = base_dir / '.env'

load_dotenv(dotenv_path=env_path)

# --- CONFIGURACIÓN ---
DB_DIR = "data"
# ... resto del código ...
DB_PATH = os.path.join(DB_DIR, "pivot.db")

# OBTENER LA CLAVE DE MANERA SEGURA
# Si no encuentra la clave, usará None o puedes poner un string vacío
api_key = os.getenv("FINNHUB_API_KEY")

if api_key:
    finnhub_client = finnhub.Client(api_key=api_key)
else:
    print("⚠️ ADVERTENCIA: No se encontró FINNHUB_API_KEY en el archivo .env")
    # Creamos un cliente dummy o manejamos el error para que no rompa el import
    finnhub_client = None 

def get_connection():
    return sqlite3.connect(DB_PATH)

# --- GESTIÓN DE CUENTAS ---

# Definición robusta con kwargs para evitar errores si faltan argumentos
def add_account(name, acc_type, balance, bank_name="-", credit_limit=0, payment_day=None, cutoff_day=None, interest_rate=0, deferred_balance=0, installments_total=0, installments_paid=0, installments_day=0):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT MAX(display_order) FROM accounts")
        res = cursor.fetchone()
        max_order = res[0] if res[0] is not None else 0
        new_order = max_order + 1

        cursor.execute("""
            INSERT INTO accounts (name, type, current_balance, bank_name, credit_limit, payment_day, cutoff_day, interest_rate, display_order, deferred_balance)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (name, acc_type, balance, bank_name, credit_limit, payment_day, cutoff_day, interest_rate, new_order, deferred_balance))
        conn.commit()
        return True, "Cuenta creada exitosamente."
    except Exception as e:
        return False, f"Error al crear: {str(e)}"
    finally:
        conn.close()

def update_account(account_id, name, acc_type, balance, bank_name, credit_limit, payment_day, cutoff_day, interest_rate=0, deferred_balance=0, installments_total=0, installments_paid=0, installments_day=0):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            UPDATE accounts 
            SET name = ?, type = ?, current_balance = ?, bank_name = ?, credit_limit = ?, payment_day = ?, cutoff_day = ?, interest_rate = ?, deferred_balance = ?
            WHERE id = ?
        """, (name, acc_type, balance, bank_name, credit_limit, payment_day, cutoff_day, interest_rate, deferred_balance, account_id))
        conn.commit()
        return True, "Cuenta actualizada exitosamente."
    except Exception as e:
        return False, f"Error al actualizar: {str(e)}"
    finally:
        conn.close()

def delete_account(account_id):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM transactions WHERE account_id = ?", (account_id,))
        cursor.execute("DELETE FROM installments WHERE account_id = ?", (account_id,)) 
        cursor.execute("DELETE FROM accounts WHERE id = ?", (account_id,))
        conn.commit()
        return True, "Cuenta eliminada."
    except Exception as e:
        return False, f"Error al eliminar: {str(e)}"
    finally:
        conn.close()

def get_accounts_by_category(category_group):
    conn = get_connection()
    try:
        df = pd.read_sql_query("SELECT * FROM accounts ORDER BY display_order ASC", conn)
        if df.empty: return df
        
        df.fillna(0, inplace=True)
        df['bank_name'] = df['bank_name'].replace(0, "-").replace("0", "-")
        
        if category_group == 'Credit':
            df = df[df['type'] == 'Credit']
            
            # Calcular total real de financiamientos
            installments_df = pd.read_sql_query("SELECT * FROM installments", conn)
            
            def calc_total_installments(acc_id):
                if installments_df.empty: return 0.0
                my_installs = installments_df[installments_df['account_id'] == acc_id]
                total_pending = 0.0
                for _, row in my_installs.iterrows():
                    if row['total_quotas'] > 0:
                        # --- LÓGICA NUEVA ---
                        total_with_interest = row['total_amount'] * (1 + (row['interest_rate'] / 100))
                        quota_val = total_with_interest / row['total_quotas']
                        # --------------------
                        
                        remaining = row['total_quotas'] - row['paid_quotas']
                        total_pending += quota_val * remaining
                return total_pending

            df['installments_pending_total'] = df['id'].apply(calc_total_installments)
        else:
            df = df[df['type'] != 'Credit']
            
        df.reset_index(drop=True, inplace=True)
    except:
        df = pd.DataFrame()
    finally:
        conn.close()
    return df

def change_account_order(account_id, direction, category_group):
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
        if order1 == order2: order1, order2 = idx + 1, swap_idx + 1
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE accounts SET display_order = ? WHERE id = ?", (int(order2), int(id1)))
        cursor.execute("UPDATE accounts SET display_order = ? WHERE id = ?", (int(order1), int(id2)))
        conn.commit()
        conn.close()

def get_account_options():
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id, name, bank_name, type FROM accounts ORDER BY display_order ASC")
        data = cursor.fetchall()
    except: data = []
    conn.close()
    return [{'label': f"{name} - {bank} ({atype})", 'value': i} for i, name, bank, atype in data]

# data_manager.py

def get_account_type_summary():
    """Calcula el total de activos, pasivos formales, y añade el detalle de cuotas para el resumen superior."""
    conn = get_connection()
    summary = {}
    try:
        # Get Credit Summary Data (Reuse the calculation that fetches installment totals)
        credit_data = get_credit_summary_data() 
        
        # 1. CÁLCULO DE CUENTAS BANCARIAS Y CRÉDITO
        df_accounts = pd.read_sql_query("SELECT type, current_balance FROM accounts", conn)
        
        total_assets = df_accounts[df_accounts['type'].isin(['Debit', 'Cash'])]['current_balance'].sum()
        total_liabilities = df_accounts[df_accounts['type'] == 'Credit']['current_balance'].sum()
        
        # 2. CÁLCULO DE DEUDAS INFORMALES (IOU) - (Must be kept to ensure Net Worth is correct)
        df_iou = pd.read_sql_query("SELECT type, current_amount FROM iou WHERE status = 'Pending'", conn)
        liabilities_informal = df_iou[df_iou['type'] == 'Payable']['current_amount'].sum() if not df_iou.empty else 0.0
        
        # --- RETURN MODIFICADO ---
        summary['TotalAssets'] = total_assets
        # Sumamos pasivos formales e informales para el KPI superior
        summary['TotalLiabilities'] = total_liabilities + liabilities_informal 
        summary['InstallmentsDebt'] = credit_data['total_installments'] # Detalle de cuotas
        
    except Exception as e:
        print(f"Error getting account type summary: {e}")
        summary['TotalAssets'] = 0.0
        summary['TotalLiabilities'] = 0.0
        summary['InstallmentsDebt'] = 0.0
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
    """Obtiene el saldo total por banco para cuentas de Débito/Efectivo."""
    conn = get_connection()
    try:
        query = """
            SELECT bank_name, SUM(current_balance) as total_balance
            FROM accounts
            WHERE type IN ('Debit', 'Cash')
            GROUP BY bank_name
            HAVING total_balance > 0
        """
        df = pd.read_sql_query(query, conn)
        return df
    except Exception as e:
        print(f"Error getting debit bank summary: {e}")
        return pd.DataFrame()
    finally:
        conn.close()

# data_manager.py

def get_credit_summary_data():
    """Obtiene métricas clave: Límite Total, Deuda Total y Deuda de Financiamientos."""
    conn = get_connection()
    summary = {
        'total_limit': 0.0,
        'total_debt': 0.0,
        'total_installments': 0.0
    }
    try:
        df = pd.read_sql_query("SELECT id, credit_limit, current_balance FROM accounts WHERE type = 'Credit'", conn)
        
        if df.empty:
            return summary

        summary['total_limit'] = df['credit_limit'].sum()
        summary['total_debt'] = df['current_balance'].sum()
        
        # Calcular la deuda pendiente de financiamientos usando la lógica de amortización
        installments_df = pd.read_sql_query("SELECT * FROM installments", conn)
        total_pending = 0.0
        
        for _, row in df.iterrows():
            acc_id = row['id']
            my_installs = installments_df[installments_df['account_id'] == acc_id]
            
            for _, inst_row in my_installs.iterrows():
                tq = inst_row['total_quotas']
                pq = inst_row['paid_quotas']
                
                if tq > 0:
                    annual_rate = inst_row['interest_rate']
                    amount = inst_row['total_amount']
                    
                    if annual_rate > 0:
                        i = annual_rate / 12 / 100
                        n = tq
                        denominator = ((1 + i) ** n) - 1
                        if denominator != 0:
                            numerator = i * ((1 + i) ** n)
                            q_val = amount * (numerator / denominator)
                        else:
                            q_val = amount / tq
                    else:
                        q_val = amount / tq
                    
                    remaining = tq - pq
                    total_pending += q_val * remaining
        
        summary['total_installments'] = total_pending
        
    except Exception as e:
        print(f"Error getting credit summary data: {e}")
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
def add_transaction(date, name, amount, category, trans_type, account_id):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO transactions (date, name, amount, category, type, account_id) VALUES (?, ?, ?, ?, ?, ?)", 
                       (date, name, amount, category, trans_type, account_id))
        
        cursor.execute("SELECT type FROM accounts WHERE id = ?", (account_id,))
        res = cursor.fetchone()
        acc_type = res[0] if res else "Debit"

        if acc_type == 'Credit':
            if trans_type == 'Expense':
                cursor.execute("UPDATE accounts SET current_balance = current_balance + ? WHERE id = ?", (amount, account_id))
            else:
                cursor.execute("UPDATE accounts SET current_balance = current_balance - ? WHERE id = ?", (amount, account_id))
        else:
            if trans_type == 'Expense':
                cursor.execute("UPDATE accounts SET current_balance = current_balance - ? WHERE id = ?", (amount, account_id))
            else:
                cursor.execute("UPDATE accounts SET current_balance = current_balance + ? WHERE id = ?", (amount, account_id))
        
        conn.commit()
        return True, "Registrado."
    except Exception as e: return False, str(e)
    finally: conn.close()

def get_transactions_df():
    conn = get_connection()
    try:
        df = pd.read_sql_query("SELECT t.*, a.name as account_name FROM transactions t LEFT JOIN accounts a ON t.account_id = a.id ORDER BY t.date DESC", conn)
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
    df = get_transactions_df()
    if df.empty: return pd.DataFrame()
    df['date'] = pd.to_datetime(df['date'])
    df['Month'] = df['date'].dt.strftime('%Y-%m')
    return df.groupby(['Month', 'type'])['amount'].sum().reset_index()

def get_category_summary():
    df = get_transactions_df()
    if df.empty: return pd.DataFrame()
    return df[df['type'] == 'Expense'].groupby('category')['amount'].sum().reset_index()

def add_iou(name, amount, iou_type, due_date, person_name=None, description=None):
    conn = get_connection()
    cursor = conn.cursor()
    date_created = date.today().strftime('%Y-%m-%d')
    
    # current_amount inicialmente es igual a amount
    try:
        cursor.execute("""
            INSERT INTO iou (name, amount, type, current_amount, date_created, due_date, person_name, description)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (name, amount, iou_type, amount, date_created, due_date, person_name, description)) # AÑADIR person_name, description
        conn.commit()
        return True, "Deuda/Cobro registrado."
    except Exception as e:
        return False, f"Error al registrar: {str(e)}"
    finally:
        conn.close()


def get_iou_df():
    conn = get_connection()
    try:
        # Recuperamos todas las deudas pendientes
        df = pd.read_sql_query("SELECT * FROM iou WHERE status = 'Pending' ORDER BY date_created DESC", conn)
        df['type_display'] = df['type'].apply(lambda x: "Por Cobrar (Activo)" if x == 'Receivable' else "Por Pagar (Pasivo)")
    except: 
        df = pd.DataFrame()
    finally:
        conn.close()
    return df

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

def update_iou(iou_id, name, amount, iou_type, due_date, person_name, description, current_amount, status):
    """Actualiza una cuenta pendiente existente."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        # Nota: La columna 'amount' es el monto ORIGINAL, 'current_amount' es el saldo.
        cursor.execute("""
            UPDATE iou SET 
                name = ?, amount = ?, type = ?, due_date = ?, 
                person_name = ?, description = ?, current_amount = ?, status = ?
            WHERE id = ?
        """, (name, amount, iou_type, due_date, person_name, description, current_amount, status, iou_id))
        conn.commit()
        return True, "Cuenta pendiente actualizada exitosamente."
    except Exception as e:
        return False, f"Error al actualizar: {str(e)}"
    finally:
        conn.close()

# data_manager.py

def get_account_name_summary():
    """Calcula el saldo total agrupado por el NOMBRE que el usuario asignó a la cuenta (Ej. 'Ahorro', 'Billetera')."""
    conn = get_connection()
    try:
        query = """
            SELECT name, SUM(current_balance) as total_balance
            FROM accounts
            WHERE type IN ('Debit', 'Cash')
            GROUP BY name
            HAVING total_balance > 0
        """
        df = pd.read_sql_query(query, conn)
        return df
    except Exception as e:
        print(f"Error getting account name summary: {e}")
        return pd.DataFrame()
    finally:
        conn.close()

# data_manager.py - Colocar junto a add_transaction y get_transactions_df

def get_transaction_by_id(trans_id):
    conn = get_connection()
    try:
        df = pd.read_sql_query("""
            SELECT t.*, a.name as account_name FROM transactions t 
            LEFT JOIN accounts a ON t.account_id = a.id 
            WHERE t.id = ?
        """, conn, params=(trans_id,))
        if not df.empty:
            return df.iloc[0].to_dict()
        return None
    except:
        return None
    finally:
        conn.close()

def _adjust_account_balance(cursor, account_id, amount, trans_type, is_reversal=False):
    """Helper para sumar o restar un monto del balance de una cuenta."""
    
    cursor.execute("SELECT type FROM accounts WHERE id = ?", (account_id,))
    res = cursor.fetchone()
    acc_type = res[0] if res else "Debit"
    
    multiplier = -1 if is_reversal else 1
    
    if acc_type == 'Credit':
        # En Crédito: Gasto SUMA deuda. Ingreso RESTA deuda.
        if trans_type == 'Expense':
            new_amount = amount * multiplier
        else: # Income
            new_amount = amount * multiplier * -1 
    else: # Debit/Cash
        # En Débito: Gasto RESTA balance. Ingreso SUMA balance.
        if trans_type == 'Expense':
            new_amount = amount * multiplier * -1
        else: # Income
            new_amount = amount * multiplier
    
    cursor.execute("UPDATE accounts SET current_balance = current_balance + ? WHERE id = ?", (new_amount, account_id))

def delete_transaction(trans_id):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        trans = get_transaction_by_id(trans_id)
        if not trans: return False, "Transacción no encontrada."
        
        # 1. Reversar el balance en la cuenta original
        _adjust_account_balance(cursor, trans['account_id'], trans['amount'], trans['type'], is_reversal=True)
        
        # 2. Eliminar la transacción
        cursor.execute("DELETE FROM transactions WHERE id = ?", (trans_id,))
        conn.commit()
        return True, "Transacción eliminada y balance corregido."
    except Exception as e:
        conn.rollback()
        return False, f"Error al eliminar: {str(e)}"
    finally:
        conn.close()

def update_transaction(trans_id, new_date, new_name, new_amount, new_category, new_type, new_account_id):
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        old_trans = get_transaction_by_id(trans_id)
        if not old_trans: return False, "Transacción original no encontrada."

        # 1. REVERSAR balance en la cuenta ORIGINAL
        _adjust_account_balance(cursor, old_trans['account_id'], old_trans['amount'], old_trans['type'], is_reversal=True)
        
        # 2. ACTUALIZAR el registro de la transacción
        cursor.execute("""
            UPDATE transactions 
            SET date = ?, name = ?, amount = ?, category = ?, type = ?, account_id = ?
            WHERE id = ?
        """, (new_date, new_name, new_amount, new_category, new_type, new_account_id, trans_id))

        # 3. APLICAR NUEVO BALANCE a la nueva cuenta/monto
        _adjust_account_balance(cursor, new_account_id, new_amount, new_type, is_reversal=False)
        
        conn.commit()
        return True, "Transacción actualizada y balance corregido."
    except Exception as e:
        conn.rollback()
        return False, f"Error al actualizar: {str(e)}"
    finally:
        conn.close()

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
    """Obtiene el saldo de la reserva de abono para tarjetas de crédito (fuera de Patrimonio Neto)."""
    conn = get_connection()
    try:
        # Intenta leer la reserva. Si la tabla no existe, falla y retorna 0.0
        df = pd.read_sql_query("SELECT balance FROM abono_reserve WHERE id = 1", conn)
        return df['balance'].iloc[0] if not df.empty else 0.0
    except Exception:
        # En caso de error (probablemente la tabla no existe), inicializamos
        setup_abono_reserve() 
        return 0.0
    finally:
        conn.close()

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

def get_informal_summary():
    """
    Calcula el total de deudas informales (negativo) y cobros informales (positivo).
    Las cuentas informales son aquellas que no son de crédito, separadas por el signo de balance.
    Retorna: (total_debt_i, total_collectible_i) ambos como valores absolutos.
    """
    conn = get_connection()
    try:
        # Filtra todas las cuentas que NO son de Crédito (Tarjetas)
        df = pd.read_sql_query("SELECT current_balance FROM accounts WHERE type != 'Credit'", conn)
        
        if df.empty:
            return 0.0, 0.0

        # Deuda Informal (Saldos Negativos: lo que YO DEBO)
        informal_debt = df[df['current_balance'] < 0]['current_balance'].sum() 
        
        # Cobros Informales (Saldos Positivos: lo que ME DEBEN)
        informal_collectible = df[df['current_balance'] > 0]['current_balance'].sum()

        # Retornamos los valores absolutos
        return abs(informal_debt), informal_collectible 
        
    except Exception as e:
        print(f"Error getting informal summary: {e}")
        return 0.0, 0.0
    finally:
        conn.close()

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

def get_net_worth_breakdown():
    """
    Obtiene un desglose detallado del Patrimonio Neto:
    - Activos: Cuentas (Debit/Cash) + Cobros Informales (Receivables)
    - Pasivos: Deuda Tarjetas (Credit) + Deudas Informales (Payables)
    """
    conn = get_connection()
    details = {
        'net_worth': 0.0,
        'assets': {'total': 0.0, 'liquid': 0.0, 'receivables': 0.0},
        'liabilities': {'total': 0.0, 'credit_cards': 0.0, 'payables': 0.0}
    }
    try:
        # 1. Cuentas Bancarias y Crédito
        df_acc = pd.read_sql_query("SELECT type, current_balance FROM accounts", conn)
        
        liquid = df_acc[df_acc['type'].isin(['Debit', 'Cash'])]['current_balance'].sum()
        credit_debt = df_acc[df_acc['type'] == 'Credit']['current_balance'].sum()

        # 2. Deudas y Cobros Informales (IOU)
        df_iou = pd.read_sql_query("SELECT type, current_amount FROM iou WHERE status = 'Pending'", conn)
        
        receivables = 0.0
        payables = 0.0
        
        if not df_iou.empty:
            receivables = df_iou[df_iou['type'] == 'Receivable']['current_amount'].sum()
            payables = df_iou[df_iou['type'] == 'Payable']['current_amount'].sum()

        # 3. Consolidación
        total_assets = liquid + receivables
        total_liabilities = credit_debt + payables
        
        details['net_worth'] = total_assets - total_liabilities
        
        details['assets']['total'] = total_assets
        details['assets']['liquid'] = liquid
        details['assets']['receivables'] = receivables
        
        details['liabilities']['total'] = total_liabilities
        details['liabilities']['credit_cards'] = credit_debt
        details['liabilities']['payables'] = payables
        
    except Exception as e:
        print(f"Error calculating net worth breakdown: {e}")
    finally:
        conn.close()
    return details

# data_manager.py

# --- SUBCATEGORÍAS ---
def add_custom_subcategory(name, parent_category):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO subcategories (name, parent_category) VALUES (?, ?)", (name, parent_category))
        conn.commit()
        return True, "Subcategoría creada."
    except Exception as e:
        return False, str(e)
    finally:
        conn.close()

def get_subcategories_by_parent(parent_category):
    conn = get_connection()
    try:
        # Retorna lista de diccionarios [{'label': 'Netflix', 'value': 'Netflix'}, ...]
        df = pd.read_sql_query("SELECT name FROM subcategories WHERE parent_category = ?", conn, params=(parent_category,))
        return [{'label': row['name'], 'value': row['name']} for _, row in df.iterrows()]
    except:
        return []
    finally:
        conn.close()

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
    """Retorna las categorías principales para el dropdown."""
    conn = get_connection()
    try:
        df = pd.read_sql_query("SELECT name FROM categories ORDER BY name ASC", conn)
        return [{'label': row['name'], 'value': row['name']} for _, row in df.iterrows()]
    except: return []
    finally: conn.close()

def add_custom_category(name):
    """Crea una nueva categoría principal."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO categories (name) VALUES (?)", (name,))
        conn.commit()
        return True, f"Categoría '{name}' creada."
    except Exception as e: return False, str(e)
    finally: conn.close()


# backend/data_manager.p

# ... (otras funciones) ...

def get_historical_networth_trend(start_date=None, end_date=None):
    """
    Calcula el historial de Patrimonio Neto diario.
    Si no se dan fechas, calcula TODA la historia disponible.
    """
    conn = get_connection()
    try:
        # 1. Obtener Patrimonio Neto ACTUAL (HOY)
        current_nw = get_net_worth_breakdown()['net_worth']
        today = date.today()
        
        # 2. Obtener Transacciones
        df_trans = pd.read_sql_query("SELECT date, amount, type FROM transactions", conn)
        if df_trans.empty:
            return pd.DataFrame()
            
        df_trans['date'] = pd.to_datetime(df_trans['date']).dt.date
        
        # 3. Preparar Rango de Fechas
        # Si no hay start_date, usamos la primera transacción
        min_db_date = df_trans['date'].min()
        
        req_start = date.fromisoformat(start_date) if start_date else min_db_date
        req_end = date.fromisoformat(end_date) if end_date else today
        
        # Aseguramos que el cálculo cubra desde hoy hacia atrás hasta la fecha requerida
        calc_start = min(req_start, min_db_date)
        calc_end = max(req_end, today)
        
        # 4. Calcular Cambio Neto Diario (Ingresos - Gastos)
        # Agrupamos por día para no iterar transacción por transacción
        daily_changes = df_trans.groupby(['date', 'type'])['amount'].sum().unstack(fill_value=0)
        
        # Asegurar columnas
        if 'Income' not in daily_changes.columns: daily_changes['Income'] = 0
        if 'Expense' not in daily_changes.columns: daily_changes['Expense'] = 0
        
        daily_changes['net_change'] = daily_changes['Income'] - daily_changes['Expense']
        
        # 5. Reindexar para tener TODOS los días (incluso los que no hubo movimientos)
        full_idx = pd.date_range(start=calc_start, end=calc_end).date
        df_history = pd.DataFrame(index=full_idx)
        df_history.index.name = 'date'
        
        # Unimos con los cambios
        df_history = df_history.join(daily_changes['net_change']).fillna(0)
        
        # 6. Cálculo Retrospectivo (Vectorizado)
        # Ordenamos descendente (Hoy -> Pasado)
        df_history = df_history.sort_index(ascending=False)
        
        # La lógica es: NW_Ayer = NW_Hoy - Cambio_Hoy
        # Usamos cumsum() para acumular los cambios desde hoy hacia atrás
        # Nota: El cambio de HOY se resta para obtener el saldo de AYER al cierre.
        # Pero para graficar el saldo DE HOY, necesitamos el saldo actual.
        
        # Creamos una serie de "ajustes" acumulativos
        # shift(1) porque el cambio de hoy afecta al saldo de ayer, no al de hoy (si lo vemos como cierre)
        # Sin embargo, para simplificar: NW_Dia = NW_Actual - Acumulado_Cambios_Futuros
        
        cumulative_changes = df_history['net_change'].cumsum()
        
        # NW Histórico = NW Actual (Fijo) - Cambio Acumulado + Cambio del propio día (para incluirlo en el saldo del día)
        # Ajuste matemático: NW(t) = NW(today) - Sum(Changes from t+1 to today)
        
        # Manera simple: Restamos el acumulado al NW actual, pero sumamos el cambio del día actual 
        # porque el acumulado ya lo restó.
        df_history['net_worth'] = current_nw - cumulative_changes + df_history['net_change']
        
        # 7. Filtrar por el rango solicitado por el usuario
        df_history = df_history.sort_index() # Ordenar ascendente para el gráfico
        
        # Convertir índice a columna para filtrar
        df_history = df_history.reset_index()
        
        mask = (df_history['date'] >= req_start) & (df_history['date'] <= req_end)
        final_df = df_history.loc[mask]
        
        return final_df

    except Exception as e:
        print(f"Error history: {e}")
        return pd.DataFrame()
    finally:
        conn.close()

# backend/data_manager.py
# backend/data_manager.py

# ... (Tus imports anteriores) ...
import yfinance as yf

# --- GESTIÓN DE INVERSIONES (STOCKS) ---

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


def get_stocks_data():
    """
    Recupera todas las posiciones de inversión, obtiene precios en vivo de la API,
    y clasifica cada activo como STOCK, ETF, o CRYPTO_FOREX para el caché del frontend.
    """
    conn = get_connection()
    try:
        # Recuperamos TODAS las posiciones de la tabla investments
        df = pd.read_sql_query("SELECT * FROM investments ORDER BY display_order ASC", conn)
        if df.empty: 
            return []
        
        stocks_list = []
        for _, row in df.iterrows():
            ticker = row['ticker']
            shares = row['shares']
            avg_price = row['avg_price']
            
            # 1. LLAMADA API: Obtener datos en vivo y clasificación
            current_price, prev_close, name, sector = _get_price_finnhub(ticker, avg_price)
            
            # --- 2. CÁLCULO DE MÉTRICAS ---
            market_value = current_price * shares
            total_cost = avg_price * shares
            total_gain = market_value - total_cost
            total_gain_pct = ((current_price - avg_price) / avg_price * 100) if avg_price > 0 else 0
            
            day_change_pct = 0
            if prev_close > 0:
                day_change_pct = ((current_price - prev_close) / prev_close) * 100

            # --- 3. CLASIFICACIÓN FINAL DE ASSET_TYPE (Para la pestaña del frontend) ---
            asset_type_db = row['asset_type']
            final_asset_type = asset_type_db 
            
            # Regla A: Clasificación basada en el sector de Finnhub
            if sector in ['Exchange Traded Fund', 'Fund']:
                 final_asset_type = 'ETF'
            
            # Regla B: Chequeo manual para ETFs comunes
            elif ticker in ['SPY', 'QQQ', 'VOO', 'VT', 'BND', 'VTI', 'QTUM']: 
                 final_asset_type = 'ETF'
                 
            # Regla C: Clasificación CRYPTO/FOREX (Patrón de pares)
            elif 'USD' in ticker.upper() or 'USDT' in ticker.upper() or '/' in ticker:
                 final_asset_type = 'CRYPTO_FOREX'
                 
            # Regla D: Mantenemos el valor original de la BD si ya está clasificado
            elif asset_type_db == 'ETF':
                 final_asset_type = 'ETF'
            # (Si no coincide con nada, se asume 'Stock' por defecto de la BD)

            # --- 4. AJUSTE DEL CAMPO 'sector' (Para el gráfico de pastel) ---
            # Si clasificamos el activo como ETF o Crypto, sobreescribimos el sector para el gráfico.
            if final_asset_type == 'ETF':
                sector = 'Fondos (ETF)'
            elif final_asset_type == 'CRYPTO_FOREX':
                sector = 'Cripto/Forex'
            elif sector == 'N/A' or sector == '':
                # Si es un Stock pero el sector no se encontró, lo etiquetamos
                sector = 'Sin Clasificar' 

            # 5. CONSTRUCCIÓN DE LA LISTA DE STOCKS PARA EL CACHÉ
            stocks_list.append({
                'id': row['id'],
                'ticker': ticker,
                'name': name,
                'shares': shares,
                'avg_price': avg_price,
                'current_price': current_price,
                'market_value': market_value,
                'total_gain': total_gain,
                'total_gain_pct': total_gain_pct,
                'day_change_pct': day_change_pct,
                'sector': sector,           # <-- Usado para el gráfico de pastel (limpio)
                'asset_type': final_asset_type  # <-- Usado para el filtro de pestañas
            })
            
        return stocks_list
    
    except Exception as e:
        print(f"Error al obtener datos de stocks: {e}")
        return []
        
    finally:
        conn.close()

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


# backend/data_manager.py (Función add_stock MODIFICADA)

# La función debe aceptar total_investment como argumento
def add_stock(ticker, shares, total_investment, asset_type="Stock", account_id=None):
    conn = get_connection()
    cursor = conn.cursor()
    
    # 1. CÁLCULO CRÍTICO: avg_price = Inversión Total / Unidades
    avg_price = total_investment / shares if shares > 0 else 0.0
    
    try:
        cursor.execute("SELECT MAX(display_order) FROM investments")
        res = cursor.fetchone()
        max_order = res[0] if res[0] is not None else 0
        new_order = max_order + 1

        # 2. INSERTAR AMBOS VALORES (total_investment debe ser la nueva columna en la DB)
        # Nota: La lista de columnas INSERT debe coincidir con la lista de valores
        cursor.execute("""
            INSERT INTO investments (ticker, shares, avg_price, total_investment, asset_type, account_id, display_order)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (ticker, shares, avg_price, total_investment, asset_type, account_id, new_order))
        
        conn.commit()
        return True, f"Ticker {ticker} agregado. Costo Promedio: ${avg_price:,.2f}"
    except Exception as e:
        return False, f"Error al crear: {str(e)}"
    finally:
        conn.close()

# backend/data_manager.py

# backend/data_manager.py - Reemplazar la función get_investment_detail

def get_investment_detail(inv_id):
    """Detalle completo para el Modal usando Finnhub (Quote + Perfil + Métricas + Noticias)."""
    conn = get_connection()
    try:
        row = pd.read_sql_query("SELECT * FROM investments WHERE id = ?", conn, params=(inv_id,))
        if row.empty: return None
        
        data = row.iloc[0]
        ticker = data['ticker']
        shares = data['shares']
        avg_price = data['avg_price']
        
        clean_ticker = ticker.strip().upper()
        
        # 1. Obtener Cotización (Precio en tiempo real)
        try:
            quote = finnhub_client.quote(clean_ticker)
            current_price = float(quote.get('c', 0))
            prev_close = float(quote.get('pc', 0))
            day_high = float(quote.get('h', 0))
            day_low = float(quote.get('l', 0))
            
            if current_price == 0: current_price = avg_price
            if prev_close == 0: prev_close = avg_price
        except:
            current_price = avg_price
            prev_close = avg_price
            day_high = 0
            day_low = 0
        
        # 2. Obtener Perfil (Nombre, Logo, Sector)
        profile = {}
        try:
            profile = finnhub_client.company_profile2(symbol=clean_ticker)
        except: pass
        if not profile: profile = {}

        # 3. OBTENER MÉTRICAS FINANCIERAS (Rango 52 sem, P/E, Div)
        metrics = {}
        try:
            basic_fins = finnhub_client.company_basic_financials(clean_ticker, 'all')
            if 'metric' in basic_fins:
                metrics = basic_fins['metric']
        except: pass
        
        # 4. OBTENER NOTICIAS (NUEVO)
        news_list = []
        if finnhub_client:
            try:
                # Noticias (últimos 7 días, limitamos a 5 items para no saturar el modal)
                today = date.today().strftime('%Y-%m-%d')
                last_week = (date.today() - timedelta(days=7)).strftime('%Y-%m-%d')
                
                raw_news = finnhub_client.company_news(clean_ticker, _from=last_week, to=today)
                
                # Limitar y simplificar la lista de noticias
                news_list = [{
                    'headline': n.get('headline', 'N/A'),
                    'source': n.get('source', 'N/A'),
                    'url': n.get('url', '#')
                } for n in raw_news[:5]] # Tomamos solo las 5 más recientes
                
            except Exception as e:
                print(f"Error fetching news for {clean_ticker}: {e}")


        # Cálculos de Posición
        market_value = current_price * shares
        total_gain = market_value - (avg_price * shares)
        total_gain_pct = (total_gain / (avg_price * shares) * 100) if avg_price > 0 else 0
        
        day_change = current_price - prev_close
        day_change_pct = (day_change / prev_close * 100) if prev_close > 0 else 0

        # Mapeo final
        return {
            # Info Básica
            'name': profile.get('name', ticker),
            'ticker': profile.get('ticker', ticker),
            'sector': profile.get('finnhubIndustry', 'N/A'),
            'country': profile.get('country', 'N/A'),
            'logo_url': profile.get('logo', ''),
            'summary': f"Moneda: {profile.get('currency', 'USD')} | IPO: {profile.get('ipo', 'N/A')}",
            
            # Datos de Mercado (Métricas)
            'current_price': current_price,
            'day_high': day_high,
            'day_low': day_low,
            'fiftyTwo_high': metrics.get('52WeekHigh', 0),
            'fiftyTwo_low': metrics.get('52WeekLow', 0),
            'market_cap': metrics.get('marketCapitalization', 0),
            'pe_ratio': metrics.get('peTTM', 0),
            'dividend_yield': metrics.get('dividendYieldIndicatedAnnual', 0),
            'beta': metrics.get('beta', 0),

            # NUEVOS DATOS
            'news': news_list,

            
            # Tu Posición
            'shares': shares,
            'avg_price': avg_price,
            'market_value': market_value,
            'total_gain': total_gain,
            'total_gain_pct': total_gain_pct,
            'day_change': day_change,
            'day_change_pct': day_change_pct
        }
    except Exception as e:
        print(f"Error detail: {e}")
        return None
    finally:
        conn.close()


# backend/data_manager.py (Función update_investment - CORREGIDA)

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
    try:
        conn.execute("DELETE FROM investments WHERE id = ?", (inv_id,))
        conn.commit()
        return True, "Eliminado."
    except Exception as e: return False, str(e)
    finally: conn.close()

# backend/data_manager.py (NUEVA FUNCIÓN)

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
    """Registra una ganancia/pérdida realizada manualmente (ajuste inicial de historial)."""
    conn = get_connection()
    cursor = conn.cursor()
    date_recorded = date.today().strftime('%Y-%m-%d')
    
    try:
        cursor.execute("""
            INSERT INTO pl_adjustments (date, ticker, realized_pl, description)
            VALUES (?, ?, ?, ?)
        """, (date_recorded, ticker.upper(), realized_pl, "Ajuste manual (Pre-sistema)"))
        
        conn.commit()
        return True, f"Ajuste de P/L de {ticker.upper()} registrado."
        
    except Exception as e:
        conn.rollback()
        return False, f"Error DB al registrar ajuste: {str(e)}"
    finally:
        conn.close()

def get_pl_adjustments_df():
    """Obtiene todos los ajustes de P/L manuales."""
    conn = get_connection()
    try:
        df = pd.read_sql_query("SELECT ticker, realized_pl FROM pl_adjustments", conn)
        return df
    except Exception as e:
        print(f"Error fetching P/L adjustments: {e}")
        return pd.DataFrame({'ticker': [], 'realized_pl': []})
    finally:
        conn.close()

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
    """
    Anula una transacción de inversión (BUY o SELL):
    1. Obtiene los datos del trade (shares, price, type, ticker).
    2. Revierte el cambio en la posición de investments (shares y total_investment).
    3. Elimina el registro de la tabla investment_transactions.
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        # 1. Obtener datos del trade
        df_trade = pd.read_sql_query("SELECT * FROM investment_transactions WHERE id = ?", conn, params=(trade_id,))
        if df_trade.empty:
            return False, "Transacción no encontrada."
            
        trade = df_trade.iloc[0]
        ticker = trade['ticker']
        trade_type = trade['type']
        shares_delta = trade['shares']
        price = trade['price']
        
        # 2. Obtener datos actuales de la posición de investments
        pos = get_investment_by_ticker(ticker)
        if not pos:
            # El activo ya fue eliminado, solo borramos la transacción de historial
            cursor.execute("DELETE FROM investment_transactions WHERE id = ?", (trade_id,))
            conn.commit()
            return True, f"Transacción de {ticker} eliminada. El activo ya no estaba en el portafolio."


        shares_current = pos['shares']
        total_investment_current = pos['avg_price'] * shares_current
        
        # 3. Lógica de Reversión
        if trade_type == 'SELL':
            # Revertir Venta: Sumar acciones y sumar el costo original de esas acciones.
            new_shares = shares_current + shares_delta
            # El costo de las acciones vendidas es (shares_delta * avg_cost_at_trade)
            cost_restored = shares_delta * trade['avg_cost_at_trade']
            new_total_investment = total_investment_current + cost_restored
            
        elif trade_type == 'BUY':
            # Revertir Compra: Restar acciones y restar el costo de esa compra.
            new_shares = shares_current - shares_delta
            cost_removed = shares_delta * price # Costo de la compra original
            new_total_investment = total_investment_current - cost_removed
            
            if new_shares < -1e-6: # Pequeña tolerancia para errores de flotante
                 return False, "Error de balance: La anulación dejaría unidades negativas. Revisa el historial de trades."
        
        # 4. Calcular Nuevo Costo Promedio
        new_avg_price = new_total_investment / new_shares if new_shares > 0 else 0.0
        
        # 5. Actualizar DB (investments)
        cursor.execute("""
            UPDATE investments 
            SET shares = ?, avg_price = ?, total_investment = ?
            WHERE ticker = ?
        """, (new_shares, new_avg_price, new_total_investment, ticker))
        
        # 6. Eliminar el registro del historial
        cursor.execute("DELETE FROM investment_transactions WHERE id = ?", (trade_id,))
        
        conn.commit()
        return True, f"Transacción de {ticker} ({trade_type}) anulada y portafolio revertido."
        
    except Exception as e:
        conn.rollback()
        return False, f"Error al anular transacción: {str(e)}"
    finally:
        conn.close()

# backend/data_manager.py (Nuevas Funciones Requeridas)

def get_adjustment_id_by_ticker(ticker):
    """
    Obtiene el ID de un ajuste manual (asumiendo que solo hay uno por ticker para ajustes manuales).
    Devuelve None si no se encuentra.
    """
    conn = get_connection()
    try:
        # Buscamos el ID del ajuste manual para este ticker
        df = pd.read_sql_query("SELECT id, realized_pl FROM pl_adjustments WHERE ticker = ?", conn, params=(ticker,))
        if not df.empty:
            return df.iloc[0]['id'], df.iloc[0]['realized_pl']
        return None, None
    finally:
        conn.close()


def update_pl_adjustment(adjustment_id, new_pl_amount):
    """Actualiza el valor de un ajuste P/L existente."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            UPDATE pl_adjustments SET realized_pl = ? WHERE id = ?
        """, (new_pl_amount, adjustment_id))
        
        conn.commit()
        return True, "Ajuste de P/L corregido exitosamente."
    except Exception as e:
        conn.rollback()
        return False, f"Error DB al actualizar ajuste: {str(e)}"
    finally:
        conn.close()

# backend/data_manager.py (Nueva Función)
def get_total_realized_pl():
    """Calcula la suma total del P/L realizado de ventas y ajustes."""
    conn = get_connection()
    total_pl = 0.0
    try:
        # 1. Sumar P/L de Ventas (SELL)
        cursor = conn.cursor()
        cursor.execute("SELECT SUM(realized_pl) FROM investment_transactions WHERE type = 'SELL'")
        sales_pl = cursor.fetchone()[0] or 0.0
        
        # 2. Sumar P/L de Ajustes Manuales
        cursor.execute("SELECT SUM(realized_pl) FROM pl_adjustments")
        adjustments_pl = cursor.fetchone()[0] or 0.0
        
        total_pl = sales_pl + adjustments_pl
        return total_pl
    except Exception as e:
        print(f"Error calculating total realized PL: {e}")
        return 0.0
    finally:
        conn.close()


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
    """
    Registra una compra en investment_transactions y actualiza la posición en investments.
    """
    conn = get_connection()
    cursor = conn.cursor()
    date_bought = date.today().strftime('%Y-%m-%d')
    
    try:
        # 1. Obtener datos actuales de la posición
        cursor.execute("SELECT shares, avg_price, total_investment FROM investments WHERE ticker = ?", (ticker,))
        pos_data = cursor.fetchone()
        
        # Lógica de posición inexistente (se asume add_stock es la vía principal)
        if not pos_data or pos_data[0] == 0:
            total_investment = shares_bought * buy_price
            success, msg = add_stock(ticker, shares_bought, total_investment)
            # Después de la inserción inicial, el avg_cost es el buy_price
            avg_cost_at_trade = buy_price 
        else:
            shares_current, avg_cost_current, total_investment_current = pos_data
            
            # Cálculo de Nuevos Valores
            cost_new_shares = shares_bought * buy_price
            new_shares_total = shares_current + shares_bought
            new_total_investment = total_investment_current + cost_new_shares

            new_avg_price = new_total_investment / new_shares_total
            avg_cost_at_trade = new_avg_price # Registramos el nuevo promedio después de la compra
            
            # 2. Actualizar DB (investments)
            cursor.execute("""
                UPDATE investments 
                SET shares = ?, avg_price = ?, total_investment = ?
                WHERE ticker = ?
            """, (new_shares_total, new_avg_price, new_total_investment, ticker))
            
        # 3. Registrar en la tabla CONSOLIDADA (investment_transactions)
        total_transaction = shares_bought * buy_price
        cursor.execute("""
            INSERT INTO investment_transactions (date, ticker, type, shares, price, total_transaction, avg_cost_at_trade, realized_pl)
            VALUES (?, ?, 'BUY', ?, ?, ?, ?, 0.0)
        """, (date_bought, ticker, shares_bought, buy_price, total_transaction, avg_cost_at_trade))
        
        conn.commit()
        return True, f"Compra de {shares_bought} {ticker} registrada."
        
    except Exception as e:
        conn.rollback()
        return False, f"Error DB al registrar compra: {str(e)}"
    finally:
        conn.close()


def add_sale(ticker, shares_sold, sale_price):
    """
    Registra una venta en investment_transactions, calcula P/L y actualiza la posición.
    """
    conn = get_connection()
    cursor = conn.cursor()
    date_sold = date.today().strftime('%Y-%m-%d')
    
    try:
        # 1. Obtener datos de la posición
        pos = get_investment_by_ticker(ticker)
        if not pos or pos['shares'] < shares_sold:
            return False, "Error: Unidades insuficientes."
            
        avg_cost = pos['avg_price']
        
        # 2. Calcular P/L Realizada
        realized_pl = (sale_price - avg_cost) * shares_sold
        total_transaction = shares_sold * sale_price
        
        # 3. Registrar en la tabla CONSOLIDADA (investment_transactions)
        cursor.execute("""
            INSERT INTO investment_transactions (date, ticker, type, shares, price, total_transaction, avg_cost_at_trade, realized_pl)
            VALUES (?, ?, 'SELL', ?, ?, ?, ?, ?)
        """, (date_sold, ticker, shares_sold, sale_price, total_transaction, avg_cost, realized_pl))
        
        # 4. Actualizar unidades restantes en 'investments'
        new_shares = pos['shares'] - shares_sold
        new_total_investment = pos['avg_price'] * new_shares # Si las shares bajan, el total investment baja proporcionalmente
        
        cursor.execute("""
            UPDATE investments SET shares = ?, total_investment = ? WHERE ticker = ?
        """, (new_shares, new_total_investment, ticker))
        
        conn.commit()
        return True, f"Venta de {shares_sold} {ticker} registrada. P&L: ${realized_pl:,.2f}"
        
    except Exception as e:
        conn.rollback()
        return False, f"Error DB al registrar venta: {str(e)}"
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
    """Obtiene el historial completo de transacciones de inversión (Compra/Venta)."""
    conn = get_connection()
    try:
        if transaction_type in ['BUY', 'SELL']:
             query = "SELECT * FROM investment_transactions WHERE type = ? ORDER BY date DESC, id DESC"
             params = (transaction_type,)
        else:
            query = "SELECT * FROM investment_transactions ORDER BY date DESC, id DESC"
            params = ()
            
        df = pd.read_sql_query(query, conn, params=params)
        df['date'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d')
        return df
    except Exception as e:
        print(f"Error fetching investment transactions: {e}")
        return pd.DataFrame()
    finally:
        conn.close()
       
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