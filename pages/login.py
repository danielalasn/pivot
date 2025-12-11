# pages/login.py
import dash
from dash import html, dcc, callback, Input, Output, State, no_update
import dash_bootstrap_components as dbc
from flask_login import login_user
import backend.data_manager as dm
from backend.models import verify_user

# --- 1. ESTILOS RESPONSIVOS ---

PAGE_BACKGROUND_STYLE = {
    "backgroundImage": "url('https://images.unsplash.com/photo-1639322537228-f710d846310a?q=80&w=2664&auto=format&fit=crop')",
    "backgroundSize": "cover",
    "backgroundPosition": "center",
    "backgroundRepeat": "no-repeat",
    "backgroundAttachment": "fixed",
    "minHeight": "100vh",
    "width": "100%",
    "position": "relative",
    "display": "flex",
    "flexDirection": "column",
    "justifyContent": "center",
    "alignItems": "center"
}

OVERLAY_STYLE = {
    "position": "absolute",
    "top": 0, "left": 0, "right": 0, "bottom": 0,
    "backgroundColor": "rgba(0, 0, 0, 0.75)",
    "zIndex": 1
}

GLASS_CARD_STYLE = {
    "background": "rgba(20, 20, 20, 0.6)",
    "backdropFilter": "blur(12px)",
    "WebkitBackdropFilter": "blur(12px)",
    "border": "1px solid rgba(255, 255, 255, 0.15)",
    "borderRadius": "16px",
    "boxShadow": "0 8px 32px 0 rgba(0, 0, 0, 0.7)",
    "position": "relative",
    "zIndex": 2,
    "overflow": "hidden"
}

INPUT_STYLE = {
    "backgroundColor": "rgba(0, 0, 0, 0.4)",
    "border": "1px solid #444",
    "color": "white",
    "borderRadius": "8px",
    "padding": "10px"
}

BRAND_STYLE = {
    "background": "-webkit-linear-gradient(45deg, #00d2ff, #3a7bd5)",
    "WebkitBackgroundClip": "text",
    "WebkitTextFillColor": "transparent",
    "fontWeight": "900",
    "fontSize": "3rem",
    "marginBottom": "0.5rem",
    "letterSpacing": "-1px"
}

# --- ESTILOS DE BOTONES ---

BTN_LOGIN_STYLE = {
    "background": "linear-gradient(90deg, #00d2ff 0%, #3a7bd5 100%)",
    "border": "none",
    "color": "white",
    "fontWeight": "700",
    "padding": "10px",
    "boxShadow": "0 4px 15px rgba(0, 210, 255, 0.4)"
}

BTN_REG_STYLE = {
    "background": "linear-gradient(90deg, #11998e 0%, #38ef7d 100%)", 
    "border": "none",
    "color": "white",
    "fontWeight": "700",
    "padding": "10px",
    "boxShadow": "0 4px 15px rgba(56, 239, 125, 0.4)" 
}

# --- NUEVO ESTILO PARA EL FONDO DEL MODAL (CORRECCIÓN DE COLOR) ---
MODAL_CONTENT_STYLE = {
    "backgroundColor": "#121212",  # Negro profundo (casi puro)
    "color": "white",
    "border": "1px solid #333",    # Borde sutil oscuro
    "borderRadius": "12px",
    "boxShadow": "0 10px 30px rgba(0,0,0,0.8)" # Sombra fuerte para profundidad
}

# Quitamos los bordes blancos por defecto de header/footer
MODAL_HEADER_STYLE = {"borderBottom": "1px solid #333", "backgroundColor": "transparent"}
MODAL_FOOTER_STYLE = {"borderTop": "1px solid #333", "backgroundColor": "transparent"}


# --- MODAL DE REGISTRO ---
register_modal = dbc.Modal([
    # Header transparente con borde oscuro
    dbc.ModalHeader(
        dbc.ModalTitle("Únete a Pívot", style={"color": "white", "fontWeight": "bold"}), 
        close_button=True, 
        style=MODAL_HEADER_STYLE
    ),
    
    # Body transparente (hereda el negro del content_style)
    dbc.ModalBody([
        html.Div(className="text-center mb-4", children=[
            html.I(className="bi bi-rocket-takeoff-fill", style={"fontSize": "2.5rem", "color": "#38ef7d"}) 
        ]),
        dbc.Label("Usuario", className="small text-secondary"),
        dbc.Input(id="reg-username", type="text", placeholder="Usuario", style=INPUT_STYLE, className="mb-3"),
        
        dbc.Label("Correo (Opcional)", className="small text-secondary"),
        dbc.Input(id="reg-email", type="email", placeholder="tu@email.com", style=INPUT_STYLE, className="mb-3"),
        
        dbc.Label("Contraseña", className="small text-secondary"),
        dbc.Input(id="reg-password", type="password", placeholder="••••••••", style=INPUT_STYLE, className="mb-4"),
        
        html.Div(id="register-feedback", className="text-center small fw-bold")
    ]), # No ponemos className bg-dark aquí para que use nuestro estilo custom
    
    # Footer transparente con borde oscuro
    dbc.ModalFooter([
        dbc.Button("Cancelar", id="btn-cancel-reg", color="secondary", outline=True, size="sm", className="border-secondary"),
        dbc.Button("Crear Cuenta", id="btn-submit-reg", style=BTN_REG_STYLE), 
    ], style=MODAL_FOOTER_STYLE)

], id="register-modal", is_open=False, centered=True, backdrop="static", content_style=MODAL_CONTENT_STYLE) # <--- AQUI APLICAMOS EL FONDO NEGRO


# --- LAYOUT PRINCIPAL ---
layout = html.Div([
    register_modal,
    html.Div(id="register-success-signal", style={"display": "none"}),
    html.Div(style=OVERLAY_STYLE),

    dbc.Container([
        dbc.Row([
            dbc.Col([
                html.Div([
                    html.H1("Pívot.", style=BRAND_STYLE),
                    html.P("Tu centro de comando financiero.", className="text-white-50 lead fs-6")
                ], className="text-center mb-4", style={"position": "relative", "zIndex": 2}),

                dbc.Card([
                    dbc.CardBody([
                        html.H4("Iniciar Sesión", className="text-white fw-bold mb-4 text-center"),
                        html.Div(id="login-alert-area", className="mb-3"),

                        dbc.Label("Usuario", className="small text-info fw-bold mb-1"),
                        dbc.InputGroup([
                            dbc.InputGroupText(html.I(className="bi bi-person-fill"), className="bg-transparent border-secondary text-secondary"),
                            dbc.Input(id="login-username", type="text", placeholder="Usuario", style=INPUT_STYLE),
                        ], className="mb-3"),
                        
                        dbc.Label("Contraseña", className="small text-info fw-bold mb-1"),
                        dbc.InputGroup([
                            dbc.InputGroupText(html.I(className="bi bi-lock-fill"), className="bg-transparent border-secondary text-secondary"),
                            dbc.Input(id="login-password", type="password", placeholder="••••••••", style=INPUT_STYLE),
                        ], className="mb-4"),
                        
                        dbc.Button("Acceder", id="btn-login", style=BTN_LOGIN_STYLE, className="w-100 mb-4"),

                        html.Div(className="d-flex align-items-center mb-3", children=[
                            html.Hr(className="flex-grow-1 border-secondary"),
                            html.Span(" o ", className="mx-2 text-muted small"),
                            html.Hr(className="flex-grow-1 border-secondary"),
                        ]),

                        html.Div([
                            html.Span("¿Aún no tienes cuenta? ", className="text-white-50 small"),
                            html.A("Regístrate", id="btn-open-reg-modal", href="#", 
                                   style={"color": "#38ef7d", "cursor": "pointer"}, 
                                   className="fw-bold small text-decoration-none ms-1")
                        ], className="text-center")

                    ], className="p-4")
                ], style=GLASS_CARD_STYLE)

            ], width=11, sm=8, md=6, lg=4)
        ], className="justify-content-center w-100")
    ], fluid=True, className="d-flex justify-content-center align-items-center h-100")

], style=PAGE_BACKGROUND_STYLE)


# --- CALLBACKS ---

@callback(
    [Output("url", "pathname", allow_duplicate=True),
     Output("login-alert-area", "children", allow_duplicate=True)],
    Input("btn-login", "n_clicks"),
    [State("login-username", "value"),
     State("login-password", "value")],
    prevent_initial_call=True
)
def login_process(n_clicks, username, password):
    if not n_clicks: return no_update, no_update
    if not username or not password:
        return no_update, dbc.Alert("Faltan datos.", color="warning", className="small py-2", dismissable=True)

    clean_user = username.strip().lower()
    clean_pass = password.strip()
    user = verify_user(clean_user, clean_pass)
    
    if user:
        dm.clear_all_caches()
        login_user(user)
        dm.update_last_login(user.id)
        return "/", ""
    else:
        return no_update, dbc.Alert("Error de credenciales.", color="danger", className="small py-2", dismissable=True)

@callback(
    Output("register-modal", "is_open"),
    [Input("btn-open-reg-modal", "n_clicks"),
     Input("btn-cancel-reg", "n_clicks"),
     Input("register-success-signal", "children")],
    [State("register-modal", "is_open")],
    prevent_initial_call=True
)
def toggle_register_modal(open_click, cancel_click, success_signal, is_open):
    if success_signal == "SUCCESS": return False
    if open_click or cancel_click: return not is_open
    return is_open

@callback(
    [Output("register-feedback", "children"),
     Output("login-alert-area", "children", allow_duplicate=True),
     Output("register-success-signal", "children"),
     Output("reg-username", "value"),
     Output("reg-password", "value"),
     Output("reg-email", "value")],
    Input("btn-submit-reg", "n_clicks"),
    [State("reg-username", "value"),
     State("reg-password", "value"),
     State("reg-email", "value")],
    prevent_initial_call=True
)
def process_registration(n_clicks, username, password, email):
    if not n_clicks: return no_update, no_update, no_update, no_update, no_update, no_update
    if not username or not password:
        return html.Span("Completa los campos.", className="text-warning"), no_update, "FAIL", no_update, no_update, no_update

    success, msg = dm.register_user(username, password, email)
    
    if success:
        success_alert = dbc.Alert([html.I(className="bi bi-check-circle-fill me-2"), "¡Cuenta creada!"], color="success", className="small py-2", dismissable=True)
        return "", success_alert, "SUCCESS", "", "", ""
    else:
        return html.Span(msg, className="text-danger"), no_update, "FAIL", no_update, no_update, no_update