# accounts_credit.py
import dash
from dash import dcc, html, callback, Input, Output, State, no_update, ctx, ALL
import dash_bootstrap_components as dbc
import backend.data_manager as dm
from datetime import date
import calendar
import time
from utils import ui_helpers
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd

# --- HELPERS ---

def get_next_payment_date(day_of_month):
    today = date.today()
    try: candidate = date(today.year, today.month, day_of_month)
    except ValueError: candidate = date(today.year, today.month, calendar.monthrange(today.year, today.month)[1])
    if candidate < today:
        next_m, next_y = (today.month + 1, today.year) if today.month < 12 else (1, today.year + 1)
        try: candidate = date(next_y, next_m, day_of_month)
        except ValueError: candidate = date(next_y, next_m, calendar.monthrange(next_y, next_m)[1])
    return candidate

def calculate_total_installments_balance(account_id):
    df = dm.get_installments(account_id)
    if df.empty: return 0.0
    
    total_pending_value = 0.0
    for _, row in df.iterrows():
        tq = row['total_quotas']
        if tq > 0:
            annual_rate = row['interest_rate']
            amount = row['total_amount']
            
            # Método Francés simplificado para saldo pendiente
            if annual_rate > 0:
                i = annual_rate / 12 / 100
                n = tq
                denominator = ((1 + i) ** n) - 1
                if denominator != 0:
                    numerator = i * ((1 + i) ** n)
                    q_val = amount * (numerator / denominator)
                else:
                    q_val = amount / tq
            else:
                q_val = amount / tq
            
            rem_q = tq - row['paid_quotas']
            total_pending_value += q_val * rem_q
            
    return total_pending_value

def generate_installments_list(account_id):
    df = dm.get_installments(account_id)
    if df.empty:
        return html.Div([html.P("No hay financiamientos activos.", className="text-muted small fst-italic mb-2")], className="text-center py-3")
    
    items = []
    for _, row in df.iterrows():
        pq = row['paid_quotas']
        tq = row['total_quotas']
        pay_day = row.get('payment_day', 15)
        annual_rate = row['interest_rate'] 
        amount = row['total_amount']

        if tq > 0:
            if annual_rate > 0:
                i = annual_rate / 12 / 100
                n = tq
                denominator = ((1 + i) ** n) - 1
                if denominator != 0:
                    numerator = i * ((1 + i) ** n)
                    q_val = amount * (numerator / denominator)
                else:
                    q_val = amount / tq
            else:
                q_val = amount / tq
            total_debt_calculated = q_val * tq
        else:
            q_val = 0
            total_debt_calculated = amount

        rem_bal = q_val * (tq - pq)
        
        item = dbc.ListGroupItem([
            dbc.Row([
                dbc.Col([
                    html.H6(row['name'], className="mb-0 fw-bold"),
                    html.Small(f"Cuota {pq}/{tq} • Tasa {annual_rate}%", className="text-muted d-block"),
                    html.Small(f"Cobro: Día {pay_day}", className="text-info small fw-bold") 
                ], width=6),
                dbc.Col([
                    html.Div(f"Deuda Restante: ${rem_bal:,.2f}", className="text-end small fw-bold text-danger"),
                    html.Div(f"Cuota Fija: ${q_val:,.2f}", className="text-end small text-muted"),
                    html.Small(f"(Total Financ.: ${total_debt_calculated:,.2f})", className="text-end d-block text-muted", style={"fontSize": "0.7rem"})
                ], width=4),
                dbc.Col([
                    dbc.Button("✏️", id={'type': 'btn-edit-inst', 'index': row['id']}, color="light", size="sm", className="me-1 py-0 px-2"),
                    dbc.Button("✖", id={'type': 'btn-del-inst', 'index': row['id']}, color="light", size="sm", className="text-danger py-0 px-2")
                ], width=2, className="d-flex align-items-center justify-content-end px-0")
            ])
        ])
        items.append(item)
    return dbc.ListGroup(items, flush=True)

def generate_header_content(row, calculated_installments_total=None):
    limit = row['credit_limit']
    debt = row['current_balance']
    inst_pend = calculated_installments_total if calculated_installments_total is not None else row.get('installments_pending_total', 0.0)
    avail = limit - debt
    payable = debt - inst_pend
    if payable < 0: payable = 0

    pay_day = int(row['payment_day']) if row['payment_day'] else 1
    next_pay = get_next_payment_date(pay_day)
    d_left = (next_pay - date.today()).days
    d_str = f"{next_pay.strftime('%d-%m-%Y')} (en {d_left} días)"
    
    return html.Div([
        html.H2(f"${avail:,.2f}", className="text-success text-center mb-0"),
        html.P("Disponible", className="text-center text-muted mb-4"),
        dbc.Row([dbc.Col("Banco:", className="fw-bold text-end"), dbc.Col(row['bank_name'])]),
        dbc.Row([dbc.Col("Límite:", className="fw-bold text-end"), dbc.Col(f"${limit:,.2f}")]),
        html.Hr(),
        dbc.Row([dbc.Col("Deuda Total:", className="fw-bold text-end"), dbc.Col(f"${debt:,.2f}")]),
        dbc.Row([dbc.Col("En Cuotas:", className="fw-bold text-info text-end"), dbc.Col(f"${inst_pend:,.2f}", className="text-info")]),
        dbc.Row([dbc.Col("Exigible (A Pagar):", className="fw-bold text-danger text-end"), dbc.Col(f"${payable:,.2f}", className="text-danger")]),
        html.Hr(),
        dbc.Row([
            dbc.Col("Próximo Pago:", className="fw-bold text-end align-self-center"), 
            dbc.Col([
                html.Span(d_str, className="text-warning fw-bold me-2"),
            ], className="align-self-center"),
            
            # --- BOTÓN DE PAGAR TARJETA ---
            dbc.Col(
                dbc.Button("Pagar Tarjeta", id="btn-open-pay-card-modal", color="success", size="sm", className="fw-bold"),
                width="auto", className="align-self-center"
            )
        ]),
    ])

# --- MODALES ---

# Modal de Reserva (Abono Global)
abono_update_modal = dbc.Modal([
    dbc.ModalHeader(dbc.ModalTitle("Actualizar Reserva de Abono")),
    dbc.ModalBody([
        dbc.Label("Nuevo Saldo Total de Reserva ($)"),
        dbc.Input(id="abono-modal-input", type="number", min=0, step=1, className="mb-3", placeholder="Ej: 500.00"),
        html.Div(id="abono-modal-feedback", className="mt-2 text-center")
    ]),
    dbc.ModalFooter([
        dbc.Button("Cancelar", id="abono-modal-cancel", outline=True),
        dbc.Button("Guardar Reserva", id="abono-modal-confirm", color="success", className="ms-2"),
    ])
], id="abono-update-modal", is_open=False, centered=True, size="sm")

# Modal de Pago de Tarjeta (NUEVO)
card_payment_modal = dbc.Modal([
    dbc.ModalHeader("Pagar Tarjeta de Crédito"),
    dbc.ModalBody([
        dbc.Alert("Selecciona la fuente de fondos. Puedes usar una cuenta bancaria o descontar de tu 'Reserva de Abono'.", color="info", className="small mb-3"),
        
        dbc.Label("Monto a Pagar ($)"),
        dbc.Input(id="pay-card-amount", type="number", min=0, placeholder="0.00", className="mb-3 form-control-lg"),
        
        dbc.Label("Origen de los Fondos"),
        dcc.Dropdown(id="pay-card-source", placeholder="Seleccionar cuenta o reserva...", className="mb-3 text-dark"),
        
        html.Div(id="pay-card-feedback", className="mt-2 text-center")
    ]),
    dbc.ModalFooter([
        dbc.Button("Cancelar", id="btn-pay-card-cancel", outline=True),
        dbc.Button("Confirmar Pago", id="btn-pay-card-confirm", color="success", className="ms-2"),
    ])
], id="card-payment-modal", is_open=False, centered=True, size="sm", zIndex=1060) # zIndex alto para estar sobre el detalle

# Modal Borrar Financiamiento
confirm_inst_del_modal = dbc.Modal([
    dbc.ModalHeader(dbc.ModalTitle("Borrar Financiamiento")),
    dbc.ModalBody("¿Estás seguro de eliminar este item?"),
    dbc.ModalFooter([
        dbc.Button("Cancelar", id="btn-inst-del-cancel", className="ms-auto"),
        dbc.Button("Sí, Borrar", id="btn-inst-del-confirm", color="danger", className="ms-2"),
    ])
], id="delete-inst-confirm-modal", is_open=False, centered=True, zIndex=1080)

# Modal Gestión Financiamiento
inst_modal = dbc.Modal([
    dbc.ModalHeader(dbc.ModalTitle(id="inst-modal-title", children="Nuevo Financiamiento")),
    dbc.ModalBody([
        dbc.Label("Nombre del Producto"),
        dbc.Input(id="new-inst-name", placeholder="Ej. Televisor...", className="mb-2"),
        dbc.Label("Monto Total"),
        dbc.Input(id="new-inst-amount", type="number", className="mb-2"),
        dbc.Label("Tasa (%)"),
        dbc.Input(id="new-inst-rate", type="number", value=0, className="mb-2"),
        dbc.Row([
            dbc.Col([dbc.Label("Cuotas Totales"), dbc.Input(id="new-inst-total-q", type="number")], width=4),
            dbc.Col([dbc.Label("Pagadas"), dbc.Input(id="new-inst-paid-q", type="number", value=0)], width=4),
            dbc.Col([dbc.Label("Día Cobro"), dbc.Input(id="new-inst-day", type="number", placeholder="15")], width=4),
        ], className="mb-3"),
    ]),
    dbc.ModalFooter([
        dbc.Button("Cancelar", id="btn-inst-cancel", color="secondary", outline=True, className="me-auto"),
        dbc.Button("Guardar", id="btn-inst-save", color="success"),
    ])
], id="inst-modal", is_open=False, centered=True, backdrop="static", zIndex=1060)

# Modal Detalle Tarjeta (Padre)
detail_modal = dbc.Modal([
    dbc.ModalHeader(dbc.ModalTitle("Detalle de Tarjeta")),
    dbc.ModalBody([
        html.Div(id="cred-detail-header"),
        html.Hr(),
        dbc.Accordion([
            dbc.AccordionItem([
                dbc.Row([
                    dbc.Col(html.H6("Lista de Cuotas", className="mb-0 text-primary"), width=True),
                    dbc.Col(dbc.Button("+ Agregar", id="btn-show-add-install", color="primary", size="sm", outline=True), width="auto")
                ], className="align-items-center mb-3"),
                html.Div(id="cred-installments-list"),
            ], title="Ver Financiamientos / Cuotas", id="accordion-inst-item")
        ], start_collapsed=True, flush=True),
    ]),
    dbc.ModalFooter([
        dbc.Button("Editar Tarjeta", id="cred-btn-trigger-edit", color="info", className="me-auto"),
        dbc.Button("Eliminar Tarjeta", id="cred-btn-trigger-delete", color="danger"),
        dbc.Button("Cerrar", id="cred-btn-close-detail", color="secondary", outline=True, className="ms-2"),
    ])
], id="cred-detail-modal", is_open=False, centered=True, size="md", zIndex=1050)

# Modal Borrar Tarjeta
delete_card_modal = dbc.Modal([
    dbc.ModalHeader("Eliminar Tarjeta"),
    dbc.ModalBody("¿Seguro que deseas eliminar esta tarjeta permanentemente?", id="cred-modal-msg"),
    dbc.ModalFooter([
        dbc.Button("Cancelar", id="cred-btn-cancel-del", className="ms-auto"),
        dbc.Button("Sí, Eliminar", id="cred-btn-confirm-del", color="danger", className="ms-2"),
    ])
], id="cred-modal-delete", is_open=False, centered=True, zIndex=1070)


# --- LAYOUT PRINCIPAL ---
layout = dbc.Card([
    dbc.CardBody([
        # Stores
        dcc.Store(id='cred-editing-id', data=None),
        dcc.Store(id='cred-delete-id', data=None),
        dcc.Store(id='cred-viewing-id', data=None),
        dcc.Store(id='inst-editing-id', data=None), 
        dcc.Store(id='inst-delete-target-id', data=None),
        dcc.Store(id='inst-update-signal', data=0),
        dcc.Store(id='inst-save-success', data=0),

        ui_helpers.get_feedback_toast("global-credit-toast"),
        
        # Inclusión de Modales
        abono_update_modal,
        card_payment_modal,
        confirm_inst_del_modal,
        inst_modal,
        detail_modal,
        delete_card_modal,

        html.H5("Resumen Consolidado de Crédito", className="mb-3 text-danger"),
        dbc.Row(id="cred-dashboard-summary", className="mb-4"),

        dbc.Row([
            dbc.Col(
                dbc.Card(
                    dbc.CardBody([
                        html.H5("Reserva para Pago de Tarjeta (Abono)", className="card-title text-info"),
                        dbc.Row([
                            dbc.Col(html.P([html.B("Reserva para Pago de Tarjeta (Abono): "), html.Span(id="abono-account-balance-display", className="text-info fw-bold me-3")], className="mb-0"), width="auto"),
                            dbc.Col(dbc.Button("Actualizar Reserva", id="abono-btn-trigger-modal", color="info", size="sm", outline=True), width="auto"),
                        ], align="center", className="mb-2"),
                        html.Small("Este es el saldo total reservado. Se resta de tu deuda exigible.", className="text-muted d-block mb-4"),
                    ]), className="metric-card"
                ), lg=12, md=12, sm=12, className="mb-4"
            ),
        ]),

        dbc.Row([
            # Panel Izquierdo (Nueva Tarjeta)
            dbc.Col([
                html.H5("Nueva Tarjeta", className="mb-3 text-info"),
                dbc.Label("Nombre"), dbc.Input(id="cred-name", placeholder="Ej. Lifemiles...", className="mb-2"),
                dbc.Label("Banco"),
                dbc.Row([
                    dbc.Col(dbc.Select(id="cred-bank", options=[{"label": "BAC", "value": "BAC"}, {"label": "Cuscatlan", "value": "Cuscatlan"}, {"label": "Agricola", "value": "Agricola"}, {"label": "Davivienda", "value": "Davivienda"}, {"label": "Otro", "value": "Otros"}], value=None, placeholder="Seleccionar..."), width=12),
                    dbc.Col(dbc.Input(id="cred-bank-custom", placeholder="Otro...", style={"display": "none"}, className="mt-2"), width=12)
                ], className="mb-2"),
                dbc.Label("Límite"), dbc.Input(id="cred-limit", type="number", placeholder="5000", className="mb-2"),
                dbc.Row([dbc.Col([dbc.Label("Corte"), dbc.Input(id="cred-cut", type="number", placeholder="4")]), dbc.Col([dbc.Label("Pago"), dbc.Input(id="cred-pay", type="number", placeholder="20")])], className="mb-3"),
                html.Hr(),
                dbc.Label("Estado Inicial"),
                dbc.RadioItems(id="cred-mode", options=[{"label": "Monto Disponible", "value": "Available"}, {"label": "Deuda Total", "value": "Utilized"}], value="Available", inline=True, className="mb-2"),
                dbc.Input(id="cred-amount", type="number", placeholder="0.00", className="mb-3"),
                dbc.Button("Guardar Tarjeta", id="cred-btn-save", color="primary", className="w-100"),
                dbc.Button("Cancelar", id="cred-btn-cancel", color="secondary", outline=True, className="w-100 mt-2", style={"display": "none"}),
            ], md=5, className="border-end border-secondary pe-4"),

            # Panel Derecho (Lista Tarjetas)
            dbc.Col([
                html.H5("Mis Tarjetas", className="mb-3"),
                html.Div(id="cred-cards-container", className="d-grid gap-3", style={"maxHeight": "80vh", "overflowY": "auto"})
            ], md=7, className="ps-4")
        ])
    ])
])

# ==============================================================================
# CALLBACKS
# ==============================================================================

# 0. DASHBOARD CRÉDITO
@callback(Output("cred-dashboard-summary", "children"), [Input("url", "pathname"), Input("inst-update-signal", "data")])
def update_credit_dashboard(pathname, signal):
    if pathname != "/cuentas": return no_update
    summary = dm.get_credit_summary_data()
    limit = summary['total_limit']
    debt = summary['total_debt']
    inst_debt = summary['total_installments']
    abono_reserve = dm.get_credit_abono_reserve()
    
    if limit == 0: return dbc.Col(html.P("No hay límites de crédito registrados.", className="text-muted fst-italic"))
    
    available = limit - debt
    utilization_rate = (debt / limit) * 100 if limit > 0 else 0
    exigible_debt_gross = debt - inst_debt
    if exigible_debt_gross < 0: exigible_debt_gross = 0
    exigible_debt_net = exigible_debt_gross - abono_reserve
    if exigible_debt_net < 0: exigible_debt_net = 0 

    return [
        dbc.Col(dbc.Card(dbc.CardBody([
            html.H4("Límite Total vs. Utilizado", className="card-title"),
            dbc.Row([dbc.Col(html.P("Límite:", className="mb-0 text-muted"), width="auto"), dbc.Col(html.P(f"${limit:,.2f}", className="mb-0 text-white fw-bold text-end"), width="auto")], justify="between"),
            dbc.Progress([
                dbc.Progress(value=(100 - utilization_rate), label=f"{100 - utilization_rate:,.1f}%" if (100 - utilization_rate) > 0.1 else " ", bar=True, color="success"),
                dbc.Progress(value=utilization_rate, label=f"{utilization_rate:,.1f}%" if utilization_rate > 0.1 else " ", bar=True, color="danger"),
            ], className="mb-2"),
            dbc.Row([dbc.Col(html.P(f"Disponible: ${available:,.2f}", className="mb-0 text-success small"), width=6), dbc.Col(html.P(f"Utilizado: ${debt:,.2f}", className="mb-0 text-danger small text-end"), width=6)], justify="between")
        ]), className="data-card h-100"), md=8, className="mb-4"),
        
        dbc.Col(dbc.Card(dbc.CardBody([
            html.H4("Desglose Total de Deuda", className="card-title"),
            html.Hr(),
            dbc.Row([dbc.Col(html.P("Deuda Total:", className="text-muted fw-bold mb-1"), width=5), dbc.Col(html.P(f"${debt:,.2f}", className="text-white fw-bold mb-1 text-end"), width=7)]),
            dbc.Row([dbc.Col(html.Small("Cuotas:", className="text-info mb-1"), width=5), dbc.Col(html.Small(f"${inst_debt:,.2f}", className="text-info mb-1 text-end"), width=7)]),
            dbc.Row([dbc.Col(html.Small("Exigible NETO:", className="text-warning fw-bold mb-1"), width=5), dbc.Col(html.Small(f"${exigible_debt_net:,.2f}", className="text-warning fw-bold mb-1 text-end"), width=7)]),
            html.Small(f"Reserva Aplicada: ${abono_reserve:,.2f}", className="text-success d-block mt-3 text-end"),
        ]), className="data-card h-100"), md=4, className="mb-4"),
    ]

@callback(Output("cred-bank-custom", "style"), Input("cred-bank", "value"))
def cred_bank_vis(val): return {"display": "block"} if val == "Otros" else {"display": "none"}

@callback(Output("cred-cards-container", "children"), [Input("cred-viewing-id", "data"), Input("url", "pathname"), Input("inst-update-signal", "data")])
def cred_load_cards(v_id, url, signal):
    df = dm.get_accounts_by_category("Credit")
    if df.empty: return html.Div("No hay tarjetas registradas.", className="text-muted")
    cards = []
    for _, row in df.iterrows():
        limit = row['credit_limit']
        debt = row['current_balance']
        inst_pend = row.get('installments_pending_total', 0.0)
        avail = limit - debt
        payable = debt - inst_pend
        if payable < 0: payable = 0
        pay_day = int(row['payment_day']) if row['payment_day'] else 1
        d_left = (get_next_payment_date(pay_day) - date.today()).days
        p_txt = f"Pago en {d_left} días" if d_left > 1 else ("Pago mañana" if d_left == 1 else "¡Pagar Hoy!")
        p_cls = "text-warning" if d_left < 5 else "text-muted"
        if d_left == 0: p_cls = "text-danger fw-bold"

        debt_display = html.Div([
            html.Div([html.Span("Exigible: ", className="text-muted"), html.Span(f"${payable:,.2f}", className="fw-bold text-dark")], className="small"),
            html.Div([html.Span("En Cuotas: ", className="text-muted"), html.Span(f"${inst_pend:,.2f}", className="text-info")], className="small")
        ], className="text-end") if inst_pend > 0 else html.Div([html.Span("Deuda: ", className="text-muted"), html.Span(f"${debt:,.2f}", className="fw-bold text-danger")], className="small text-end")

        up = dbc.Button("⬆️", id={'type': 'cred-up', 'index': row['id']}, size="sm", color="link", className="p-0 text-decoration-none text-muted")
        down = dbc.Button("⬇️", id={'type': 'cred-down', 'index': row['id']}, size="sm", color="link", className="p-0 text-decoration-none text-muted")
        
        card = dbc.Card(dbc.CardBody([dbc.Row([
            dbc.Col([up, html.Div(style={"height": "2px"}), down], width="auto", className="d-flex flex-column border-end pe-2 me-2"),
            dbc.Col(html.Div([dbc.Row([
                dbc.Col(html.Div("💳", className="display-6"), width="auto", className="d-flex align-items-center pe-0"),
                dbc.Col([html.H5(row['name'], className="mb-0 fw-bold"), html.Small(row['bank_name'], className="text-muted d-block"), html.Small(p_txt, className=f"{p_cls} small")], className="d-flex flex-column justify-content-center"),
                dbc.Col([html.H4(f"${avail:,.2f}", className="mb-0 text-success text-end"), html.Small("Disponible", className="text-muted d-block text-end mb-1"), debt_display], width="auto", className="d-flex flex-column justify-content-center ms-auto")
            ])], id={'type': 'cred-card-item', 'index': row['id']}, n_clicks=0, style={"cursor": "pointer", "height": "100%", "width": "100%"}), className="flex-grow-1")
        ], className="g-0 align-items-center")]), className="data-card zoom-on-hover")
        cards.append(card)
    return cards

@callback(Output("inst-update-signal", "data", allow_duplicate=True), Input({'type': 'cred-up', 'index': ALL}, 'n_clicks'), Input({'type': 'cred-down', 'index': ALL}, 'n_clicks'), State("inst-update-signal", "data"), prevent_initial_call=True)
def cred_reorder(n_up, n_down, sig):
    if not ctx.triggered or not ctx.triggered[0]['value']: return no_update
    dm.change_account_order(ctx.triggered_id['index'], 'up' if ctx.triggered_id['type']=='cred-up' else 'down', "Credit")
    return (sig or 0) + 1

# --- MODAL DETALLE TARJETA ---
@callback(
    [Output("cred-detail-modal", "is_open"), Output("cred-detail-header", "children"), Output("cred-installments-list", "children"), Output("cred-viewing-id", "data"), Output("accordion-inst-item", "title")], 
    [Input({'type': 'cred-card-item', 'index': ALL}, 'n_clicks'), Input("cred-btn-close-detail", "n_clicks"), Input("cred-btn-trigger-edit", "n_clicks"), Input("cred-btn-trigger-delete", "n_clicks"), Input("inst-update-signal", "data")], 
    [State("cred-viewing-id", "data"), State("cred-detail-modal", "is_open")], prevent_initial_call=True
)
def cred_open_detail(n, close, edit, delete, signal, current_view_id, is_open):
    trig = ctx.triggered_id
    if trig in ["cred-btn-close-detail", "cred-btn-trigger-edit", "cred-btn-trigger-delete"]: return False, no_update, no_update, None, no_update
    target_id = current_view_id if trig == "inst-update-signal" and is_open and current_view_id else (trig['index'] if isinstance(trig, dict) and ctx.triggered[0]['value'] else None)

    if target_id:
        df = dm.get_accounts_by_category("Credit")
        try:
            row = df[df['id'] == target_id].iloc[0]
            real_install_total = calculate_total_installments_balance(target_id)
            header = generate_header_content(row, calculated_installments_total=real_install_total)
            return True, header, generate_installments_list(target_id), target_id, f"Ver Financiamientos ({len(dm.get_installments(target_id))} activos - Total: ${real_install_total:,.2f})"
        except: return False, no_update, no_update, None, no_update
    return no_update, no_update, no_update, no_update, no_update

# --- MODAL PAGO TARJETA (CALLBACKS) ---
# 1. Abrir/Cerrar Modal de Pago y Cargar Opciones
@callback(
    [Output("card-payment-modal", "is_open"),
     Output("pay-card-source", "options"),
     Output("pay-card-feedback", "children")],
    [Input("btn-open-pay-card-modal", "n_clicks"), 
     Input("btn-pay-card-cancel", "n_clicks")],
    State("cred-viewing-id", "data"),
    prevent_initial_call=True
)
def toggle_card_payment_modal(n_open, n_cancel, card_id):
    trig = ctx.triggered_id
    
    # Caso Cancelar
    if trig == "btn-pay-card-cancel":
        return False, no_update, ""
    
    # Caso Abrir: Validamos 'n_open'
    if trig == "btn-open-pay-card-modal" and n_open: 
        if card_id:
            # 🚨 CORRECCIÓN: Usamos directamete la lista del backend.
            # Ya no agregamos manualmente la Reserva ni la estrellita.
            options = dm.get_account_options()
            
            return True, options, ""
    
    return no_update, no_update, no_update


# 2. Procesar Pago de Tarjeta
# pages/accounts_credit.py (Callback 2)

# 2. Procesar Pago de Tarjeta
@callback(
    [Output("card-payment-modal", "is_open", allow_duplicate=True),
     Output("inst-update-signal", "data", allow_duplicate=True),
     Output("global-credit-toast", "is_open", allow_duplicate=True),
     Output("global-credit-toast", "children", allow_duplicate=True),
     Output("global-credit-toast", "icon", allow_duplicate=True),
     Output("pay-card-feedback", "children", allow_duplicate=True),
     Output("abono-account-balance-display", "children", allow_duplicate=True)], 
    Input("btn-pay-card-confirm", "n_clicks"),
    [State("pay-card-amount", "value"),
     State("pay-card-source", "value"),
     State("cred-viewing-id", "data"),
     State("inst-update-signal", "data")],
    prevent_initial_call=True
)
def process_card_payment(n_clicks, amount, source, card_id, signal):
    if not n_clicks: return no_update
    
    if not amount or float(amount) <= 0:
        return True, no_update, False, "", "", html.Span("Monto inválido.", className="text-danger"), no_update
    
    # YA NO VALIDAMOS 'source' OBLIGATORIAMENTE
    # Si source es None, el backend lo interpretará como "Origen Externo"
        
    success, msg = dm.process_card_payment(card_id, float(amount), source)
    
    if success:
        new_reserve_bal = dm.get_credit_abono_reserve()
        return False, (signal or 0) + 1, *ui_helpers.mensaje_alerta_exito("success", msg), "", f"${new_reserve_bal:,.2f}"
    else:
        return True, no_update, False, "", "", html.Span(msg, className="text-danger"), no_update
# --- GESTIÓN FINANCIAMIENTOS ---
@callback(
    [Output("inst-modal", "is_open"), Output("inst-modal-title", "children"), Output("new-inst-name", "value"), Output("new-inst-amount", "value"), Output("new-inst-rate", "value"), Output("new-inst-total-q", "value"), Output("new-inst-paid-q", "value"), Output("new-inst-day", "value"), Output("inst-editing-id", "data"), Output("delete-inst-confirm-modal", "is_open"), Output("inst-delete-target-id", "data")],
    [Input("btn-show-add-install", "n_clicks"), Input({'type': 'btn-edit-inst', 'index': ALL}, 'n_clicks'), Input({'type': 'btn-del-inst', 'index': ALL}, 'n_clicks'), Input("btn-inst-cancel", "n_clicks"), Input("inst-save-success", "data"), Input("btn-inst-del-cancel", "n_clicks"), Input("inst-update-signal", "data")],
    [State("cred-viewing-id", "data")], prevent_initial_call=True
)
def manage_inst_ui_logic(n_add, n_edit, n_del, n_cancel, save_sig, n_del_cancel, update_sig, acc_id):
    trig = ctx.triggered_id
    if trig in ["btn-inst-cancel", "inst-save-success"]: return False, "Nuevo Financiamiento", "", "", 0, "", 0, "", None, False, None
    if trig == "btn-inst-del-cancel" or trig == "inst-update-signal": return False, no_update, no_update, no_update, no_update, no_update, no_update, no_update, no_update, False, None
    if trig == "btn-show-add-install": return True, "Nuevo Financiamiento", "", "", 0, "", 0, "", None, False, None
    if isinstance(trig, dict) and trig['type'] == 'btn-edit-inst' and ctx.triggered[0]['value']:
        row = dm.get_installments(acc_id)[dm.get_installments(acc_id)['id'] == trig['index']].iloc[0]
        return True, "Editar Financiamiento", row['name'], row['total_amount'], row['interest_rate'], row['total_quotas'], row['paid_quotas'], row.get('payment_day', 15), row['id'], False, None
    if isinstance(trig, dict) and trig['type'] == 'btn-del-inst' and ctx.triggered[0]['value']: return False, no_update, no_update, no_update, no_update, no_update, no_update, no_update, no_update, True, trig['index']
    return no_update, no_update, no_update, no_update, no_update, no_update, no_update, no_update, no_update, no_update, no_update

@callback(
    [Output("inst-save-success", "data"), Output("inst-update-signal", "data", allow_duplicate=True), Output("global-credit-toast", "is_open", allow_duplicate=True), Output("global-credit-toast", "children", allow_duplicate=True), Output("global-credit-toast", "icon", allow_duplicate=True)],
    [Input("btn-inst-save", "n_clicks"), Input("btn-inst-del-confirm", "n_clicks"), Input("cred-btn-save", "n_clicks"), Input("cred-btn-confirm-del", "n_clicks")],
    [State("cred-viewing-id", "data"), State("inst-editing-id", "data"), State("new-inst-name", "value"), State("new-inst-amount", "value"), State("new-inst-rate", "value"), State("new-inst-total-q", "value"), State("new-inst-paid-q", "value"), State("new-inst-day", "value"), State("inst-update-signal", "data"), State("inst-delete-target-id", "data"), State("cred-name", "value"), State("cred-bank", "value"), State("cred-bank-custom", "value"), State("cred-limit", "value"), State("cred-cut", "value"), State("cred-pay", "value"), State("cred-mode", "value"), State("cred-amount", "value"), State("cred-editing-id", "data"), State("cred-delete-id", "data")],
    prevent_initial_call=True
)
def global_save_delete_handler(n_save, n_del, n_card_save, n_card_del, acc_id, inst_id, name, amt, rate, tq, pq, pday, sig, del_id, cn, cb, cbc, cl, cc, cp, cm, ca, ce_id, cd_id):
    trig = ctx.triggered_id
    sig = (sig or 0) + 1
    if trig == "btn-inst-del-confirm": 
        dm.delete_installment(del_id)
        return no_update, sig, *ui_helpers.mensaje_alerta_exito("success", "Eliminado")
    if trig == "btn-inst-save":
        if not name or not amt: return no_update, no_update, *ui_helpers.mensaje_alerta_exito("danger", "Faltan datos")
        day = int(pday) if pday else 15
        if inst_id: dm.update_installment(inst_id, name, float(amt), float(rate or 0), int(tq), int(pq or 0), day)
        else: dm.add_installment(acc_id, name, float(amt), float(rate or 0), int(tq), int(pq or 0), day)
        return int(time.time()), sig, *ui_helpers.mensaje_alerta_exito("success", "Guardado")
    if trig == "cred-btn-save":
        if not cn or not cl: return no_update, no_update, *ui_helpers.mensaje_alerta_exito("danger", "Faltan datos")
        bf = cbc if cb == "Otros" else (cb if cb else "-")
        bal = (float(ca) if ca else 0) if cm == "Utilized" else (float(cl) - (float(ca) if ca else 0))
        if ce_id: dm.update_account(ce_id, cn, "Credit", bal, bf, float(cl), cp, cc)
        else: dm.add_account(cn, "Credit", bal, bf, float(cl), cp, cc)
        return no_update, sig, *ui_helpers.mensaje_alerta_exito("success", "Guardado")
    if trig == "cred-btn-confirm-del":
        dm.delete_account(cd_id)
        return no_update, sig, *ui_helpers.mensaje_alerta_exito("success", "Eliminada")
    return no_update, no_update, no_update, no_update, no_update

# Callbacks auxiliares de tarjeta
@callback([Output("cred-modal-delete", "is_open"), Output("cred-delete-id", "data")], [Input("cred-btn-trigger-delete", "n_clicks"), Input("cred-btn-cancel-del", "n_clicks"), Input("cred-btn-confirm-del", "n_clicks")], [State("cred-viewing-id", "data")], prevent_initial_call=True)
def cred_del_modal(t, c, conf, vid): return (True, vid) if ctx.triggered_id == "cred-btn-trigger-delete" else (False, no_update)

@callback(Output("cred-editing-id", "data", allow_duplicate=True), Input("cred-btn-close-detail", "n_clicks"), prevent_initial_call=True)
def cred_clean_id(n): return None

@callback([Output("cred-name", "value"), Output("cred-bank", "value"), Output("cred-bank-custom", "value"), Output("cred-limit", "value"), Output("cred-cut", "value"), Output("cred-pay", "value"), Output("cred-amount", "value"), Output("cred-mode", "value"), Output("cred-btn-save", "children"), Output("cred-btn-cancel", "style"), Output("cred-editing-id", "data", allow_duplicate=True)], [Input("cred-btn-trigger-edit", "n_clicks"), Input("cred-btn-cancel", "n_clicks"), Input("cred-btn-save", "n_clicks")], [State("cred-viewing-id", "data")], prevent_initial_call=True)
def cred_populate(e, c, s, viewed_id):
    trig = ctx.triggered_id
    if trig in ["cred-btn-cancel", "cred-btn-save"]: return "", None, "", "", "", "", "", "Available", "Guardar Tarjeta", {"display": "none"}, None
    if trig == "cred-btn-trigger-edit" and viewed_id:
        row = dm.get_accounts_by_category("Credit")[dm.get_accounts_by_category("Credit")['id']==viewed_id].iloc[0]
        bank_sel = row['bank_name'] if row['bank_name'] in ["BAC","Cuscatlan","Agricola","Davivienda"] else "Otros"
        return row['name'], bank_sel, (row['bank_name'] if bank_sel=="Otros" else ""), row['credit_limit'], row['cutoff_day'], row['payment_day'], (row['credit_limit']-row['current_balance']), "Available", "Actualizar", {"display": "block"}, viewed_id
    return no_update

# Abono Display
@callback(Output("abono-account-balance-display", "children"), [Input("url", "pathname"), Input("inst-update-signal", "data")])
def update_abono_display(path, sig): return f"${dm.get_credit_abono_reserve():,.2f}" if path == "/cuentas" else no_update

@callback(Output("abono-update-modal", "is_open"), Output("abono-modal-input", "value"), Input("abono-btn-trigger-modal", "n_clicks"), State("abono-account-balance-display", "children"), prevent_initial_call=True)
def open_abono_modal(n, val):
    try: amt = float(val.replace('$', '').replace(',', ''))
    except: amt = 0.0
    return True, amt

@callback(Output("abono-modal-feedback", "children"), Output("abono-account-balance-display", "children", allow_duplicate=True), Output("abono-update-modal", "is_open", allow_duplicate=True), Output("inst-update-signal", "data", allow_duplicate=True), Input("abono-modal-confirm", "n_clicks"), Input("abono-modal-cancel", "n_clicks"), State("abono-modal-input", "value"), prevent_initial_call=True)
def handle_abono_save(conf, cancel, amt):
    if ctx.triggered_id == "abono-modal-cancel": return "", no_update, False, no_update
    if not amt or float(amt) < 0: return html.Span("Inválido", className="text-danger"), no_update, no_update, no_update
    dm.update_credit_abono_reserve(float(amt))
    return "", f"${float(amt):,.2f}", False, 0