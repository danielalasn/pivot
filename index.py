import dash
from dash import dcc, html
from dash.dependencies import Input, Output
import dash_bootstrap_components as dbc

# Importar la app principal (instanciada en app.py)
from app import app, server

# Importar los layouts de las páginas (módulos)
from pages import dashboard #, transactions, accounts, goals, investments, advice
# A medida que crees los otros módulos, añádelos aquí:
# from pages import dashboard, transactions, accounts, goals, investments, advice

# ------------------------------------------------------------------------------
# LAYOUT PRINCIPAL Y NAVEGACIÓN
# ------------------------------------------------------------------------------

# Define la barra lateral de navegación
sidebar = html.Div(
    id="sidebar",  # <-- CORRECCIÓN 1 (era un argumento posicional)
    className="sidebar",
    children=[
        html.H2("Pívot", className="sidebar-header"),
        html.Hr(className="sidebar-divider"),
        dbc.Nav(
            [
                dbc.NavLink("Dashboard", href="/", active="exact"),
                dbc.NavLink("Transacciones", href="/transacciones", active="exact"),
                dbc.NavLink("Cuentas", href="/cuentas", active="exact"),
                dbc.NavLink("Metas (Goals)", href="/metas", active="exact"),
                dbc.NavLink("Inversiones", href="/inversiones", active="exact"),
                dbc.NavLink("Consejos (Advice)", href="/consejos", active="exact"),
            ],
            vertical=True,
            pills=True,
        ),
    ],
)

# Define el contenedor principal donde se renderizarán las páginas
content = html.Div(id="page-content", className="content")

# Layout principal de la aplicación
app.layout = html.Div([
    dcc.Location(id="url", refresh=False),
    sidebar,
    content
])

# ------------------------------------------------------------------------------
# CALLBACK PARA RENDERIZAR PÁGINAS
# ------------------------------------------------------------------------------
# Este callback cambia el contenido de 'page-content' según la URL
@app.callback(
    Output("page-content", "children"),
    [Input("url", "pathname")]
)
def display_page(pathname):
    if pathname == "/":
        return dashboard.layout
    elif pathname == "/transacciones":
        # return transactions.layout  # Descomentar cuando crees 'pages/transactions.py'
        return html.P("Página de Transacciones (en construcción)")
    elif pathname == "/cuentas":
        # return accounts.layout
        return html.P("Página de Cuentas (en construcción)")
    elif pathname == "/metas":
        # return goals.layout
        return html.P("Página de Metas (en construcción)")
    elif pathname == "/inversiones":
        # return investments.layout
        return html.P("Página de Inversiones (en construcción)")
    elif pathname == "/consejos":
        # return advice.layout
        return html.P("Página de Consejos (en construcción)")
    
    # Página de error 404
    return dbc.Container(
        [
            html.H1("404: No encontrado", className="text-danger"),
            html.Hr(),
            html.P(f"El pathname {pathname} no fue reconocido..."),
        ],
        fluid=True,
        className="py-3",
    )

# ------------------------------------------------------------------------------
# PUNTO DE ENTRADA
# ------------------------------------------------------------------------------
if __name__ == "__main__":
    # app.run_server(debug=True, port=8050) <-- MÉTODO ANTIGUO
    app.run(debug=True, port=8050) # <-- CORRECCIÓN 2 (nuevo método de Dash 2+)