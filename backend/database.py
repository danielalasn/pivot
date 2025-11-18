import sqlite3
import os

# Define la ruta de la base de datos
DB_DIR = "data"
DB_PATH = os.path.join(DB_DIR, "pivot.db")

def init_db():
    """
    Inicializa la base de datos SQLite y crea las tablas
    necesarias si no existen.
    """
    # Asegura que el directorio 'data' exista
    os.makedirs(DB_DIR, exist_ok=True)
    
    print(f"Inicializando base de datos en: {DB_PATH}")
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # --- Creación de Tablas ---

    # 1. Cuentas (Accounts)
    # 'type' puede ser: 'Debit', 'Credit', 'Savings', 'Investment'
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS accounts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        type TEXT NOT NULL,
        current_balance REAL DEFAULT 0.0
    );
    """)

    # 2. Transacciones (Transactions)
    # 'category': 'Costos Fijos', 'Guilt Free', 'Investments', 'Savings'
    # 'type': 'Income' (Ingreso) o 'Expense' (Gasto)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL,
        name TEXT NOT NULL,
        amount REAL NOT NULL,
        category TEXT NOT NULL,
        type TEXT NOT NULL,
        account_id INTEGER,
        FOREIGN KEY (account_id) REFERENCES accounts (id)
    );
    """)

    # 3. Metas (Goals)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS goals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        target_amount REAL NOT NULL,
        target_date TEXT NOT NULL,
        current_amount REAL DEFAULT 0.0
    );
    """)

    # 4. Inversiones (Investment Positions)
    # 'asset_type': 'Stock', 'Crypto'
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS investments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ticker TEXT NOT NULL,
        shares REAL NOT NULL,
        avg_price REAL NOT NULL,
        asset_type TEXT NOT NULL,
        account_id INTEGER,
        FOREIGN KEY (account_id) REFERENCES accounts (id)
    );
    """)

    conn.commit()
    conn.close()
    print("Base de datos inicializada con éxito.")

if __name__ == "__main__":
    # Permite ejecutar este script directamente para crear la DB
    # python backend/database.py
    init_db()