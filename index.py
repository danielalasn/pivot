import dash
from dash import dcc, html, Input, Output, State, clientside_callback, ctx
import dash_bootstrap_components as dbc

# Importar la app principal
from app import app, server

# Importar los layouts de las páginas
from pages import dashboard, transactions, debts
from pages.accounts import accounts 

# 🚨 CAMBIO 1: Importamos el archivo 'padre' que tiene las tabs
from pages.investments import investments 

# ------------------------------------------------------------------------------
# 1. CONTENIDO DEL OFFCANVAS (Sidebar)
# ------------------------------------------------------------------------------

# Lista de enlaces de navegación
nav_links = [
    dbc.NavLink([html.I(className="bi bi-house me-2"), "Dashboard"], href="/", active="exact"),
    dbc.NavLink([html.I(className="bi bi-receipt me-2"), "Transacciones"], href="/transacciones", active="exact"),
    dbc.NavLink([html.I(className="bi bi-wallet2 me-2"), "Cuentas"], href="/cuentas", active="exact"),
    dbc.NavLink([html.I(className="bi bi-arrow-left-right me-2"), "Deudas y Cobros"], href="/deudas", active="exact"), 
    dbc.NavLink([html.I(className="bi bi-bullseye me-2"), "Metas"], href="/metas", active="exact"),
    dbc.NavLink([html.I(className="bi bi-graph-up me-2"), "Inversiones"], href="/inversiones", active="exact"),
    dbc.NavLink([html.I(className="bi bi-lightbulb me-2"), "Consejos"], href="/consejos", active="exact"),
]

# Contenido del Offcanvas
offcanvas_content = html.Div(
    [
        # Encabezado personalizado
        html.H1("Pívot", className="offcanvas-header-title-custom"),

        html.Hr(className="sidebar-divider"),
        
        # Navegación
        dbc.Nav(nav_links, vertical=True, pills=True, id="nav-list"), 
        
        # Switch de tema
        html.Div([
            dbc.Label("Modo Claro", html_for="theme-switch", className="text-muted small mb-1"),
            dbc.Switch(
                id="theme-switch",
                value=False,
                className="d-inline-block ms-2",
                persistence=True, 
                persistence_type='local'
            ),
        ], className="d-flex align-items-center justify-content-center pt-3 pb-2")
    ],
    className="h-100 d-flex flex-column" 
)

# ------------------------------------------------------------------------------
# 2. NAVBAR (Encabezado Fijo)
# ------------------------------------------------------------------------------
navbar = dbc.Navbar(
    dbc.Container(
        [
            dbc.Row(
                [
                    # Botón Hamburguesa
                    dbc.Col(
                        dbc.Button(
                            html.I(className="bi bi-list text-white", style={"fontSize": "1.8rem"}), 
                            id="open-offcanvas-btn",
                            n_clicks=0,
                            className="p-1", 
                            style={"border": "none", "backgroundColor": "transparent"} 
                        ),
                        width="auto",
                        className="d-flex align-items-center me-2"
                    ),
                    
                    # Título
                    dbc.Col(
                        html.A(
                            html.H1(
                                "Pívot",
                                className="mb-0 navbar-brand text-white fw-bolder",
                                style={"fontSize": "1.5rem"}
                            ),
                            href="/",
                            style={"textDecoration": "none"},
                        ),
                        width="auto",
                        className="d-flex align-items-center"
                    ),
                ],
                align="center",
                className="g-0 flex-grow-1", 
            ),
            html.Div(className="ms-auto")
        ],
        fluid=True,
        className="px-3 py-2" 
    ),
    id="main-navbar",
    color="dark",
    dark=True,
    fixed="top", 
    style={"zIndex": 1020, "borderBottom": "none"} 
)


# ------------------------------------------------------------------------------
# LAYOUT PRINCIPAL
# ------------------------------------------------------------------------------
app.layout = html.Div([
    dcc.Location(id="url", refresh=False),
    dcc.Store(id="theme-store"), 
    
    navbar, 
    
    html.Div(id="page-content", className="main-content"),
    
    dbc.Offcanvas(
        offcanvas_content,
        id="offcanvas-sidebar",
        title="", 
        is_open=False,
        placement="start",
        scrollable=True,
        className="offcanvas-custom",
        backdrop=True 
    ),
    
], id="main-container")


# ------------------------------------------------------------------------------
# CALLBACKS
# ------------------------------------------------------------------------------

@app.callback(
    Output("offcanvas-sidebar", "is_open"),
    [Input("open-offcanvas-btn", "n_clicks"), 
     Input("url", "pathname")],
    [State("offcanvas-sidebar", "is_open")],
    prevent_initial_call=True
)
def toggle_offcanvas_and_close_on_nav(n_clicks, pathname, is_open):
    trig_id = ctx.triggered_id

    if trig_id == "open-offcanvas-btn":
        return not is_open
    
    if trig_id == "url" and is_open:
        return False
        
    return is_open

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


# ------------------------------------------------------------------------------
# CALLBACK PARA RENDERIZAR PÁGINAS
# ------------------------------------------------------------------------------
@app.callback(
    Output("page-content", "children"),
    [Input("url", "pathname")]
)
def display_page(pathname):
    if pathname == "/":
        return dashboard.layout
    elif pathname == "/transacciones":
        return transactions.layout
    elif pathname == "/cuentas":
        return accounts.layout
    elif pathname == "/deudas":
        return debts.layout
    elif pathname == "/metas":
        return html.P("Página de Metas (en construcción)")
    elif pathname == "/inversiones":
        # 🚨 CAMBIO 2: Llamamos al layout 'padre' (investments.layout) 
        # que contiene las pestañas, no al 'hijo' (assets)
        return investments.layout
    elif pathname == "/consejos":
         return html.P("Página de Consejos (en construcción)")
    
    return dbc.Container(
        [
            html.H1("404: No encontrado", className="text-danger"),
            html.Hr(),
            html.P(f"El pathname {pathname} no fue reconocido..."),
        ],
        fluid=True,
        className="py-3",
    )

if __name__ == "__main__":
    app.run(debug=True, port=8050)