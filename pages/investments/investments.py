<<<<<<< HEAD
# pages/investments/investments.py
import dash
from dash import html
import dash_bootstrap_components as dbc

# --- IMPORTACIÓN DE LOS SUB-MÓDULOS ---
# Importamos los layouts específicos que has definido en los otros archivos
from . import investments_assets
from . import investments_sales_analysis
from . import investments_transactions_history 

# --- LAYOUT PRINCIPAL ---
layout = dbc.Container([
    
    # 1. Título de la Sección
    html.H2("Portafolio de Inversiones", className="mb-4"),
    
    # 2. Sistema de Pestañas (Tabs)
    dbc.Tabs([
        
        # PESTAÑA 1: ACTIVOS VIVOS
        # Carga el layout de 'investments_assets.py' (Dashboard, Cards, Modals de Compra/Venta)
        dbc.Tab(
            investments_assets.layout, 
            label="Activos Vivos", 
            tab_id="tab-assets"
        ),

        # PESTAÑA 2: ANÁLISIS P/L
        # Carga el layout de 'investments_sales_analysis.py' (Gráficos de barras, Pivot Table)
        dbc.Tab(
            investments_sales_analysis.layout, 
            label="Análisis P/L (Ventas)", 
            tab_id="tab-analysis"
        ), 
        
        # PESTAÑA 3: HISTORIAL
        # Carga el layout de 'investments_transactions_history.py' (Tabla detallada de transacciones)
        dbc.Tab(
            investments_transactions_history.layout, 
            label="Historial Detallado", 
            tab_id="tab-history"
        ),

    ], active_tab="tab-assets", id="investments-tabs")
    
=======
# pages/investments/investments.py
import dash
from dash import html
import dash_bootstrap_components as dbc

# --- IMPORTACIÓN DE LOS SUB-MÓDULOS ---
# Importamos los layouts específicos que has definido en los otros archivos
from . import investments_assets
from . import investments_sales_analysis
from . import investments_transactions_history 

# --- LAYOUT PRINCIPAL ---
layout = dbc.Container([
    
    # 1. Título de la Sección
    html.H2("Portafolio de Inversiones", className="mb-4"),
    
    # 2. Sistema de Pestañas (Tabs)
    dbc.Tabs([
        
        # PESTAÑA 1: ACTIVOS VIVOS
        # Carga el layout de 'investments_assets.py' (Dashboard, Cards, Modals de Compra/Venta)
        dbc.Tab(
            investments_assets.layout, 
            label="Activos Vivos", 
            tab_id="tab-assets"
        ),

        # PESTAÑA 2: ANÁLISIS P/L
        # Carga el layout de 'investments_sales_analysis.py' (Gráficos de barras, Pivot Table)
        dbc.Tab(
            investments_sales_analysis.layout, 
            label="Análisis P/L (Ventas)", 
            tab_id="tab-analysis"
        ), 
        
        # PESTAÑA 3: HISTORIAL
        # Carga el layout de 'investments_transactions_history.py' (Tabla detallada de transacciones)
        dbc.Tab(
            investments_transactions_history.layout, 
            label="Historial Detallado", 
            tab_id="tab-history"
        ),

    ], active_tab="tab-assets", id="investments-tabs")
    
>>>>>>> b74f1b0a886c27181c8264a954a4baf9f2b71029
], fluid=True, className="page-container")