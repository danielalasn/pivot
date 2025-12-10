# pages/distribution/distribution.py
import dash
from dash import html
import dash_bootstrap_components as dbc
from . import fixed_costs, savings, revenue, stabilizer

# LAYOUT DEL CONTENEDOR PRINCIPAL
layout = dbc.Container([
    html.H2("Distribución de Ingresos", className="mb-4"),

    dbc.Tabs([
        dbc.Tab(revenue.layout, label="Reparto de Ingreso", tab_id="tab-distribution"),

        dbc.Tab(fixed_costs.layout, label="Costos Fijos", tab_id="tab-fixed-costs"),

        dbc.Tab(savings.layout, label="Metas de Ahorro", tab_id="tab-savings"),

        dbc.Tab(stabilizer.layout, label="Estabilizador (Salario)", tab_id="tab-stabilizer"),
        
    ], active_tab="tab-distribution", id="distribution-tabs")

], fluid=True, className="page-container")