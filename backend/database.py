# database.py
import sqlite3
import os
from werkzeug.security import generate_password_hash

DB_DIR = "data"
DB_PATH = os.path.join(DB_DIR, "pivot.db")

def get_connection():
    return sqlite3.connect(DB_PATH)

def ensure_db_structure():
    if not os.path.exists(DB_DIR):
        os.makedirs(DB_DIR)
    
    print(f"Asegurando estructura DB en: {DB_PATH}")
    conn = get_connection()
    cursor = conn.cursor()

    # ==========================================
    # 1. TABLA DE USUARIOS (NUEVO)
    # ==========================================
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL,
        email TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # --- CREAR USUARIO ADMIN POR DEFECTO ---
    # Si no hay usuarios, creamos al admin dueño de todo
    cursor.execute("SELECT count(*) FROM users")
    if cursor.fetchone()[0] == 0:
        # Contraseña temporal: "admin123" (La cambiaremos luego)
        # Usamos un hash real para seguridad desde el principio
        default_pass = generate_password_hash("admin123", method='pbkdf2:sha256')
        cursor.execute(
            "INSERT INTO users (id, username, password_hash, email) VALUES (?, ?, ?, ?)", 
            (1, "admin", default_pass, "admin@pivot.app")
        )
        print("✅ Usuario 'admin' creado por defecto (ID: 1).")
        print("ℹ️  Password temporal: 'admin123'")

    # ==========================================
    # 2. DEFINICIÓN DE TABLAS (Con user_id)
    # ==========================================
    
    # NOTA: En SQLite, si la tabla ya existe, CREATE TABLE IF NOT EXISTS no hace nada.
    # Por eso, la "magia" de añadir user_id la haremos en el paso de migración más abajo.
    # Aquí definimos las tablas para instalaciones NUEVAS desde cero.

    # 1. Cuentas
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS accounts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER DEFAULT 1, -- NUEVO
        name TEXT NOT NULL,
        type TEXT NOT NULL,
        current_balance REAL DEFAULT 0.0,
        bank_name TEXT,
        credit_limit REAL DEFAULT 0.0,
        payment_day INTEGER,
        cutoff_day INTEGER,
        interest_rate REAL DEFAULT 0.0,
        display_order INTEGER DEFAULT 0,
        deferred_balance REAL DEFAULT 0.0,
        FOREIGN KEY (user_id) REFERENCES users (id)
    );""")

    # 2. Transacciones
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER DEFAULT 1, -- NUEVO
        date TEXT NOT NULL,
        name TEXT NOT NULL,
        amount REAL NOT NULL,
        category TEXT NOT NULL,
        type TEXT NOT NULL,
        account_id INTEGER,
        subcategory TEXT,
        FOREIGN KEY (account_id) REFERENCES accounts (id),
        FOREIGN KEY (user_id) REFERENCES users (id)
    );""")

    # 3. Metas
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS goals (
        id INTEGER PRIMARY KEY AUTOINCREMENT, 
        user_id INTEGER DEFAULT 1,
        name TEXT, 
        target_amount REAL, 
        target_date TEXT, 
        current_amount REAL DEFAULT 0
    );""")
    
    # 4. Inversiones (Portafolio)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS investments (
        id INTEGER PRIMARY KEY AUTOINCREMENT, 
        user_id INTEGER DEFAULT 1,
        ticker TEXT, 
        shares REAL, 
        avg_price REAL, 
        asset_type TEXT, 
        account_id INTEGER, 
        total_investment REAL DEFAULT 0.0, 
        display_order INTEGER DEFAULT 0
    );""")
    
    # 5. Financiamientos (Cuotas)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS installments (
        id INTEGER PRIMARY KEY AUTOINCREMENT, 
        user_id INTEGER DEFAULT 1,
        account_id INTEGER, 
        name TEXT, 
        total_amount REAL, 
        interest_rate REAL, 
        total_quotas INTEGER, 
        paid_quotas INTEGER, 
        payment_day INTEGER
    );""")

    # 6. IOU (Deudas Informales)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS iou (
        id INTEGER PRIMARY KEY AUTOINCREMENT, 
        user_id INTEGER DEFAULT 1,
        name TEXT, 
        amount REAL, 
        type TEXT, 
        current_amount REAL, 
        date_created TEXT, 
        due_date TEXT, 
        status TEXT, 
        person_name TEXT, 
        description TEXT
    );""")

    # 7. Subcategorías
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS subcategories (
        id INTEGER PRIMARY KEY AUTOINCREMENT, 
        user_id INTEGER DEFAULT 1,
        name TEXT NOT NULL, 
        parent_category TEXT NOT NULL
    );""")

    # 8. Categorías Principales
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS categories (
        id INTEGER PRIMARY KEY AUTOINCREMENT, 
        user_id INTEGER DEFAULT 1,
        name TEXT NOT NULL
    );""")

    # 9. Historial de Patrimonio
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS history_snapshots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER DEFAULT 1,
        date TEXT NOT NULL,
        net_worth REAL NOT NULL,
        difference REAL DEFAULT 0.0,
        period_type TEXT
    );
    """)

    # 10. Historial de Transacciones de Inversión (Compras/Ventas)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS investment_transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER DEFAULT 1,
        date TEXT NOT NULL,
        ticker TEXT NOT NULL,
        type TEXT NOT NULL,          -- 'BUY' o 'SELL'
        shares REAL NOT NULL,        
        price REAL NOT NULL,         
        total_transaction REAL NOT NULL, 
        avg_cost_at_trade REAL DEFAULT 0.0, 
        realized_pl REAL DEFAULT 0.0 
    );
    """)

    # 11. Ajustes manuales de P/L
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS pl_adjustments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER DEFAULT 1,
        date TEXT NOT NULL,
        ticker TEXT NOT NULL,
        realized_pl REAL NOT NULL, 
        description TEXT
    );
    """)

    # 12. Reserva de Abono
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS abono_reserve (
        id INTEGER PRIMARY KEY,
        user_id INTEGER DEFAULT 1,
        balance REAL DEFAULT 0.0
    );""")

    # 13. CACHÉ DE MERCADO (GLOBAL - NO LLEVA USER_ID)
    # Esta tabla es compartida porque los precios de AAPL son iguales para todos.
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS market_cache (
        ticker TEXT PRIMARY KEY,
        company_name TEXT,
        price REAL, day_change REAL, day_change_pct REAL,
        day_high REAL, day_low REAL, fiftyTwo_high REAL, fiftyTwo_low REAL,
        market_cap REAL, shares_outstanding REAL, pe_ratio REAL, peg_ratio REAL, 
        dividend_yield REAL, beta REAL, sector TEXT, country TEXT, summary TEXT,
        news TEXT, sentiment TEXT,
        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    conn.commit()

    # =========================================================
    # 3. MIGRACIÓN: AGREGAR user_id A TABLAS EXISTENTES
    # =========================================================
    # Esta sección actualiza tu base de datos actual sin borrar nada.
    
    tables_to_migrate = [
        'accounts', 'transactions', 'goals', 'investments', 'installments', 
        'iou', 'subcategories', 'categories', 'history_snapshots', 
        'investment_transactions', 'pl_adjustments', 'abono_reserve'
    ]

    print("--- Verificando Migración de Tablas ---")
    for table in tables_to_migrate:
        try:
            # Verificar si la columna existe
            cursor.execute(f"PRAGMA table_info({table})")
            columns = [info[1] for info in cursor.fetchall()]
            
            if 'user_id' not in columns:
                print(f"🔄 Migrando tabla '{table}': Agregando user_id...")
                # Añadimos la columna y ponemos por defecto 1 (el Admin)
                cursor.execute(f"ALTER TABLE {table} ADD COLUMN user_id INTEGER DEFAULT 1 REFERENCES users(id)")
                
                # Aseguramos que los datos viejos sean del admin
                cursor.execute(f"UPDATE {table} SET user_id = 1 WHERE user_id IS NULL")
                conn.commit()
            else:
                pass 
                # print(f"✓ Tabla '{table}' ya tiene user_id.")
        except Exception as e:
            print(f"⚠️ Alerta en tabla {table}: {e}")

    # ==========================================
    # 4. DATOS POR DEFECTO (Categorías)
    # ==========================================
    # Insertar categorías default para el admin si no tiene
    cursor.execute("SELECT count(*) FROM categories WHERE user_id = 1")
    if cursor.fetchone()[0] == 0:
        defaults = [
            ('Costos Fijos', 1), ('Libres (Guilt Free)', 1), ('Inversión', 1), 
            ('Ahorro', 1), ('Deudas/Cobros', 1), ('Ingresos', 1)
        ]
        cursor.executemany("INSERT INTO categories (name, user_id) VALUES (?, ?)", defaults)
        print("Categorías por defecto insertadas para Admin.")

    conn.commit()
    conn.close()
    print("Base de datos lista y migrada a Multi-Usuario.")

if __name__ == "__main__":
    ensure_db_structure()