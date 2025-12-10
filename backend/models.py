# backend/models.py
import sqlite3
from flask_login import UserMixin
from werkzeug.security import check_password_hash # <--- Faltaba esta importación importante
from backend.data_manager import DB_PATH

class User(UserMixin):
    def __init__(self, id, username, email, display_name=None):
        self.id = str(id)
        self.username = username
        self.email = email
        # Si no hay display_name, usamos el username como fallback
        self.display_name = display_name if display_name else username

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def get_user_by_id(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    # Seleccionamos id, username, email y display_name
    cursor.execute("SELECT id, username, email, display_name FROM users WHERE id = ?", (user_id,))
    user_data = cursor.fetchone()
    conn.close()

    if user_data:
        return User(
            id=user_data['id'], 
            username=user_data['username'], 
            email=user_data['email'],
            display_name=user_data['display_name']
        )
    return None

def get_user_by_username(username):
    conn = get_db_connection()
    cursor = conn.cursor()
    # Seleccionamos también password_hash para poder verificar el login
    cursor.execute("SELECT id, username, email, password_hash, display_name FROM users WHERE username = ?", (username,))
    user_data = cursor.fetchone()
    conn.close()

    if user_data:
        user = User(
            id=user_data['id'], 
            username=user_data['username'], 
            email=user_data['email'],
            display_name=user_data['display_name']
        )
        # Guardamos el hash temporalmente en el objeto para usarlo en verify_user
        user.password_hash = user_data['password_hash']
        return user
    return None

# --- ESTA ES LA FUNCIÓN QUE FALTABA ---
def verify_user(username, password):
    user = get_user_by_username(username)
    if user and check_password_hash(user.password_hash, password):
        return user
    return None