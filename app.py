# app.py
import dash
import dash_bootstrap_components as dbc
from flask_login import LoginManager
from backend.models import get_user_by_id
import os
from datetime import timedelta
from dotenv import load_dotenv # <--- 1. Importar librería
from backend.extensions import cache

# 2. Cargar variables de entorno al inicio
load_dotenv()

BOOTSTRAP_ICONS = "https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css"

app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.CYBORG, BOOTSTRAP_ICONS],
    suppress_callback_exceptions=True,
    meta_tags=[
        {"name": "viewport", "content": "width=device-width, initial-scale=1.0"}
    ],
)

app.title = "Pívot"

server = app.server

cache.init_app(server, config={
    'CACHE_TYPE': 'SimpleCache',
    'CACHE_DEFAULT_TIMEOUT': 300
})

# --- CONFIGURACIÓN DE SEGURIDAD (MEJORADA) ---
# 3. Leemos desde el .env. 
# El segundo parámetro es un "fallback" por si no encuentra la variable en el .env
secret_key = os.getenv("FLASK_SECRET_KEY")

# 2. Validación CRÍTICA: Si no hay clave, detener la aplicación
if not secret_key:
    raise RuntimeError("ERROR CRÍTICO: No se encontró 'FLASK_SECRET_KEY' en el archivo .env. Por seguridad, la app no iniciará.")

# 3. Configurar el servidor
server.config.update(
    SECRET_KEY=secret_key,
    REMEMBER_COOKIE_DURATION=timedelta(days=7)
)

login_manager = LoginManager()
login_manager.init_app(server)
login_manager.login_view = '/login'

from backend.models import get_user_by_id
@login_manager.user_loader
def load_user(user_id):
    return get_user_by_id(user_id)