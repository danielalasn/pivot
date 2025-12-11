from flask_login import UserMixin
from werkzeug.security import check_password_hash
from backend.data_manager import get_connection

class User(UserMixin):
    def __init__(self, id, username, email, display_name):
        self.id = str(id)
        self.username = username
        self.email = email
        self.display_name = display_name

def verify_user(username, password):
    """
    Busca el usuario por username y verifica el hash del password.
    """
    conn = get_connection()
    # Usamos cursor() para aprovechar el Wrapper que convierte ? a %s si es necesario
    cursor = conn.cursor()
    
    try:
        # 1. Buscar usuario en la DB
        # Es vital seleccionar el campo 'password_hash'
        cursor.execute("""
            SELECT id, username, email, display_name, password_hash 
            FROM users 
            WHERE username = ?
        """, (username,))
        
        data = cursor.fetchone()

        if not data:
            return None # Usuario no encontrado

        # Desempaquetar los datos (El orden coincide con el SELECT: 0, 1, 2, 3, 4)
        uid = data[0]
        u_name = data[1]
        email = data[2]
        display = data[3]
        stored_hash = data[4]

        # 2. Verificar Contraseña
        if stored_hash and check_password_hash(stored_hash, password):
            return User(uid, u_name, email, display)
        
        return None # Contraseña incorrecta

    except Exception as e:
        print(f"❌ Error en verify_user: {e}")
        return None
    finally:
        conn.close()

def get_user_by_id(user_id):
    """Necesario para Flask-Login (load_user)."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT id, username, email, display_name 
            FROM users 
            WHERE id = ?
        """, (user_id,))
        data = cursor.fetchone()
        
        if data:
            # Retornamos el objeto User usando los índices de la tupla
            return User(data[0], data[1], data[2], data[3])
        return None
    except:
        return None
    finally:
        conn.close()