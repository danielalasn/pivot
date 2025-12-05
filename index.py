# index.py
import dash
from dash import dcc, html, Input, Output, State, clientside_callback, ctx
import dash_bootstrap_components as dbc
from flask_login import current_user, logout_user

# Importar la app y páginas
from app import app, server
# 🚨 CAMBIO 1: Agregamos 'register' a la lista de importaciones iniciales
from pages import dashboard, transactions, debts, login, register 
from pages.accounts import accounts 
from pages.investments import investments 

# ------------------------------------------------------------------------------
# 1. CONTENIDO DEL SIDEBAR (Solo se mostrará si hay login)
# ------------------------------------------------------------------------------
nav_links = [
    dbc.NavLink([html.I(className="bi bi-house me-2"), "Dashboard"], href="/", active="exact"),
    dbc.NavLink([html.I(className="bi bi-receipt me-2"), "Transacciones"], href="/transacciones", active="exact"),
    dbc.NavLink([html.I(className="bi bi-wallet2 me-2"), "Cuentas"], href="/cuentas", active="exact"),
    dbc.NavLink([html.I(className="bi bi-arrow-left-right me-2"), "Deudas"], href="/deudas", active="exact"), 
    dbc.NavLink([html.I(className="bi bi-graph-up me-2"), "Inversiones"], href="/inversiones", active="exact"),
    
    # Botón de Salir (Logout)
    dbc.NavLink([html.I(className="bi bi-box-arrow-left me-2 text-danger"), "Cerrar Sesión"], href="/logout", active="exact", className="mt-4 border-top border-secondary pt-3"),
]

sidebar = dbc.Offcanvas(
    html.Div([
        html.H2("Pívot", className="offcanvas-header-title-custom mb-4"),
        dbc.Nav(nav_links, vertical=True, pills=True),
    ], className="h-100 d-flex flex-column"),
    id="offcanvas-sidebar",
    is_open=False,
    placement="start",
    className="offcanvas-custom",
    backdrop=True 
)

# ------------------------------------------------------------------------------
# 2. NAVBAR (Solo visible si hay login)
# ------------------------------------------------------------------------------
navbar = dbc.Navbar(
    dbc.Container([
        dbc.Row([
            dbc.Col(
                dbc.Button(html.I(className="bi bi-list text-white fs-2"), id="open-offcanvas-btn", color="link", className="p-0"),
                width="auto"
            ),
            dbc.Col(
                dbc.NavbarBrand("Pívot Finance", className="ms-3 fw-bold"),
                width="auto"
            ),
        ], align="center", className="g-0"),
    ], fluid=True),
    id="main-navbar",
    color="dark",
    dark=True,
    fixed="top",
    style={"display": "none"} 
)

# ------------------------------------------------------------------------------
# LAYOUT PRINCIPAL
# ------------------------------------------------------------------------------
app.layout = html.Div([
    dcc.Location(id="url", refresh=False),
    
    navbar,  
    sidebar, 
    
    html.Div(id="page-content", className="main-content p-0"),
])

# ------------------------------------------------------------------------------
# CALLBACKS DE NAVEGACIÓN Y SEGURIDAD
# ------------------------------------------------------------------------------

@app.callback(
    Output("page-content", "children"),
    Input("url", "pathname")
)
def display_page(pathname):
    # A. Manejo de Logout
    if pathname == "/logout":
        if current_user.is_authenticated:
            logout_user()
        return login.layout

    # B. Rutas Públicas (Solo Login y Registro)
    if pathname == "/login":
        if current_user.is_authenticated: return dashboard.layout 
        return login.layout
    
    # 🚨 CAMBIO 2: Ya no importamos 'register' aquí adentro, usamos el global
    if pathname == "/register":
        if current_user.is_authenticated: return dashboard.layout
        return register.layout # Usa la variable importada arriba

    # C. Rutas Privadas (Requieren Auth)
    if current_user.is_authenticated:
        if pathname == "/" or pathname == "/dashboard":
            return dashboard.layout
        elif pathname == "/transacciones":
            return transactions.layout
        elif pathname == "/cuentas":
            return accounts.layout
        elif pathname == "/deudas":
            return debts.layout
        elif pathname == "/inversiones":
            return investments.layout
        else:
            return html.Div([html.H1("404"), html.P("Página no encontrada")], className="p-5 text-center")
    
    # D. Si no está logueado y trata de entrar a una privada -> Login
    return login.layout


@app.callback(
    [Output("main-navbar", "style"), 
     Output("page-content", "className")], 
    Input("url", "pathname")
)
def toggle_navbar_visibility(pathname):
    # 🚨 CAMBIO 3: Añadimos "/register" a la lista de páginas sin menú
    if pathname == "/login" or pathname == "/register" or pathname == "/logout" or not current_user.is_authenticated:
        return {"display": "none"}, "main-content p-0"
    
    return {"display": "block"}, "main-content pt-5 mt-5 px-4"


@app.callback(
    Output("offcanvas-sidebar", "is_open"),
    [Input("open-offcanvas-btn", "n_clicks"), Input("url", "pathname")],
    [State("offcanvas-sidebar", "is_open")],
    prevent_initial_call=True
)
def toggle_sidebar(n, pathname, is_open):
    trig = ctx.triggered_id
    if trig == "open-offcanvas-btn":
        return not is_open
    return False

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
    Input("theme-switch", "value"),
)

if __name__ == "__main__":
    app.run(debug=True, port=8050)