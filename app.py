import dash
import dash_bootstrap_components as dbc

# ------------------------------------------------------------------------------
# INICIALIZACIÓN DE LA APP
# ------------------------------------------------------------------------------
# Usamos dash-bootstrap-components para un diseño moderno y responsivo.
# El tema 'CYBORG' es un excelente punto de partida para tu 'dark theme'.
# 'external_stylesheets' carga el tema y permite que 'assets/style.css' lo sobrescriba.
app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.CYBORG],
    suppress_callback_exceptions=True,
    meta_tags=[
        {"name": "viewport", "content": "width=device-width, initial-scale=1.0"}
    ],
)

# Referencia al servidor para despliegue (ej. Gunicorn)
server = app.server

app.title = "Pívot Finance"