# pages/investments/investments.py
import dash
from dash import dcc, html, callback, Input, Output, State, no_update, ctx 
import dash_bootstrap_components as dbc

# Importar los layouts de las subpáginas
# pages/investments/investments.py

from . import investments_assets, investments_sales_analysis, investments_transactions_history # <-- IMPORTAR NUEVOS

layout = dbc.Container([
    html.H2("Portafolio de Inversiones", className="mb-4"),
    
    dbc.Tabs([
        dbc.Tab(investments_assets.layout, label="Activos Vivos", tab_id="tab-assets"),
        # 🚨 NUEVA PESTAÑA DE ANÁLISIS
        dbc.Tab(investments_sales_analysis.layout, label="Análisis P/L (Ventas)", tab_id="tab-analysis"), 
        # 🚨 NUEVA PESTAÑA DE HISTORIAL
        dbc.Tab(investments_transactions_history.layout, label="Historial Detallado", tab_id="tab-history"),
    ], active_tab="tab-assets", id="investments-tabs")
    
], fluid=True, className="page-container")