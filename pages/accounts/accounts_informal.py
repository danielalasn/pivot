# pages/accounts/accounts_informal.py

import dash
from dash import dcc, html, callback, Input, Output
import dash_bootstrap_components as dbc
import backend.data_manager as dm
from dash import no_update

layout = dbc.Container([
    html.H3("Resumen de Deudas y Cobros Informales", className="mb-4"),
    
    # Fila del Dashboard (donde se renderea el contenido)
    dbc.Row(id="informal-dashboard-summary", className="mb-4"),

], fluid=True, className="page-container")


# Callback para actualizar el Dashboard
@callback(
    Output("informal-dashboard-summary", "children"),
    Input("url", "pathname"),
    # FIX: Usamos "deb-msg" (el div de mensaje en accounts_debit.py) como trigger de cambio de cuenta.
    Input("deb-msg", "children"), 
    Input("inst-update-signal", "data"), 
)
def update_informal_dashboard(pathname, deb_msg_content, inst_signal):
    if pathname != "/cuentas":
        return no_update

    # 1. Obtener Datos (LLAMADA UNIFICADA)
    # 🚨 ANTES:
    # informal_debt, informal_collectible = dm.get_informal_summary()
    # credit_exigible_net = dm.get_net_exigible_credit_debt()
    # total_gross_debt = informal_debt + credit_exigible_net
    # net_exposure = total_gross_debt - informal_collectible
    # informal_net_balance = informal_collectible - informal_debt

    # ✅ AHORA:
    summary = dm.get_full_debt_summary()
    
    informal_debt = summary['informal_debt']
    informal_collectible = summary['informal_collectible']
    net_exposure = summary['net_exposure']
    informal_net_balance = summary['informal_net_balance']
    total_gross_debt = summary['total_gross_debt']

    
    # Determinar el color para CARD 2 (Balance Neto Informal)
    if informal_net_balance > 0:
        net_color = "text-success"
        net_icon = "bi bi-arrow-up-circle-fill me-2"
    elif informal_net_balance < 0:
        net_color = "text-danger"
        net_icon = "bi bi-arrow-down-circle-fill me-2"
    else:
        net_color = "text-primary"
        net_icon = "bi bi-check-circle-fill me-2"

    return [
        # CARD 1: Exposición de Deuda Total (Deuda - Cobros)
        dbc.Col(
            dbc.Card(
                dbc.CardBody([
                    html.H5("Exposición Neta a Deuda", className="card-title text-warning"),
                    html.H2(f"${net_exposure:,.2f}", className=f"card-value {'text-danger' if net_exposure > 0 else 'text-success'} mb-3"),
                    html.Small("Detalle:", className="d-block text-muted"),
                    html.Ul([
                        html.Li(f"Deuda Total (Informal + Crédito Exigible): ${total_gross_debt:,.2f}", className="mb-1"),
                        html.Li(f"Menos: Total Cobros Pendientes (a mi favor): -${informal_collectible:,.2f}", className="text-success"),
                    ], className="list-unstyled small ps-3")
                ]),
                className="metric-card h-100"
            ),
            lg=6, md=12, className="mb-4"
        ),

        # CARD 2: Saldo Neto Informal
        dbc.Col(
            dbc.Card(
                dbc.CardBody([
                    html.H5("Saldo Neto de Cuentas Informales", className="card-title"),
                    html.H2([
                        html.I(className=net_icon),
                        f"${informal_net_balance:,.2f}"
                    ], className=f"card-value {net_color} mb-3"),
                    html.Small("Componentes:", className="d-block text-muted"),
                    html.Ul([
                        html.Li(f"Cobros a mi favor: ${informal_collectible:,.2f}", className="text-success mb-1"),
                        html.Li(f"Deudas mías: -${informal_debt:,.2f}", className="text-danger"),
                    ], className="list-unstyled small ps-3")
                ]),
                className="metric-card h-100"
            ),
            lg=6, md=12, className="mb-4"
        ),
    ]