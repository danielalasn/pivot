# pages/investments.py
import dash
from dash import html
import dash_bootstrap_components as dbc
from . import investments_stocks # Importamos el archivo que crearemos abajo

layout = dbc.Container([
    html.H2("Portafolio de Inversiones", className="mb-4"),
    
    dbc.Tabs([
        dbc.Tab(investments_stocks.layout, label="Bolsa de Valores (Stocks)", tab_id="tab-stocks"),
        dbc.Tab(html.Div("Crypto (Próximamente)", className="p-4 text-muted"), label="Criptomonedas", tab_id="tab-crypto"),
    ], active_tab="tab-stocks")
    
], fluid=True, className="page-container")