# backend/models.py
from flask_login import UserMixin
from werkzeug.security import check_password_hash
from backend.database import get_connection

class User(UserMixin):
    def __init__(self, id, username, email):
        self.id = id
        self.username = username
        self.email = email

def get_user_by_id(user_id):
    """Busca un usuario por ID (Para mantener la sesión activa)."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id, username, email FROM users WHERE id = ?", (user_id,))
        user_data = cursor.fetchone()
        if user_data:
            return User(id=user_data[0], username=user_data[1], email=user_data[2])
    finally:
        conn.close()
    return None

def verify_user(username, password):
    """Verifica usuario y contraseña para el Login."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id, username, email, password_hash FROM users WHERE username = ?", (username,))
        user_data = cursor.fetchone()
        
        if user_data:
            # user_data = (id, username, email, password_hash)
            stored_hash = user_data[3]
            if check_password_hash(stored_hash, password):
                return User(id=user_data[0], username=user_data[1], email=user_data[2])
    finally:
        conn.close()
    return None