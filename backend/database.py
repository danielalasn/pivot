# database.py
import sqlite3
import os

DB_DIR = "data"
DB_PATH = os.path.join(DB_DIR, "pivot.db")

def ensure_db_structure():
    if not os.path.exists(DB_DIR):
        os.makedirs(DB_DIR)
    
    print(f"Asegurando estructura DB en: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        cursor.execute("ALTER TABLE investments ADD COLUMN total_investment REAL DEFAULT 0.0;")
        print("Migración: Columna 'total_investment' agregada a investments.")
    except: pass
    # 1. Cuentas
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS accounts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        type TEXT NOT NULL,
        current_balance REAL DEFAULT 0.0,
        bank_name TEXT,
        credit_limit REAL DEFAULT 0.0,
        payment_day INTEGER,
        cutoff_day INTEGER,
        interest_rate REAL DEFAULT 0.0,
        display_order INTEGER DEFAULT 0,
        deferred_balance REAL DEFAULT 0.0 
    );""")

    # 2. Transacciones
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL,
        name TEXT NOT NULL, -- Ahora se usará para "Detalle"
        amount REAL NOT NULL,
        category TEXT NOT NULL,
        type TEXT NOT NULL,
        account_id INTEGER,
        subcategory TEXT,
        FOREIGN KEY (account_id) REFERENCES accounts (id)
    );""")

    # 3. Metas
    cursor.execute("CREATE TABLE IF NOT EXISTS goals (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, target_amount REAL, target_date TEXT, current_amount REAL DEFAULT 0);")
    
    # 4. Inversiones
    cursor.execute("CREATE TABLE IF NOT EXISTS investments (id INTEGER PRIMARY KEY AUTOINCREMENT, ticker TEXT, shares REAL, avg_price REAL, asset_type TEXT, account_id INTEGER);")
    
    # 5. Financiamientos
    cursor.execute("CREATE TABLE IF NOT EXISTS installments (id INTEGER PRIMARY KEY AUTOINCREMENT, account_id INTEGER, name TEXT, total_amount REAL, interest_rate REAL, total_quotas INTEGER, paid_quotas INTEGER, payment_day INTEGER);")

    # 6. IOU
    cursor.execute("CREATE TABLE IF NOT EXISTS iou (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, amount REAL, type TEXT, current_amount REAL, date_created TEXT, due_date TEXT, status TEXT, person_name TEXT, description TEXT);")

    # 7. Subcategorías
    cursor.execute("CREATE TABLE IF NOT EXISTS subcategories (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, parent_category TEXT NOT NULL);")

    # 8. CATEGORÍAS PRINCIPALES (NUEVO)
    cursor.execute("CREATE TABLE IF NOT EXISTS categories (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE);")

    # --- DATOS POR DEFECTO ---
    # Insertar categorías default si la tabla está vacía
    cursor.execute("SELECT count(*) FROM categories")
    if cursor.fetchone()[0] == 0:
        defaults = [('Costos Fijos',), ('Libres (Guilt Free)',), ('Inversión',), ('Ahorro',), ('Deudas/Cobros',), ('Ingresos',)]
        cursor.executemany("INSERT OR IGNORE INTO categories (name) VALUES (?)", defaults)
        print("Categorías por defecto insertadas.")

    # database.py - Agregar esto dentro de ensure_db_structure()

    # ... (tablas anteriores) ...

    # 9. HISTORIAL DE PATRIMONIO (SNAPSHOTS)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS history_snapshots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL,
        net_worth REAL NOT NULL,
        difference REAL DEFAULT 0.0, -- Cambio respecto al periodo anterior
        period_type TEXT -- 'Q1' (Quincena 1) o 'Q2' (Fin de mes)
    );
    """)

    # database.py

    # ... (código anterior) ...

    # Migración C: Columna 'display_order' en Investments
    try:
        cursor.execute("ALTER TABLE investments ADD COLUMN display_order INTEGER DEFAULT 0;")
        print("Migración: Columna 'display_order' agregada a investments.")
    except: pass 

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS history_snapshots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL,
        net_worth REAL NOT NULL,
        difference REAL DEFAULT 0.0,
        period_type TEXT
    );
    """)

# 🚨 NUEVA TABLA CONSOLIDADA para COMPRAS y VENTAS
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS investment_transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL,
        ticker TEXT NOT NULL,
        type TEXT NOT NULL,          -- 'BUY' o 'SELL'
        shares REAL NOT NULL,        -- Cantidad de unidades
        price REAL NOT NULL,         -- Precio de ejecución (por unidad)
        total_transaction REAL NOT NULL, -- shares * price
        avg_cost_at_trade REAL DEFAULT 0.0, -- Costo promedio en el momento del trade (solo para cálculo de P/L en VENTA)
        realized_pl REAL DEFAULT 0.0 -- P/L Realizado (SOLO EN VENTAS)
    );
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pl_adjustments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            ticker TEXT NOT NULL,
            realized_pl REAL NOT NULL, -- Ganancia (positivo) o Pérdida (negativo)
            description TEXT -- Para saber si fue ajuste manual
        );
        """)
    
    # ... (otras tablas) ...

    # 10. CACHÉ DE PRECIOS DE MERCADO (NUEVO)
    # Guarda el último precio conocido para no llamar a la API constantemente
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS market_cache (
        ticker TEXT PRIMARY KEY,
        price REAL NOT NULL,
        prev_close REAL DEFAULT 0.0,
        company_name TEXT,
        sector TEXT,
        last_updated TEXT NOT NULL
    );
    """)
    
    print("Tabla 'market_cache' verificada.")

    # 🚨 LIMPIEZA: Eliminar la tabla antigua si existe
    try:
        cursor.execute("DROP TABLE IF EXISTS sales_history;")
        print("Limpieza: Tabla 'sales_history' eliminada.")
    except:
        pass

    conn.commit()
    # ...
    # ...
    conn.close()
    print("Base de datos lista.")

if __name__ == "__main__":
    ensure_db_structure()