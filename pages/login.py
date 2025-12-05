# pages/login.py
import dash
from dash import html, dcc, callback, Input, Output, State
import dash_bootstrap_components as dbc
from flask_login import login_user, current_user
from backend.models import verify_user

# Layout de la página de Login
layout = dbc.Container([
    dbc.Row([
        dbc.Col(
            dbc.Card([
                dbc.CardHeader("Bienvenido a Pívot", className="text-center fw-bold text-white bg-primary"),
                dbc.CardBody([
                    html.Div(className="text-center mb-4", children=[
                        html.I(className="bi bi-shield-lock-fill", style={"fontSize": "3rem", "color": "#2A9FD6"})
                    ]),
                    
                    dbc.Label("Usuario"),
                    dbc.Input(id="login-username", type="text", placeholder="Ej: admin", className="mb-3"),
                    
                    dbc.Label("Contraseña"),
                    dbc.Input(id="login-password", type="password", placeholder="••••••", className="mb-3"),
                    
                    dbc.Button("Iniciar Sesión", id="btn-login", color="primary", className="w-100 fw-bold"),

                    html.Div([
                        html.Span("¿Nuevo en Pívot? "),
                        dcc.Link("Crea una cuenta", href="/register", className="fw-bold text-success")
                    ], className="text-center mt-3 small"),
                    
                    html.Div(id="login-alert", className="mt-3 text-center")
                ])
            ], className="shadow-lg border-0", style={"maxWidth": "400px", "margin": "0 auto"}), # Centrado
            width=12,
            className="d-flex justify-content-center align-items-center",
            style={"height": "100vh"} # Ocupa toda la altura de la pantalla
        )
    ])
], fluid=True)

# Callback para procesar el login
@callback(
    [Output("url", "pathname", allow_duplicate=True),
     Output("login-alert", "children")],
    Input("btn-login", "n_clicks"),
    [State("login-username", "value"),
     State("login-password", "value")],
    prevent_initial_call=True
)
def login_process(n_clicks, username, password):
    if not n_clicks:
        return dash.no_update, ""
    
    if not username or not password:
        return dash.no_update, html.Span("Por favor ingresa usuario y contraseña.", className="text-warning")

    # --- CORRECCIÓN AQUÍ: NORMALIZACIÓN DE INPUTS ---
    # 1. Usuario: Quitamos espacios y convertimos a minúsculas (igual que en registro)
    clean_user = username.strip().lower()
    
    # 2. Contraseña: Solo quitamos espacios laterales (respetamos mayúsculas intermedias)
    clean_pass = password.strip()

    # Verificar credenciales usando los datos limpios
    user = verify_user(clean_user, clean_pass)
    
    if user:
        login_user(user) # Esto crea la sesión segura en Flask
        return "/", ""   # Redirige al Dashboard
    else:
        return dash.no_update, html.Span("Usuario o contraseña incorrectos.", className="text-danger fw-bold")