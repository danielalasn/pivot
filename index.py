import dash
from dash import dcc, html, Input, Output, State, clientside_callback
import dash_bootstrap_components as dbc

# Importar la app principal
from app import app, server

# Importar los layouts de las páginas
from pages import dashboard, transactions
from pages.accounts import accounts 

# ------------------------------------------------------------------------------
# LAYOUT PRINCIPAL Y NAVEGACIÓN
# ------------------------------------------------------------------------------

sidebar = html.Div(
    id="sidebar", 
    className="sidebar",
    children=[
        html.H2("Pívot", className="sidebar-header"),
        html.Hr(className="sidebar-divider"),
        
        # --- NAVEGACIÓN ---
        dbc.Nav(
            [
                dbc.NavLink([html.I(className="bi bi-house me-2"), "Dashboard"], href="/", active="exact"),
                dbc.NavLink([html.I(className="bi bi-receipt me-2"), "Transacciones"], href="/transacciones", active="exact"),
                dbc.NavLink([html.I(className="bi bi-wallet2 me-2"), "Cuentas"], href="/cuentas", active="exact"),
                dbc.NavLink([html.I(className="bi bi-bullseye me-2"), "Metas"], href="/metas", active="exact"),
                dbc.NavLink([html.I(className="bi bi-graph-up me-2"), "Inversiones"], href="/inversiones", active="exact"),
                dbc.NavLink([html.I(className="bi bi-lightbulb me-2"), "Consejos"], href="/consejos", active="exact"),
            ],
            vertical=True,
            pills=True,
        ),
        
        html.Hr(className="sidebar-divider"),
        
        # --- SWITCH DE TEMA ---
        html.Div([
            dbc.Label("Modo Claro", html_for="theme-switch", className="text-muted small mb-1"),
            dbc.Switch(
                id="theme-switch",
                value=False, # False = Dark (Default), True = Light
                className="d-inline-block ms-2",
                persistence=True, 
                persistence_type='local'
            ),
        ], className="d-flex align-items-center justify-content-center mt-auto pb-4")
    ],
)

content = html.Div(id="page-content", className="content")

app.layout = html.Div([
    dcc.Location(id="url", refresh=False),
    dcc.Store(id="theme-store"), 
    sidebar,
    content
], id="main-container")


# ------------------------------------------------------------------------------
# CALLBACK CLIENTSIDE PARA CAMBIAR EL TEMA (SOLO COLORES)
# ------------------------------------------------------------------------------
# Corrección: Eliminamos la lógica que cambiaba el archivo .css de bootstrap.
# Ahora solo cambiamos el atributo 'data-theme' en el HTML.
# El archivo style.css se encarga de repintar los colores manteniendo la estructura.
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
    elif pathname == "/metas":
        return html.P("Página de Metas (en construcción)")
    elif pathname == "/inversiones":
        return html.P("Página de Inversiones (en construcción)")
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