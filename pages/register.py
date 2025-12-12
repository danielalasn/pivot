# pages/register.py
import dash
from dash import html, dcc, callback, Input, Output, State
import dash_bootstrap_components as dbc
import backend.data_manager as dm

# --- DEFINICIÓN DEL LAYOUT ---
layout = dbc.Container([
    dbc.Row([
        dbc.Col(
            dbc.Card([
                dbc.CardHeader("Crear Cuenta Nueva", className="text-center fw-bold text-white bg-success"),
                dbc.CardBody([
                    html.Div(className="text-center mb-4", children=[
                        html.I(className="bi bi-person-plus-fill", style={"fontSize": "3rem", "color": "#28a745"})
                    ]),
                    
                    dbc.Label("Nombre de Usuario"),
                    dbc.Input(id="reg-username", type="text", placeholder="Elige tu usuario", className="mb-3"),
                    
                    dbc.Label("Correo Electrónico"),
                    dbc.Input(id="reg-email", type="email", placeholder="tu@email.com", className="mb-3"),
                    
                    dbc.Label("Contraseña"),
                    dbc.Input(id="reg-password", type="password", placeholder="••••••", className="mb-3"),

                    # --- NUEVO CAMPO: CONFIRMAR CONTRASEÑA ---
                    dbc.Label("Confirmar Contraseña"),
                    dbc.Input(id="reg-password-confirm", type="password", placeholder="Repite la contraseña", className="mb-3"),
                    
                    dbc.Button("Registrarse", id="btn-register", color="success", className="w-100 fw-bold mb-3"),
                    
                    # Enlace para volver al Login
                    html.Div([
                        html.Span("¿Ya tienes cuenta? "),
                        dcc.Link("Inicia Sesión aquí", href="/login", className="fw-bold text-info")
                    ], className="text-center small"),
                    
                    html.Div(id="register-alert", className="mt-3 text-center")
                ])
            ], className="shadow-lg border-0", style={"maxWidth": "400px", "margin": "0 auto"}),
            width=12,
            className="d-flex justify-content-center align-items-center",
            style={"height": "100vh"}
        )
    ])
], fluid=True)

# --- CALLBACKS ---
@callback(
    [Output("register-alert", "children"),
     Output("reg-username", "value"),
     Output("reg-password", "value"),
     Output("reg-password-confirm", "value"), # Salida para limpiar el campo de confirmación
     Output("reg-email", "value")],
    Input("btn-register", "n_clicks"),
    [State("reg-username", "value"),
     State("reg-password", "value"),
     State("reg-password-confirm", "value"), # Estado del campo de confirmación
     State("reg-email", "value")],
    prevent_initial_call=True
)
def register_process(n_clicks, username, password, password_confirm, email):
    # Definimos el valor de no_update para 5 salidas
    no_up = dash.no_update
    
    if not n_clicks: 
        return no_up, no_up, no_up, no_up, no_up
    
    # 1. Validación de campos vacíos
    if not username or not password or not password_confirm:
        return html.Span("Todos los campos son obligatorios.", className="text-warning"), no_up, no_up, no_up, no_up

    # 2. Validación de coincidencia de contraseñas
    if password != password_confirm:
        return html.Span("Las contraseñas no coinciden.", className="text-danger fw-bold"), no_up, no_up, no_up, no_up

    # 3. Intento de registro en Base de Datos
    success, msg = dm.register_user(username, password, email)
    
    if success:
        # Éxito: Mostramos mensaje y limpiamos TODOS los campos
        success_msg = html.Div([
            html.I(className="bi bi-check-circle-fill text-success me-2"),
            "¡Cuenta creada! ",
            dcc.Link("Ir al Login", href="/login", className="fw-bold text-white text-decoration-underline")
        ], className="text-success")
        
        return success_msg, "", "", "", ""
    else:
        # Error desde el backend (ej: usuario ya existe)
        return html.Span(msg, className="text-danger fw-bold"), no_up, no_up, no_up, no_up