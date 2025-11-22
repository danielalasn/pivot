import dash
import dash_bootstrap_components as dbc

# --- En app.py ---

# Asegúrate de importar Bootstrap Icons (BI)
BOOTSTRAP_ICONS = "https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css"

# Usamos dash-bootstrap-components para un diseño moderno y responsivo.
app = dash.Dash(
    __name__,
    # Añadimos BOOTSTRAP_ICONS a la lista de hojas de estilo
    external_stylesheets=[dbc.themes.CYBORG, BOOTSTRAP_ICONS],
    suppress_callback_exceptions=True,
    meta_tags=[
        {"name": "viewport", "content": "width=device-width, initial-scale=1.0"}
    ],
)

# Referencia al servidor para despliegue (ej. Gunicorn)
server = app.server

app.title = "Pívot Finance"