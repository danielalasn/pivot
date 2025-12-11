# accounts.py
import dash
from dash import html, callback, Input, Output, no_update # FIX: Se añadió no_update
import dash_bootstrap_components as dbc
import backend.data_manager as dm

# Importación relativa (punto . significa "en esta misma carpeta")
from . import accounts_debit, accounts_credit

# --- LAYOUT DE RESUMEN (MINI DASHBOARD) ---
# accounts.py - Dentro de summary_layout

summary_layout = dbc.Row([
    dbc.Col(
        dbc.Card(
            dbc.CardBody([
                html.H6("Activos (Ahorros/Efectivo)", className="card-title text-success"),
                # El padding vertical (py-3) asegura el balance de altura con la tarjeta de Pasivos
                html.H3(id="summary-total-assets", className="card-value mb-0") 
            ]),
            className="metric-card"
        ),
        lg=6, md=6, sm=12, className="mb-4"
    ),
    dbc.Col(
        dbc.Card(
            dbc.CardBody([
                html.H6("Pasivos (Deuda Tarjetas)", className="card-title text-danger"),
                # SOLO MOSTRAMOS EL TOTAL DE DEUDA
                html.H3(id="summary-total-liabilities", className="card-value mb-0"), 
            ]),
            className="metric-card"
        ),
        lg=6, md=6, sm=12, className="mb-4"
    ),
], className="mb-4")

layout = dbc.Container([
    html.H2("Gestión de Productos Financieros", className="mb-4"),
    
    # CONTENEDOR DEL MINI-DASHBOARD
    summary_layout, 
    
    dbc.Tabs([
        dbc.Tab(accounts_debit.layout, label="Cuentas y Efectivo", tab_id="tab-debit"),
        dbc.Tab(accounts_credit.layout, label="Tarjetas de Crédito", tab_id="tab-credit"),
    ], active_tab="tab-debit", id="accounts-tabs")
    
], fluid=True, className="page-container")




# --- CALLBACKS para el Mini-Dashboard ---
# accounts.py - Callback update_account_summary

# pages/accounts.py
# pages/accounts.py

@callback(
    [Output("summary-total-assets", "children"),
     Output("summary-total-liabilities", "children")], 
    [Input("url", "pathname"), 
     Input("accounts-tabs", "active_tab"), 
     Input("deb-msg", "children"), 
     Input("inst-update-signal", "data")]
)
def update_account_summary(pathname, active_tab, deb_msg, inst_signal):
    if pathname != "/cuentas":
        return no_update, no_update 

    summary = dm.get_account_type_summary()
    
    # 1. VISUALIZACIÓN DE ACTIVOS
    total_assets = summary['TotalAssets']
    liquid = summary['LiquidAssets']
    reserve = summary['ReserveAssets']
    
    assets_display = html.Div([
        html.Span(f"${total_assets:,.2f}", className="fw-bold"),
        html.Br(),
        html.Small(
            f"Cuentas: ${liquid:,.2f} | Reserva: ${reserve:,.2f}", 
            className="text-muted", 
            style={"fontSize": "0.9rem", "fontWeight": "normal"}
        )
    ])
    
    # 2. VISUALIZACIÓN DE PASIVOS (Con Desglose)
    total_liabilities = summary['TotalLiabilities']
    immediate = summary['ImmediateDebt']
    installments = summary['InstallmentsDebt']
    
    liabilities_display = html.Div([
        html.Span(f"${total_liabilities:,.2f}", className="fw-bold"), # Número Grande
        html.Br(),
        html.Small(
            f"Exigible: ${immediate:,.2f} | Cuotas: ${installments:,.2f}", 
            className="text-muted", 
            style={"fontSize": "0.9rem", "fontWeight": "normal"}
        )
    ])
    
    return assets_display, liabilities_display