# index.py
import dash
from dash import dcc, html, Input, Output, State, ctx, callback, clientside_callback
import dash_bootstrap_components as dbc
from flask_login import current_user, logout_user
import pandas as pd
import base64
import io

# Importar la app y el servidor
from app import app, server

# Importar páginas
from pages import dashboard, transactions, debts, login, admin, reports
from pages.accounts import accounts 
from pages.investments import investments 
from pages.distribution import distribution

# Importar Data Manager y UI Helpers
import backend.data_manager as dm 
import utils.ui_helpers as ui_helpers # <--- Importado desde carpeta utils

# ==============================================================================
# 1. MODALES DE AJUSTES (Ventanas Emergentes)
# ==============================================================================

# --- MODAL 1: MI PERFIL ---
modal_profile = dbc.Modal([
    dbc.ModalHeader(dbc.ModalTitle("Mi Perfil")),
    dbc.ModalBody([
        # Ya no necesitamos div de alertas aquí, usamos Toasts
        dbc.Label("Nombre de Visualización"),
        dbc.Input(id="input-profile-name", placeholder="Tu nombre", className="mb-3"),
        
        html.Hr(),
        
        dbc.Label("Cambiar Contraseña (Opcional)"),
        dbc.Input(id="input-profile-pass", type="password", placeholder="Nueva contraseña", className="mb-2"),
        dbc.Input(id="input-profile-pass-confirm", type="password", placeholder="Confirmar contraseña", className="mb-3"),
    ]),
    dbc.ModalFooter(
        dbc.Button("Guardar Cambios", id="btn-save-profile", color="primary", n_clicks=0)
    ),
], id="modal-profile", is_open=False)

# --- MODAL 2: IMPORTAR HISTORIAL ---
modal_import = dbc.Modal([
    dbc.ModalHeader(dbc.ModalTitle("Importar Historial Pasado")),
    dbc.ModalBody([
        dbc.Alert([
            html.H6("Formato Requerido (.xlsx / .csv):", className="alert-heading"),
            html.Ul([
                html.Li("Columna 'Date': Fecha (YYYY-MM-DD)"),
                html.Li("Columna 'Net_Worth': Valor numérico total")
            ], className="small mb-0")
        ], color="info"),
        dcc.Upload(
            id='upload-history-file',
            children=html.Div(['Arrastra un archivo o ', html.A('Selecciónalo')]),
            style={
                'width': '100%', 'height': '60px', 'lineHeight': '60px',
                'borderWidth': '1px', 'borderStyle': 'dashed',
                'borderRadius': '5px', 'textAlign': 'center',
                'borderColor': '#666'
            },
            multiple=False
        ),
        # Ya no necesitamos div de status aquí, usamos Toasts
    ]),
    dbc.ModalFooter(
        dbc.Button("Cerrar", id="btn-close-import", className="ms-auto", n_clicks=0)
    ),
], id="modal-import", is_open=False)

# --- MODAL 3: SISTEMA ---
modal_system = dbc.Modal([
    dbc.ModalHeader(dbc.ModalTitle("Sistema y Datos")),
    dbc.ModalBody([
        # (Sección de Exportar ELIMINADA - Ahora vive en la página de Reportes)
        
        html.H5("Zona de Peligro", className="text-danger"),
        dbc.Alert("Esta acción eliminará tu cuenta y todos tus registros permanentemente.", color="danger", className="small"),
        
        dbc.Label("Para confirmar, escribe: 'borrar toda mi data'"),
        dbc.Input(id="input-delete-confirm", placeholder="Escribe la frase aquí...", type="text", className="mb-3"),
        
        dbc.Button([html.I(className="bi bi-trash me-2"), "Borrar Todo Definitivamente"], 
                   color="danger", outline=True, className="w-100", id="btn-delete-all-data"),
    ]),
], id="modal-system", is_open=False)

# ==============================================================================
# 2. NAVBAR SUPERIOR (Con Saludo y Dropdown)
# ==============================================================================
navbar = dbc.Navbar(
    dbc.Container([
        # LADO IZQUIERDO: Botón Menú + Logo
        dbc.Row([
            dbc.Col(
                dbc.Button(html.I(className="bi bi-list fs-2"), id="open-offcanvas-btn", color="link", className="p-0 text-white"),
                width="auto"
            ),
            dbc.Col(
                dbc.NavbarBrand("Pívot Finance", className="ms-3 fw-bold", href="/"),
                width="auto"
            ),
        ], align="center", className="g-0"),

        # LADO DERECHO: Saludo + Dropdown
        dbc.Row([
            # 1. Saludo al usuario
            dbc.Col(
                html.Span(id="user-greeting", className="me-3 text-white d-none d-md-block fw-light"), 
                width="auto", className="d-flex align-items-center"
            ),
            # 2. Dropdown de Ajustes
            dbc.Col(
                dbc.Nav([
                    dbc.DropdownMenu(
                        [
                            dbc.DropdownMenuItem("Mi Perfil", id="opt-profile", n_clicks=0),
                            dbc.DropdownMenuItem("Importar Historial", id="opt-import", n_clicks=0),
                            dbc.DropdownMenuItem("Sistema", id="opt-system", n_clicks=0),
                            dbc.DropdownMenuItem(divider=True),
                            # Clase text-danger para color rojo (Bootstrap)
                            dbc.DropdownMenuItem("Cerrar Sesión", href="/logout", className="text-danger"), 
                        ],
                        label=html.I(className="bi bi-gear-fill fs-4"), 
                        nav=True,
                        in_navbar=True,
                        align_end=True, 
                        caret=False,   
                        color="link",   
                        className="text-white"
                    )
                ], navbar=True),
                width="auto"
            )
        ], align="center", className="g-0 ms-auto"),

    ], fluid=True),
    id="main-navbar",
    color="dark",
    dark=True,
    fixed="top",
    style={"display": "none"} # Se controla con callback
)


# ==============================================================================
# 3. SIDEBAR
# ==============================================================================
sidebar = dbc.Offcanvas(
    html.Div([
        html.H2("Pívot", className="offcanvas-header-title-custom mb-4"),
        dbc.Nav(id="sidebar-nav-links", vertical=True, pills=True), 
    ], className="h-100 d-flex flex-column"),
    id="offcanvas-sidebar",
    is_open=False,
    placement="start",
    className="offcanvas-custom",
    backdrop=True 
)


# ==============================================================================
# LAYOUT PRINCIPAL
# ==============================================================================
app.layout = html.Div([
    dcc.Location(id="url", refresh=False),
    dcc.Store(id="theme-store", storage_type="local"), # Store para tema (si se usa)
    
    # --- COMPONENTE TOAST (Notificaciones Flotantes) ---
    ui_helpers.get_feedback_toast("settings-toast"),
    
    # Componentes fijos
    navbar,  
    sidebar,
    
    # Modales
    modal_profile,
    modal_import,
    modal_system,
    
    # Contenido de las páginas
    html.Div(id="page-content", className="main-content p-0"),
])


# ==============================================================================
# CALLBACKS DE NAVEGACIÓN Y VISUALIZACIÓN
# ==============================================================================

# 1. CONTROL DE VISUALIZACIÓN DE MODALES (SOLO APERTURA Y CIERRE BÁSICO)
@app.callback(
    [Output("modal-profile", "is_open"),
     Output("modal-import", "is_open"),
     Output("modal-system", "is_open")],
    [Input("opt-profile", "n_clicks"),
     Input("opt-import", "n_clicks"),
     Input("opt-system", "n_clicks"),
     Input("btn-close-import", "n_clicks")], 
    [State("modal-profile", "is_open"),
     State("modal-import", "is_open"),
     State("modal-system", "is_open")],
    prevent_initial_call=True
)
def toggle_modals(n_prof, n_imp, n_sys, n_close_imp, is_prof, is_imp, is_sys):
    ctx_id = ctx.triggered_id
    
    # Perfil
    if ctx_id == "opt-profile": return not is_prof, False, False
    
    # Importar
    if ctx_id == "opt-import": return False, not is_imp, False
    if ctx_id == "btn-close-import": return False, False, False
    
    # Sistema
    if ctx_id == "opt-system": return False, False, not is_sys
    
    return is_prof, is_imp, is_sys

# ------------------------------------------------------------------------------
# 9. CALLBACK: BORRAR CUENTA (CON CONFIRMACIÓN DE TEXTO)
# ------------------------------------------------------------------------------
@app.callback(
    [Output("settings-toast", "is_open", allow_duplicate=True),
     Output("settings-toast", "children", allow_duplicate=True),
     Output("settings-toast", "icon", allow_duplicate=True),
     Output("url", "pathname", allow_duplicate=True)], # Para redirigir al logout
    Input("btn-delete-all-data", "n_clicks"),
    State("input-delete-confirm", "value"),
    prevent_initial_call=True
)
def delete_account_callback(n, confirm_text):
    # 1. Verificar frase de seguridad
    if confirm_text != "borrar toda mi data":
        is_open, msg, icon = ui_helpers.mensaje_alerta_exito("danger", "Frase de confirmación incorrecta.")
        return is_open, msg, icon, dash.no_update

    # 2. Intentar borrar usuario y datos
    # Usamos la función admin_delete_user pasando el ID del usuario actual
    success, text_msg = dm.admin_delete_user(current_user.id)
    
    if success:
        # ÉXITO: Redirigir a logout inmediatamente
        return True, "Cuenta eliminada. Adiós.", "success", "/logout"
    else:
        # ERROR: Mostrar mensaje y quedarse ahí
        is_open, msg, icon = ui_helpers.mensaje_alerta_exito("danger", text_msg)
        return is_open, msg, icon, dash.no_update

# 2. NAVEGACIÓN LATERAL
@app.callback(
    Output("sidebar-nav-links", "children"),
    Input("url", "pathname")
)
def update_sidebar_links(pathname):
    links = [
        dbc.NavLink([html.I(className="bi bi-house me-2"), "Dashboard"], href="/", active="exact"),
        dbc.NavLink([html.I(className="bi bi-receipt me-2"), "Transacciones"], href="/transacciones", active="exact"),
        dbc.NavLink([html.I(className="bi bi-wallet2 me-2"), "Cuentas"], href="/cuentas", active="exact"),
        dbc.NavLink([html.I(className="bi bi-arrow-left-right me-2"), "Deudas"], href="/deudas", active="exact"), 
        dbc.NavLink([html.I(className="bi bi-graph-up me-2"), "Inversiones"], href="/inversiones", active="exact"),
        dbc.NavLink([html.I(className="bi bi-pie-chart me-2"), "Distribución"], href="/distribucion", active="exact"),
        dbc.NavLink([html.I(className="bi bi-file-earmark-text me-2"), "Reportes"], href="/reportes", active="exact"),
    ]
    
    if current_user.is_authenticated and current_user.username == 'admin': 
         links.append(dbc.NavLink([html.I(className="bi bi-shield-lock me-2 text-warning"), "Admin Panel"], href="/admin", active="exact"))
    
    return links


# 3. RUTEO DE PÁGINAS
@app.callback(
    Output("page-content", "children"),
    Input("url", "pathname")
)
def display_page(pathname):
    if pathname == "/logout":
        if current_user.is_authenticated: logout_user()
        return login.layout

    if pathname == "/login":
        if current_user.is_authenticated: return dashboard.layout 
        return login.layout
    
    if current_user.is_authenticated:
        if pathname == "/" or pathname == "/dashboard": return dashboard.layout
        elif pathname == "/transacciones": return transactions.layout
        elif pathname == "/cuentas": return accounts.layout
        elif pathname == "/deudas": return debts.layout
        elif pathname == "/inversiones": return investments.layout
        elif pathname == "/distribucion": return distribution.layout
        elif pathname == "/reportes": return reports.layout
        elif pathname == "/admin": return admin.layout
        else: return html.Div([html.H1("404"), html.P("Página no encontrada")], className="p-5 text-center")
    
    return login.layout


# 4. VISIBILIDAD DE NAVBAR Y CLASES CSS
# 4. VISIBILIDAD DE NAVBAR Y CLASES CSS
# index.py -> dentro de toggle_navbar_visibility

@app.callback(
    [Output("main-navbar", "style"), 
     Output("page-content", "className")], 
    Input("url", "pathname")
)
def toggle_navbar_visibility(pathname):
    if pathname in ["/login", "/register", "/logout"] or not current_user.is_authenticated:
        return {"display": "none"}, "main-content p-0"
    
    # 🚨 CAMBIO AQUÍ: Usamos pb-2 o pb-3 para reducir el padding inferior 
    # (El 'pt-5 mt-5' es necesario para la navbar fija)
    return {"display": "block"}, "main-content pt-5 mt-5 px-2 px-md-4 pb-2" 
    # Añade 'pb-2' (padding-bottom: 0.5rem) o 'pb-3' (padding-bottom: 1rem)



# 5. CONTROL DEL SIDEBAR
@app.callback(
    Output("offcanvas-sidebar", "is_open"),
    [Input("open-offcanvas-btn", "n_clicks"), Input("url", "pathname")],
    [State("offcanvas-sidebar", "is_open")],
    prevent_initial_call=True
)
def toggle_sidebar(n, pathname, is_open):
    if ctx.triggered_id == "open-offcanvas-btn":
        return not is_open
    return False


# ==============================================================================
# CALLBACKS DE LÓGICA (SETTINGS)
# ==============================================================================

# 6. ACTUALIZAR SALUDO
@app.callback(
    [Output("user-greeting", "children"),
     Output("input-profile-name", "value")], 
    [Input("url", "pathname"), 
     Input("btn-save-profile", "n_clicks")], 
     prevent_initial_call=False
)
def update_user_greeting(pathname, n_save):
    if current_user.is_authenticated:
        greeting = f"Hola, {current_user.display_name}"
        return greeting, current_user.display_name
    return "", ""


# 7. GUARDAR PERFIL (CON TOAST)
@app.callback(
    [Output("settings-toast", "is_open"),
     Output("settings-toast", "children"),
     Output("settings-toast", "icon"),
     Output("modal-profile", "is_open", allow_duplicate=True)], 
    Input("btn-save-profile", "n_clicks"),
    [State("input-profile-name", "value"),
     State("input-profile-pass", "value"),
     State("input-profile-pass-confirm", "value")],
    prevent_initial_call=True
)
def save_profile_changes(n, name, password, confirm):
    if not name:
        is_open, msg, icon = ui_helpers.mensaje_alerta_exito("danger", "El nombre no puede estar vacío.")
        return is_open, msg, icon, True # Mantener abierto
    
    final_pass = None
    if password or confirm:
        if password != confirm:
            is_open, msg, icon = ui_helpers.mensaje_alerta_exito("danger", "Las contraseñas no coinciden.")
            return is_open, msg, icon, True
        if len(password) < 4:
            is_open, msg, icon = ui_helpers.mensaje_alerta_exito("warning", "La contraseña es muy corta.")
            return is_open, msg, icon, True
        final_pass = password
    
    success, text_msg = dm.update_user_profile_data(name, final_pass)
    
    if success:
        is_open, msg, icon = ui_helpers.mensaje_alerta_exito("success", text_msg)
        return is_open, msg, icon, False # CERRAR MODAL
    else:
        is_open, msg, icon = ui_helpers.mensaje_alerta_exito("danger", text_msg)
        return is_open, msg, icon, True # MANTENER ABIERTO


# 8. IMPORTAR HISTORIAL (CON TOAST)
@app.callback(
    [Output("settings-toast", "is_open", allow_duplicate=True),
     Output("settings-toast", "children", allow_duplicate=True),
     Output("settings-toast", "icon", allow_duplicate=True),
     Output("modal-import", "is_open", allow_duplicate=True)],
    Input("upload-history-file", "contents"),
    State("upload-history-file", "filename"),
    prevent_initial_call=True
)
def import_history_callback(contents, filename):
    if contents is None: return dash.no_update
    
    content_type, content_string = contents.split(',')
    decoded = base64.b64decode(content_string)
    
    try:
        if 'csv' in filename:
            df = pd.read_csv(io.StringIO(decoded.decode('utf-8')))
        elif 'xls' in filename:
            df = pd.read_excel(io.BytesIO(decoded))
        else:
            is_open, msg, icon = ui_helpers.mensaje_alerta_exito("danger", "Formato no soportado. Usa CSV o Excel.")
            return is_open, msg, icon, True
        
        # Validaciones
        df.columns = [c.strip() for c in df.columns]
        cols_lower = [c.lower() for c in df.columns]
        
        if 'date' not in cols_lower or 'net_worth' not in cols_lower:
             is_open, msg, icon = ui_helpers.mensaje_alerta_exito("danger", "Requiere columnas 'Date' y 'Net_Worth'.")
             return is_open, msg, icon, True
        
        col_map = {c: c.title() for c in df.columns}
        df.rename(columns=col_map, inplace=True)
        if 'Date' not in df.columns: df.rename(columns={df.columns[cols_lower.index('date')]: 'Date'}, inplace=True)
        if 'Net_Worth' not in df.columns: df.rename(columns={df.columns[cols_lower.index('net_worth')]: 'Net_Worth'}, inplace=True)

        success, text_msg = dm.import_historical_data(df[['Date', 'Net_Worth']])
        
        if success:
            is_open, msg, icon = ui_helpers.mensaje_alerta_exito("success", text_msg)
            return is_open, msg, icon, False # CERRAR MODAL
        else:
            is_open, msg, icon = ui_helpers.mensaje_alerta_exito("danger", text_msg)
            return is_open, msg, icon, True

    except Exception as e:
        is_open, msg, icon = ui_helpers.mensaje_alerta_exito("danger", f"Error: {str(e)}")
        return is_open, msg, icon, True

# Callback original de tema (si existe el switch)
clientside_callback(
    """
    function(is_light) {
        if (is_light) {
            document.documentElement.setAttribute('data-theme', 'light');
            return "light";
        } else {
            document.documentElement.removeAttribute('data-theme');
            return "dark";
        }
    }
    """,
    Output("theme-store", "data"),
    Input("theme-switch", "value"), # Asegúrate de que este ID exista si usas el switch
    prevent_initial_call=True
)

if __name__ == "__main__":
    app.run(debug=True, port=8050)