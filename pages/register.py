# pages/register.py
import dash
from dash import html, dcc, callback, Input, Output, State
import dash_bootstrap_components as dbc
import backend.data_manager as dm

# --- DEFINICIÓN DEL LAYOUT ---
# Esta variable 'layout' es la que index.py está buscando y no encuentra.
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
     Output("reg-email", "value")],
    Input("btn-register", "n_clicks"),
    [State("reg-username", "value"),
     State("reg-password", "value"),
     State("reg-email", "value")],
    prevent_initial_call=True
)
def register_process(n_clicks, username, password, email):
    if not n_clicks: return dash.no_update, dash.no_update, dash.no_update, dash.no_update
    
    if not username or not password:
        return html.Span("Usuario y contraseña son obligatorios.", className="text-warning"), dash.no_update, dash.no_update, dash.no_update

    success, msg = dm.register_user(username, password, email)
    
    if success:
        # Éxito: Mostramos mensaje y enlace para ir al login
        success_msg = html.Div([
            html.I(className="bi bi-check-circle-fill text-success me-2"),
            "¡Cuenta creada! ",
            dcc.Link("Ir al Login", href="/login", className="fw-bold text-white text-decoration-underline")
        ], className="text-success")
        # Limpiamos los campos
        return success_msg, "", "", ""
    else:
        # Error
        return html.Span(msg, className="text-danger fw-bold"), dash.no_update, dash.no_update, dash.no_update