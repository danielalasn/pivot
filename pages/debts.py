<<<<<<< HEAD
# pages/debts.py
import dash
from dash import dcc, html, callback, Input, Output, State, no_update, ctx, ALL
from dash import dash_table
import dash_bootstrap_components as dbc
from datetime import date
import backend.data_manager as dm
from utils import ui_helpers
import time 

# -----------------------------------------------------------------------------
# 1. FUNCIONES AUXILIARES (Solo lógica visual)
# -----------------------------------------------------------------------------

def render_summary_cards():
    """Genera las tarjetas de resumen (Calculadas dinámicamente)."""
    # 1. OBTENER DATOS (Ahora filtrados por usuario gracias a data_manager)
    try:
        summary = dm.get_full_debt_summary()
        
        informal_debt = summary['informal_debt']
        informal_collectible = summary['informal_collectible']
        net_exposure = summary['net_exposure']
        informal_net_balance = summary['informal_net_balance']
        credit_exigible_net = summary['credit_exigible_net']
        
        # Recalcular receivables/payables crudos para visualización si es necesario
        # O confiar en el resumen. Para los badges usamos el desglose:
        
        # --- LÓGICA VISUAL ---
        if net_exposure > 0:
            exposure_color = "text-danger"
            exposure_title = "Deuda Neta Real (A Pagar)"
        elif net_exposure < 0:
            exposure_color = "text-success"
            exposure_title = "Excedente de Liquidez Real"
            net_exposure = abs(net_exposure)
        else:
            exposure_color = "text-primary"
            exposure_title = "Punto de Equilibrio"

        if informal_net_balance > 0:
            net_icon = "bi bi-arrow-up-circle-fill me-2"
            informal_color = "text-success"
        elif informal_net_balance < 0:
            net_icon = "bi bi-arrow-down-circle-fill me-2"
            informal_color = "text-danger"
        else:
            net_icon = "bi bi-check-circle-fill me-2"
            informal_color = "text-muted"

        return [
            # TARJETA 1
            dbc.Col(dbc.Card(dbc.CardBody([
                html.H5(exposure_title, className="card-title text-muted small text-uppercase fw-bold"),
                html.H2(f"${net_exposure:,.2f}", className=f"card-value {exposure_color} mb-3 fw-bold"),
                html.Div([
                    dbc.Row([dbc.Col("Exigible TC (Neto):", className="text-muted small"), dbc.Col(f"${credit_exigible_net:,.2f}", className="text-end small fw-bold")]),
                    dbc.Row([dbc.Col("Posición Informal:", className="text-muted small"), dbc.Col(f"{'-' if informal_net_balance > 0 else '+'}${abs(informal_net_balance):,.2f}", className=f"text-end small fw-bold {informal_color}")]),
                ], className="border-top pt-2 mt-2")
            ]), className="metric-card h-100 shadow-sm border-0"), lg=6, md=12, className="mb-4"),
            
            # TARJETA 2
            dbc.Col(dbc.Card(dbc.CardBody([
                html.H5("Posición Informal (IOU)", className="card-title text-muted small text-uppercase fw-bold"),
                html.H2([html.I(className=net_icon), f"${abs(informal_net_balance):,.2f}"], className=f"card-value {informal_color} mb-3"),
                html.Div([
                    html.Span([html.I(className="bi bi-box-arrow-in-down me-1"), f"Me deben: ${informal_collectible:,.2f}"], className="badge bg-success bg-opacity-10 text-success me-2 p-2"),
                    html.Span([html.I(className="bi bi-box-arrow-up-right me-1"), f"Yo debo: ${informal_debt:,.2f}"], className="badge bg-danger bg-opacity-10 text-danger p-2")
                ], className="d-flex justify-content-center")
            ]), className="metric-card h-100 shadow-sm border-0"), lg=6, md=12, className="mb-4"),
        ]
    except Exception as e:
        return html.Div(f"Error cargando resumen: {e}", className="text-danger")


def generate_iou_table(dataframe):
    """Genera la tabla visual."""
    if dataframe.empty:
        return html.Div("No hay cuentas pendientes registradas.", className="text-muted fst-italic text-center py-4")
        
    dataframe = dataframe.copy()
    if 'status' in dataframe.columns:
        dataframe = dataframe[dataframe['status'] != 'Paid']
    else:
        dataframe = dataframe[dataframe['current_amount'].abs() > 0.01]

    if dataframe.empty:
        return html.Div("¡Todo al día! No tienes cuentas pendientes.", className="text-success fst-italic text-center py-4")

    dataframe['action'] = "ℹ️"
    dataframe['tipo_visual'] = dataframe['type'].apply(lambda x: "🟢 Me deben" if x == 'Receivable' else "🔴 Yo debo")
    
    return dash_table.DataTable(
        id='iou-data-table',
        data=dataframe.to_dict('records'),
        style_table={'overflowX': 'auto', 'minWidth': '100%', 'maxHeight': '32vh', 'overflowY': 'auto'},
        fixed_rows={'headers': True}, 
        columns=[
            {"name": "ID", "id": "id", "deletable": False, "selectable": False}, 
            {"name": "Condición", "id": "tipo_visual"}, 
            {"name": "Persona/Entidad", "id": "person_name"}, 
            {"name": "Concepto", "id": "name"},
            {"name": "Saldo Pendiente", "id": "current_amount", "type": "numeric", "format": {"specifier": "$,.2f"}},
            {"name": "Info", "id": "action", "deletable": False, "selectable": False}
        ],
        style_header={'backgroundColor': '#333', 'color': 'white', 'fontWeight': 'bold'},
        style_header_conditional=[{'if': {'column_id': 'id'}, 'display': 'none'}],
        style_data={'backgroundColor': '#1E1E1E', 'color': '#E0E0E0'},
        style_data_conditional=[
            {'if': {'column_id': 'id'}, 'display': 'none'},
            {'if': {'filter_query': '{type} = "Receivable"'}, 'backgroundColor': 'rgba(0, 100, 0, 0.3)', 'color': '#e8f5e9'},
            {'if': {'filter_query': '{type} = "Payable"'}, 'backgroundColor': 'rgba(100, 0, 0, 0.3)', 'color': '#ffebee'},
            {'if': {'column_id': 'action'}, 'textAlign': 'center', 'cursor': 'pointer', 'fontWeight': 'bold', 'color': '#33b5e5'}, 
        ],
        style_cell={'border': '1px solid #444', 'padding': '10px'},
        page_action='none', page_size=9999,     
    )

# -----------------------------------------------------------------------------
# 2. DEFINICIÓN DE MODALES (Igual que antes)
# -----------------------------------------------------------------------------
pay_full_confirm_modal = dbc.Modal([
    dbc.ModalHeader(dbc.ModalTitle("Confirmar Pago Total"), className="bg-danger text-white"),
    dbc.ModalBody([
        html.H4("¿Estás seguro?", className="text-center mb-3"),
        html.P("Esto marcará la deuda como completamente pagada.", className="text-center"),
    ]),
    dbc.ModalFooter([
        dbc.Button("Cancelar", id="btn-cancel-confirm-full", outline=True, className="me-auto"),
        dbc.Button("¡Sí, Pagar Todo!", id="btn-really-pay-full", color="success", className="fw-bold"),
    ])
], id="pay-full-confirm-modal", is_open=False, centered=True, size="sm", backdrop="static")

payment_modal = dbc.Modal([
    dbc.ModalHeader("Registrar Abono o Pago"),
    dbc.ModalBody([
        html.Div([html.Small("Saldo Pendiente Actual:", className="text-muted d-block"), html.H3(id="pay-modal-current-balance", className="text-primary fw-bold")], className="text-center mb-4 p-2 border rounded bg-light bg-opacity-10"),
        dbc.Label("Monto a Abonar"),
        dbc.Input(id="pay-modal-amount", type="number", min=0, placeholder="0.00", className="mb-3 form-control-lg"),
        dbc.Label("Cuenta de Origen/Destino"),
        dcc.Dropdown(id="pay-modal-account", placeholder="Seleccionar cuenta...", className="mb-4 text-dark"),
        dbc.Row([
            dbc.Col(dbc.Button("Abonar Cantidad", id="btn-confirm-partial-pay", color="warning", className="w-100"), width=6),
            dbc.Col(dbc.Button("✅ Pagar Todo", id="btn-confirm-full-pay", color="success", className="w-100"), width=6),
        ], className="g-2"),
        html.Div(id="pay-modal-msg", className="mt-3 text-center")
    ]),
    dbc.ModalFooter([dbc.Button("Cancelar", id="btn-cancel-pay-modal", outline=True, size="sm")])
], id="iou-payment-modal", is_open=False, centered=True, size="md")

detail_modal = dbc.Modal([
    dbc.ModalHeader(dbc.ModalTitle("Detalle de Cuenta")),
    dbc.ModalBody([
        dcc.Store(id="iou-detail-id-store"),
        dbc.Row([
            dbc.Col([dbc.Label("Tipo", className="small fw-bold mb-0"), dbc.RadioItems(id="iou-detail-type", options=[{"label": "Cobro", "value": "Receivable"}, {"label": "Deuda", "value": "Payable"}], inline=True, className="small")], width=7),
            dbc.Col([dbc.Label("Estado", className="small fw-bold mb-0"), dbc.Select(id="iou-detail-status", options=[{"label": "Pendiente", "value": "Pending"}, {"label": "Pagado", "value": "Paid"}], size="sm", disabled=True)], width=5),
        ], className="mb-2 align-items-center"),
        dbc.Row([dbc.Col([dbc.Label("Persona/Entidad", className="small mb-0"), dbc.Input(id="iou-detail-person-name", size="sm", disabled=True)], width=6), dbc.Col([dbc.Label("Concepto", className="small mb-0"), dbc.Input(id="iou-detail-name", size="sm", disabled=True)], width=6)], className="mb-2"),
        dbc.Row([dbc.Col([dbc.Label("Monto Original", className="small mb-0"), dbc.Input(id="iou-detail-amount", type="number", size="sm", disabled=True)], width=6), dbc.Col([dbc.Label("Saldo Pendiente", className="small mb-0 text-warning fw-bold"), dbc.Input(id="iou-detail-current-amount", type="number", size="sm", className="fw-bold text-warning", disabled=True)], width=6)], className="mb-2"),
        dbc.Row([dbc.Col([dbc.Label("Fecha Límite", className="small mb-0"), dcc.DatePickerSingle(id='iou-detail-due-date', display_format='YYYY-MM-DD', className='d-block small-date-picker', disabled=True)], width=5), dbc.Col([dbc.Label("Notas", className="small mb-0"), dbc.Textarea(id="iou-detail-description", rows=1, size="sm", disabled=True)], width=7)], className="mb-3"),
        html.Div(id="iou-detail-msg", className="text-center small")
    ]),
    dbc.ModalFooter([
        dbc.Button("💰 Registrar Pago", id="btn-open-payment-modal", color="primary", className="me-auto"),
        dbc.Button("Editar", id="iou-btn-edit-mode", color="info", outline=True, size="sm", className="me-1"),
        dbc.Button("Guardar", id="iou-btn-save", color="success", size="sm", className="me-1", style={'display': 'none'}),
        dbc.Button("Borrar", id="iou-btn-trigger-delete", color="danger", outline=True, size="sm", className="me-1"),
        dbc.Button("Cerrar", id="iou-btn-close-detail", color="secondary", size="sm"),
    ], className="d-flex justify-content-between align-items-center py-2")
], id="iou-detail-modal", is_open=False, size="md", centered=True)

delete_modal = dbc.Modal([
    dbc.ModalHeader("Confirmar Eliminación"),
    dbc.ModalBody("¿Eliminar permanentemente?"),
    dbc.ModalFooter([dbc.Button("Cancelar", id="iou-btn-del-cancel", outline=True, size="sm"), dbc.Button("Sí, Borrar", id="iou-btn-del-confirm", color="danger", size="sm")])
], id="iou-delete-modal", is_open=False, centered=True, size="sm")


# -----------------------------------------------------------------------------
# 3. LAYOUT PRINCIPAL (VACÍO INICIALMENTE)
# -----------------------------------------------------------------------------
layout = dbc.Container([
    dcc.Store(id='iou-viewing-id', data=None),
    dcc.Store(id='iou-edit-signal', data=0), 
    ui_helpers.get_feedback_toast("global-iou-toast"),
    
    detail_modal, payment_modal, pay_full_confirm_modal, delete_modal,

    html.H2("Deudas y Cobros (IOU)", className="mb-4"),
    
    # 🚨 CAMBIO: Los hijos inician con Spinner, se llenan vía callback
    dbc.Row(id="iou-summary-row", children=[dbc.Spinner(color="primary")], className="mb-4"),

    dbc.Row([
        # Formulario
        dbc.Col([
            dbc.Card([
                dbc.CardHeader("Nuevo Registro"),
                dbc.CardBody([
                    dbc.RadioItems(id="iou-type", options=[{"label": "Me deben", "value": "Receivable"}, {"label": "Yo debo", "value": "Payable"}], value="Receivable", inline=True, className="mb-2 small"),
                    dbc.Row([dbc.Col(dbc.Input(id="iou-person-name", placeholder="Persona/Entidad", size="sm"), width=6), dbc.Col(dbc.Input(id="iou-name", placeholder="Concepto", size="sm"), width=6)], className="mb-2 g-2"),
                    dbc.Row([dbc.Col(dbc.Input(id="iou-amount", placeholder="Monto $", type="number", size="sm"), width=6), dbc.Col(dcc.DatePickerSingle(id='iou-due-date', placeholder='Fecha Límite', display_format='YYYY-MM-DD', className='d-block w-100 small-date-picker'), width=6)], className="mb-3 g-2"),
                    dbc.Button("Registrar", id="btn-add-iou", color="primary", size="sm", className="w-100"),
                    html.Div(id="msg-add-iou", className="mt-1 text-center small")
                ])
            ], className="data-card mb-3")
        ], lg=4, md=12),

        # Tabla
        # 🚨 CAMBIO: El body inicia con Spinner, se llena vía callback
        dbc.Col([
            dbc.Card([
                dbc.CardHeader("Listado de Pendientes"),
                dbc.CardBody(id="iou-table-container", children=[dbc.Spinner(color="primary")], style={"padding": "0"}) 
            ], className="data-card")
        ], lg=8, md=12)
    ])
], fluid=True, className="page-container")


# -----------------------------------------------------------------------------
# 4. CALLBACKS
# -----------------------------------------------------------------------------

# 🚨 NUEVO CALLBACK DE CARGA INICIAL (Este es el que arregla el problema)
@callback(
    [Output("iou-summary-row", "children"),
     Output("iou-table-container", "children")],
    [Input("url", "pathname")],
    prevent_initial_call=False 
)
def load_iou_data_on_start(pathname):
    if pathname != "/deudas":
        return no_update, no_update
        
    # Ahora sí, al ejecutarse dentro del callback, dm.get_iou_df() usará el usuario logueado
    df = dm.get_iou_df()
    table = generate_iou_table(df)
    cards = render_summary_cards()
    
    return cards, table


# 1. Agregar IOU (Actualiza tabla y resumen)
@callback(
    [Output("msg-add-iou", "children"), Output("iou-table-container", "children", allow_duplicate=True), Output("iou-summary-row", "children", allow_duplicate=True), Output("iou-name", "value"), Output("iou-amount", "value")],
    Input("btn-add-iou", "n_clicks"),
    [State("iou-name", "value"), State("iou-amount", "value"), State("iou-type", "value"), State("iou-due-date", "date"), State("iou-person-name", "value")],
    prevent_initial_call=True
)
def add_iou(n, name, amount, i_type, date, person):
    if not n: return no_update
    if not all([name, amount, i_type, person]): return html.Span("Faltan datos", className="text-danger"), no_update, no_update, no_update, no_update
    dm.add_iou(name, float(amount), i_type, date, person, "")
    return html.Span("Registrado", className="text-success"), generate_iou_table(dm.get_iou_df()), render_summary_cards(), "", ""

# 2. Capturar Clic en Tabla
@callback(Output("iou-viewing-id", "data"), [Input("iou-data-table", "active_cell")], [State("iou-data-table", "data")], prevent_initial_call=True)
def handle_iou_click(active_cell, table_data):
    if active_cell and active_cell['column_id'] == 'action': return table_data[active_cell['row']]['id']
    return no_update

# 3. Abrir Modal Detalle
@callback(
    [Output("iou-detail-modal", "is_open"), Output("iou-detail-id-store", "data"), Output("iou-detail-type", "value"), Output("iou-detail-person-name", "value"), Output("iou-detail-name", "value"), Output("iou-detail-description", "value"), Output("iou-detail-amount", "value"), Output("iou-detail-current-amount", "value"), Output("iou-detail-due-date", "date"), Output("iou-detail-status", "value"), Output("btn-open-payment-modal", "disabled")], 
    [Input('iou-viewing-id', 'data'), Input("iou-btn-close-detail", "n_clicks")], prevent_initial_call=True
)
def open_detail_modal(viewing_id, close_click):
    if ctx.triggered_id == "iou-btn-close-detail" or not viewing_id: return [False] + [no_update]*10
    item = dm.get_iou_by_id(viewing_id)
    if not item: return [no_update]*11
    return True, item['id'], item['type'], item['person_name'], item['name'], item.get('description', ''), item['amount'], item['current_amount'], item['due_date'], item['status'], (item['status'] == 'Paid')

# 4. Abrir/Cerrar Pago
@callback(
    [Output("iou-payment-modal", "is_open"), Output("pay-modal-current-balance", "children"), Output("pay-modal-amount", "value"), Output("pay-modal-msg", "children"), Output("pay-modal-account", "options")], 
    [Input("btn-open-payment-modal", "n_clicks"), Input("btn-cancel-pay-modal", "n_clicks")], [State("iou-viewing-id", "data")], prevent_initial_call=True
)
def toggle_payment_modal(open_n, close_n, iou_id):
    if ctx.triggered_id == "btn-cancel-pay-modal": return False, no_update, "", "", no_update
    if ctx.triggered_id == "btn-open-payment-modal" and iou_id:
        item = dm.get_iou_by_id(iou_id)
        if item: return True, f"${item['current_amount']:,.2f}", "", "", dm.get_account_options()
    return no_update, no_update, no_update, no_update, no_update

# 5. Confirmar Pago Total Modal
@callback(Output("pay-full-confirm-modal", "is_open"), [Input("btn-confirm-full-pay", "n_clicks"), Input("btn-cancel-confirm-full", "n_clicks")], prevent_initial_call=True)
def toggle_pay_full_confirm(open_click, cancel_click): return True if ctx.triggered_id == "btn-confirm-full-pay" else False

# 6. Pago Parcial
@callback(
    [Output("iou-payment-modal", "is_open", allow_duplicate=True), Output("iou-detail-current-amount", "value", allow_duplicate=True), Output("iou-detail-status", "value", allow_duplicate=True), Output("btn-open-payment-modal", "disabled", allow_duplicate=True), Output("iou-table-container", "children", allow_duplicate=True), Output("iou-summary-row", "children", allow_duplicate=True), Output("global-iou-toast", "is_open", allow_duplicate=True), Output("global-iou-toast", "children", allow_duplicate=True), Output("global-iou-toast", "icon", allow_duplicate=True), Output("pay-modal-msg", "children", allow_duplicate=True), Output("iou-viewing-id", "data", allow_duplicate=True)], 
    Input("btn-confirm-partial-pay", "n_clicks"), [State("iou-viewing-id", "data"), State("pay-modal-amount", "value"), State("pay-modal-account", "value")], prevent_initial_call=True
)
def process_partial_payment(n_clicks, iou_id, amount_input, acc_id):
    if not n_clicks or not iou_id: return no_update
    if not amount_input or float(amount_input) <= 0: return True, no_update, no_update, no_update, no_update, no_update, False, "", "", html.Span("Inválido", className="text-danger"), no_update
    success, msg, new_bal, new_stat = dm.make_iou_payment(iou_id, float(amount_input), acc_id)
    if success: return False, new_bal, new_stat, (new_stat=='Paid'), generate_iou_table(dm.get_iou_df()), render_summary_cards(), *ui_helpers.mensaje_alerta_exito("success", msg), "", iou_id
    return True, no_update, no_update, no_update, no_update, no_update, False, "", "", html.Span(msg, className="text-danger"), no_update

# 7. Pago Total
@callback(
    [Output("pay-full-confirm-modal", "is_open", allow_duplicate=True), Output("iou-payment-modal", "is_open", allow_duplicate=True), Output("iou-viewing-id", "data", allow_duplicate=True), Output("iou-table-container", "children", allow_duplicate=True), Output("iou-summary-row", "children", allow_duplicate=True), Output("global-iou-toast", "is_open", allow_duplicate=True), Output("global-iou-toast", "children", allow_duplicate=True), Output("global-iou-toast", "icon", allow_duplicate=True)],
    Input("btn-really-pay-full", "n_clicks"), [State("iou-viewing-id", "data"), State("pay-modal-account", "value")], prevent_initial_call=True
)
def execute_full_payment(n_clicks, iou_id, acc_id):
    if not n_clicks or not iou_id: return no_update
    iou = dm.get_iou_by_id(iou_id)
    success, msg, _, _ = dm.make_iou_payment(iou_id, iou['current_amount'], acc_id)
    if success: return False, False, None, generate_iou_table(dm.get_iou_df()), render_summary_cards(), *ui_helpers.mensaje_alerta_exito("success", "Pagado")
    return False, True, no_update, no_update, no_update, *ui_helpers.mensaje_alerta_exito("danger", msg)

# 8. Close detail on None
@callback(Output("iou-detail-modal", "is_open", allow_duplicate=True), Input("iou-viewing-id", "data"), prevent_initial_call=True)
def close_detail_on_none_id(view_id): return False if view_id is None else no_update

# 9. Edit Mode
@callback([Output("iou-detail-person-name", "disabled"), Output("iou-detail-name", "disabled"), Output("iou-detail-amount", "disabled"), Output("iou-detail-current-amount", "disabled"), Output("iou-detail-due-date", "disabled"), Output("iou-detail-description", "disabled"), Output("iou-btn-save", "style")], Input("iou-btn-edit-mode", "n_clicks"), prevent_initial_call=True)
def enable_edit(n): return (False, False, False, False, False, False, {'display': 'inline-block'}) if n and n%2!=0 else (True, True, True, True, True, True, {'display': 'none'})

# 10. Save Edit
@callback([Output("iou-table-container", "children", allow_duplicate=True), Output("iou-summary-row", "children", allow_duplicate=True), Output("global-iou-toast", "is_open", allow_duplicate=True), Output("global-iou-toast", "children", allow_duplicate=True), Output("global-iou-toast", "icon", allow_duplicate=True)], Input("iou-btn-save", "n_clicks"), [State("iou-viewing-id", "data"), State("iou-detail-name", "value"), State("iou-detail-amount", "value"), State("iou-detail-type", "value"), State("iou-detail-due-date", "date"), State("iou-detail-person-name", "value"), State("iou-detail-description", "value"), State("iou-detail-current-amount", "value"), State("iou-detail-status", "value")], prevent_initial_call=True)
def save_edit(n, iou_id, name, amt, type, date, person, desc, curr, stat):
    if not n: return no_update
    success, msg = dm.update_iou(iou_id, name, float(amt), type, date, person, desc, float(curr), stat)
    return generate_iou_table(dm.get_iou_df()), render_summary_cards(), *ui_helpers.mensaje_alerta_exito("success" if success else "danger", msg)

# 11. Delete
@callback(Output("iou-delete-modal", "is_open"), [Input("iou-btn-trigger-delete", "n_clicks"), Input("iou-btn-del-cancel", "n_clicks")], prevent_initial_call=True)
def toggle_del_modal(trig, cancel): return True if ctx.triggered_id == "iou-btn-trigger-delete" else False

@callback([Output("iou-delete-modal", "is_open", allow_duplicate=True), Output("iou-detail-modal", "is_open", allow_duplicate=True), Output("iou-table-container", "children", allow_duplicate=True), Output("iou-summary-row", "children", allow_duplicate=True), Output("global-iou-toast", "is_open", allow_duplicate=True), Output("global-iou-toast", "children", allow_duplicate=True), Output("global-iou-toast", "icon", allow_duplicate=True)], Input("iou-btn-del-confirm", "n_clicks"), State("iou-viewing-id", "data"), prevent_initial_call=True)
def confirm_delete(n, iou_id):
    if not n: return no_update
    dm.delete_iou(iou_id)
=======
# pages/debts.py
import dash
from dash import dcc, html, callback, Input, Output, State, no_update, ctx, ALL
from dash import dash_table
import dash_bootstrap_components as dbc
from datetime import date
import backend.data_manager as dm
from utils import ui_helpers
import time 

# -----------------------------------------------------------------------------
# 1. FUNCIONES AUXILIARES (Solo lógica visual)
# -----------------------------------------------------------------------------

def render_summary_cards():
    """Genera las tarjetas de resumen (Calculadas dinámicamente)."""
    # 1. OBTENER DATOS (Ahora filtrados por usuario gracias a data_manager)
    try:
        summary = dm.get_full_debt_summary()
        
        informal_debt = summary['informal_debt']
        informal_collectible = summary['informal_collectible']
        net_exposure = summary['net_exposure']
        informal_net_balance = summary['informal_net_balance']
        credit_exigible_net = summary['credit_exigible_net']
        
        # Recalcular receivables/payables crudos para visualización si es necesario
        # O confiar en el resumen. Para los badges usamos el desglose:
        
        # --- LÓGICA VISUAL ---
        if net_exposure > 0:
            exposure_color = "text-danger"
            exposure_title = "Deuda Neta Real (A Pagar)"
        elif net_exposure < 0:
            exposure_color = "text-success"
            exposure_title = "Excedente de Liquidez Real"
            net_exposure = abs(net_exposure)
        else:
            exposure_color = "text-primary"
            exposure_title = "Punto de Equilibrio"

        if informal_net_balance > 0:
            net_icon = "bi bi-arrow-up-circle-fill me-2"
            informal_color = "text-success"
        elif informal_net_balance < 0:
            net_icon = "bi bi-arrow-down-circle-fill me-2"
            informal_color = "text-danger"
        else:
            net_icon = "bi bi-check-circle-fill me-2"
            informal_color = "text-muted"

        return [
            # TARJETA 1
            dbc.Col(dbc.Card(dbc.CardBody([
                html.H5(exposure_title, className="card-title text-muted small text-uppercase fw-bold"),
                html.H2(f"${net_exposure:,.2f}", className=f"card-value {exposure_color} mb-3 fw-bold"),
                html.Div([
                    dbc.Row([dbc.Col("Exigible TC (Neto):", className="text-muted small"), dbc.Col(f"${credit_exigible_net:,.2f}", className="text-end small fw-bold")]),
                    dbc.Row([dbc.Col("Posición Informal:", className="text-muted small"), dbc.Col(f"{'-' if informal_net_balance > 0 else '+'}${abs(informal_net_balance):,.2f}", className=f"text-end small fw-bold {informal_color}")]),
                ], className="border-top pt-2 mt-2")
            ]), className="metric-card h-100 shadow-sm border-0"), lg=6, md=12, className="mb-4"),
            
            # TARJETA 2
            dbc.Col(dbc.Card(dbc.CardBody([
                html.H5("Posición Informal (IOU)", className="card-title text-muted small text-uppercase fw-bold"),
                html.H2([html.I(className=net_icon), f"${abs(informal_net_balance):,.2f}"], className=f"card-value {informal_color} mb-3"),
                html.Div([
                    html.Span([html.I(className="bi bi-box-arrow-in-down me-1"), f"Me deben: ${informal_collectible:,.2f}"], className="badge bg-success bg-opacity-10 text-success me-2 p-2"),
                    html.Span([html.I(className="bi bi-box-arrow-up-right me-1"), f"Yo debo: ${informal_debt:,.2f}"], className="badge bg-danger bg-opacity-10 text-danger p-2")
                ], className="d-flex justify-content-center")
            ]), className="metric-card h-100 shadow-sm border-0"), lg=6, md=12, className="mb-4"),
        ]
    except Exception as e:
        return html.Div(f"Error cargando resumen: {e}", className="text-danger")


def generate_iou_table(dataframe):
    """Genera la tabla visual."""
    if dataframe.empty:
        return html.Div("No hay cuentas pendientes registradas.", className="text-muted fst-italic text-center py-4")
        
    dataframe = dataframe.copy()
    if 'status' in dataframe.columns:
        dataframe = dataframe[dataframe['status'] != 'Paid']
    else:
        dataframe = dataframe[dataframe['current_amount'].abs() > 0.01]

    if dataframe.empty:
        return html.Div("¡Todo al día! No tienes cuentas pendientes.", className="text-success fst-italic text-center py-4")

    dataframe['action'] = "ℹ️"
    dataframe['tipo_visual'] = dataframe['type'].apply(lambda x: "🟢 Me deben" if x == 'Receivable' else "🔴 Yo debo")
    
    return dash_table.DataTable(
        id='iou-data-table',
        data=dataframe.to_dict('records'),
        style_table={'overflowX': 'auto', 'minWidth': '100%', 'maxHeight': '32vh', 'overflowY': 'auto'},
        fixed_rows={'headers': True}, 
        columns=[
            {"name": "ID", "id": "id", "deletable": False, "selectable": False}, 
            {"name": "Condición", "id": "tipo_visual"}, 
            {"name": "Persona/Entidad", "id": "person_name"}, 
            {"name": "Concepto", "id": "name"},
            {"name": "Saldo Pendiente", "id": "current_amount", "type": "numeric", "format": {"specifier": "$,.2f"}},
            {"name": "Info", "id": "action", "deletable": False, "selectable": False}
        ],
        style_header={'backgroundColor': '#333', 'color': 'white', 'fontWeight': 'bold'},
        style_header_conditional=[{'if': {'column_id': 'id'}, 'display': 'none'}],
        style_data={'backgroundColor': '#1E1E1E', 'color': '#E0E0E0'},
        style_data_conditional=[
            {'if': {'column_id': 'id'}, 'display': 'none'},
            {'if': {'filter_query': '{type} = "Receivable"'}, 'backgroundColor': 'rgba(0, 100, 0, 0.3)', 'color': '#e8f5e9'},
            {'if': {'filter_query': '{type} = "Payable"'}, 'backgroundColor': 'rgba(100, 0, 0, 0.3)', 'color': '#ffebee'},
            {'if': {'column_id': 'action'}, 'textAlign': 'center', 'cursor': 'pointer', 'fontWeight': 'bold', 'color': '#33b5e5'}, 
        ],
        style_cell={'border': '1px solid #444', 'padding': '10px'},
        page_action='none', page_size=9999,     
    )

# -----------------------------------------------------------------------------
# 2. DEFINICIÓN DE MODALES (Igual que antes)
# -----------------------------------------------------------------------------
pay_full_confirm_modal = dbc.Modal([
    dbc.ModalHeader(dbc.ModalTitle("Confirmar Pago Total"), className="bg-danger text-white"),
    dbc.ModalBody([
        html.H4("¿Estás seguro?", className="text-center mb-3"),
        html.P("Esto marcará la deuda como completamente pagada.", className="text-center"),
    ]),
    dbc.ModalFooter([
        dbc.Button("Cancelar", id="btn-cancel-confirm-full", outline=True, className="me-auto"),
        dbc.Button("¡Sí, Pagar Todo!", id="btn-really-pay-full", color="success", className="fw-bold"),
    ])
], id="pay-full-confirm-modal", is_open=False, centered=True, size="sm", backdrop="static")

payment_modal = dbc.Modal([
    dbc.ModalHeader("Registrar Abono o Pago"),
    dbc.ModalBody([
        html.Div([html.Small("Saldo Pendiente Actual:", className="text-muted d-block"), html.H3(id="pay-modal-current-balance", className="text-primary fw-bold")], className="text-center mb-4 p-2 border rounded bg-light bg-opacity-10"),
        dbc.Label("Monto a Abonar"),
        dbc.Input(id="pay-modal-amount", type="number", min=0, placeholder="0.00", className="mb-3 form-control-lg"),
        dbc.Label("Cuenta de Origen/Destino"),
        dcc.Dropdown(id="pay-modal-account", placeholder="Seleccionar cuenta...", className="mb-4 text-dark"),
        dbc.Row([
            dbc.Col(dbc.Button("Abonar Cantidad", id="btn-confirm-partial-pay", color="warning", className="w-100"), width=6),
            dbc.Col(dbc.Button("✅ Pagar Todo", id="btn-confirm-full-pay", color="success", className="w-100"), width=6),
        ], className="g-2"),
        html.Div(id="pay-modal-msg", className="mt-3 text-center")
    ]),
    dbc.ModalFooter([dbc.Button("Cancelar", id="btn-cancel-pay-modal", outline=True, size="sm")])
], id="iou-payment-modal", is_open=False, centered=True, size="md")

detail_modal = dbc.Modal([
    dbc.ModalHeader(dbc.ModalTitle("Detalle de Cuenta")),
    dbc.ModalBody([
        dcc.Store(id="iou-detail-id-store"),
        dbc.Row([
            dbc.Col([dbc.Label("Tipo", className="small fw-bold mb-0"), dbc.RadioItems(id="iou-detail-type", options=[{"label": "Cobro", "value": "Receivable"}, {"label": "Deuda", "value": "Payable"}], inline=True, className="small")], width=7),
            dbc.Col([dbc.Label("Estado", className="small fw-bold mb-0"), dbc.Select(id="iou-detail-status", options=[{"label": "Pendiente", "value": "Pending"}, {"label": "Pagado", "value": "Paid"}], size="sm", disabled=True)], width=5),
        ], className="mb-2 align-items-center"),
        dbc.Row([dbc.Col([dbc.Label("Persona/Entidad", className="small mb-0"), dbc.Input(id="iou-detail-person-name", size="sm", disabled=True)], width=6), dbc.Col([dbc.Label("Concepto", className="small mb-0"), dbc.Input(id="iou-detail-name", size="sm", disabled=True)], width=6)], className="mb-2"),
        dbc.Row([dbc.Col([dbc.Label("Monto Original", className="small mb-0"), dbc.Input(id="iou-detail-amount", type="number", size="sm", disabled=True)], width=6), dbc.Col([dbc.Label("Saldo Pendiente", className="small mb-0 text-warning fw-bold"), dbc.Input(id="iou-detail-current-amount", type="number", size="sm", className="fw-bold text-warning", disabled=True)], width=6)], className="mb-2"),
        dbc.Row([dbc.Col([dbc.Label("Fecha Límite", className="small mb-0"), dcc.DatePickerSingle(id='iou-detail-due-date', display_format='YYYY-MM-DD', className='d-block small-date-picker', disabled=True)], width=5), dbc.Col([dbc.Label("Notas", className="small mb-0"), dbc.Textarea(id="iou-detail-description", rows=1, size="sm", disabled=True)], width=7)], className="mb-3"),
        html.Div(id="iou-detail-msg", className="text-center small")
    ]),
    dbc.ModalFooter([
        dbc.Button("💰 Registrar Pago", id="btn-open-payment-modal", color="primary", className="me-auto"),
        dbc.Button("Editar", id="iou-btn-edit-mode", color="info", outline=True, size="sm", className="me-1"),
        dbc.Button("Guardar", id="iou-btn-save", color="success", size="sm", className="me-1", style={'display': 'none'}),
        dbc.Button("Borrar", id="iou-btn-trigger-delete", color="danger", outline=True, size="sm", className="me-1"),
        dbc.Button("Cerrar", id="iou-btn-close-detail", color="secondary", size="sm"),
    ], className="d-flex justify-content-between align-items-center py-2")
], id="iou-detail-modal", is_open=False, size="md", centered=True)

delete_modal = dbc.Modal([
    dbc.ModalHeader("Confirmar Eliminación"),
    dbc.ModalBody("¿Eliminar permanentemente?"),
    dbc.ModalFooter([dbc.Button("Cancelar", id="iou-btn-del-cancel", outline=True, size="sm"), dbc.Button("Sí, Borrar", id="iou-btn-del-confirm", color="danger", size="sm")])
], id="iou-delete-modal", is_open=False, centered=True, size="sm")


# -----------------------------------------------------------------------------
# 3. LAYOUT PRINCIPAL (VACÍO INICIALMENTE)
# -----------------------------------------------------------------------------
layout = dbc.Container([
    dcc.Store(id='iou-viewing-id', data=None),
    dcc.Store(id='iou-edit-signal', data=0), 
    ui_helpers.get_feedback_toast("global-iou-toast"),
    
    detail_modal, payment_modal, pay_full_confirm_modal, delete_modal,

    html.H2("Deudas y Cobros (IOU)", className="mb-4"),
    
    # 🚨 CAMBIO: Los hijos inician con Spinner, se llenan vía callback
    dbc.Row(id="iou-summary-row", children=[dbc.Spinner(color="primary")], className="mb-4"),

    dbc.Row([
        # Formulario
        dbc.Col([
            dbc.Card([
                dbc.CardHeader("Nuevo Registro"),
                dbc.CardBody([
                    dbc.RadioItems(id="iou-type", options=[{"label": "Me deben", "value": "Receivable"}, {"label": "Yo debo", "value": "Payable"}], value="Receivable", inline=True, className="mb-2 small"),
                    dbc.Row([dbc.Col(dbc.Input(id="iou-person-name", placeholder="Persona/Entidad", size="sm"), width=6), dbc.Col(dbc.Input(id="iou-name", placeholder="Concepto", size="sm"), width=6)], className="mb-2 g-2"),
                    dbc.Row([dbc.Col(dbc.Input(id="iou-amount", placeholder="Monto $", type="number", size="sm"), width=6), dbc.Col(dcc.DatePickerSingle(id='iou-due-date', placeholder='Fecha Límite', display_format='YYYY-MM-DD', className='d-block w-100 small-date-picker'), width=6)], className="mb-3 g-2"),
                    dbc.Button("Registrar", id="btn-add-iou", color="primary", size="sm", className="w-100"),
                    html.Div(id="msg-add-iou", className="mt-1 text-center small")
                ])
            ], className="data-card mb-3")
        ], lg=4, md=12),

        # Tabla
        # 🚨 CAMBIO: El body inicia con Spinner, se llena vía callback
        dbc.Col([
            dbc.Card([
                dbc.CardHeader("Listado de Pendientes"),
                dbc.CardBody(id="iou-table-container", children=[dbc.Spinner(color="primary")], style={"padding": "0"}) 
            ], className="data-card")
        ], lg=8, md=12)
    ])
], fluid=True, className="page-container")


# -----------------------------------------------------------------------------
# 4. CALLBACKS
# -----------------------------------------------------------------------------

# 🚨 NUEVO CALLBACK DE CARGA INICIAL (Este es el que arregla el problema)
@callback(
    [Output("iou-summary-row", "children"),
     Output("iou-table-container", "children")],
    [Input("url", "pathname")],
    prevent_initial_call=False 
)
def load_iou_data_on_start(pathname):
    if pathname != "/deudas":
        return no_update, no_update
        
    # Ahora sí, al ejecutarse dentro del callback, dm.get_iou_df() usará el usuario logueado
    df = dm.get_iou_df()
    table = generate_iou_table(df)
    cards = render_summary_cards()
    
    return cards, table


# 1. Agregar IOU (Actualiza tabla y resumen)
@callback(
    [Output("msg-add-iou", "children"), Output("iou-table-container", "children", allow_duplicate=True), Output("iou-summary-row", "children", allow_duplicate=True), Output("iou-name", "value"), Output("iou-amount", "value")],
    Input("btn-add-iou", "n_clicks"),
    [State("iou-name", "value"), State("iou-amount", "value"), State("iou-type", "value"), State("iou-due-date", "date"), State("iou-person-name", "value")],
    prevent_initial_call=True
)
def add_iou(n, name, amount, i_type, date, person):
    if not n: return no_update
    if not all([name, amount, i_type, person]): return html.Span("Faltan datos", className="text-danger"), no_update, no_update, no_update, no_update
    dm.add_iou(name, float(amount), i_type, date, person, "")
    return html.Span("Registrado", className="text-success"), generate_iou_table(dm.get_iou_df()), render_summary_cards(), "", ""

# 2. Capturar Clic en Tabla
@callback(Output("iou-viewing-id", "data"), [Input("iou-data-table", "active_cell")], [State("iou-data-table", "data")], prevent_initial_call=True)
def handle_iou_click(active_cell, table_data):
    if active_cell and active_cell['column_id'] == 'action': return table_data[active_cell['row']]['id']
    return no_update

# 3. Abrir Modal Detalle
@callback(
    [Output("iou-detail-modal", "is_open"), Output("iou-detail-id-store", "data"), Output("iou-detail-type", "value"), Output("iou-detail-person-name", "value"), Output("iou-detail-name", "value"), Output("iou-detail-description", "value"), Output("iou-detail-amount", "value"), Output("iou-detail-current-amount", "value"), Output("iou-detail-due-date", "date"), Output("iou-detail-status", "value"), Output("btn-open-payment-modal", "disabled")], 
    [Input('iou-viewing-id', 'data'), Input("iou-btn-close-detail", "n_clicks")], prevent_initial_call=True
)
def open_detail_modal(viewing_id, close_click):
    if ctx.triggered_id == "iou-btn-close-detail" or not viewing_id: return [False] + [no_update]*10
    item = dm.get_iou_by_id(viewing_id)
    if not item: return [no_update]*11
    return True, item['id'], item['type'], item['person_name'], item['name'], item.get('description', ''), item['amount'], item['current_amount'], item['due_date'], item['status'], (item['status'] == 'Paid')

# 4. Abrir/Cerrar Pago
@callback(
    [Output("iou-payment-modal", "is_open"), Output("pay-modal-current-balance", "children"), Output("pay-modal-amount", "value"), Output("pay-modal-msg", "children"), Output("pay-modal-account", "options")], 
    [Input("btn-open-payment-modal", "n_clicks"), Input("btn-cancel-pay-modal", "n_clicks")], [State("iou-viewing-id", "data")], prevent_initial_call=True
)
def toggle_payment_modal(open_n, close_n, iou_id):
    if ctx.triggered_id == "btn-cancel-pay-modal": return False, no_update, "", "", no_update
    if ctx.triggered_id == "btn-open-payment-modal" and iou_id:
        item = dm.get_iou_by_id(iou_id)
        if item: return True, f"${item['current_amount']:,.2f}", "", "", dm.get_account_options()
    return no_update, no_update, no_update, no_update, no_update

# 5. Confirmar Pago Total Modal
@callback(Output("pay-full-confirm-modal", "is_open"), [Input("btn-confirm-full-pay", "n_clicks"), Input("btn-cancel-confirm-full", "n_clicks")], prevent_initial_call=True)
def toggle_pay_full_confirm(open_click, cancel_click): return True if ctx.triggered_id == "btn-confirm-full-pay" else False

# 6. Pago Parcial
@callback(
    [Output("iou-payment-modal", "is_open", allow_duplicate=True), Output("iou-detail-current-amount", "value", allow_duplicate=True), Output("iou-detail-status", "value", allow_duplicate=True), Output("btn-open-payment-modal", "disabled", allow_duplicate=True), Output("iou-table-container", "children", allow_duplicate=True), Output("iou-summary-row", "children", allow_duplicate=True), Output("global-iou-toast", "is_open", allow_duplicate=True), Output("global-iou-toast", "children", allow_duplicate=True), Output("global-iou-toast", "icon", allow_duplicate=True), Output("pay-modal-msg", "children", allow_duplicate=True), Output("iou-viewing-id", "data", allow_duplicate=True)], 
    Input("btn-confirm-partial-pay", "n_clicks"), [State("iou-viewing-id", "data"), State("pay-modal-amount", "value"), State("pay-modal-account", "value")], prevent_initial_call=True
)
def process_partial_payment(n_clicks, iou_id, amount_input, acc_id):
    if not n_clicks or not iou_id: return no_update
    if not amount_input or float(amount_input) <= 0: return True, no_update, no_update, no_update, no_update, no_update, False, "", "", html.Span("Inválido", className="text-danger"), no_update
    success, msg, new_bal, new_stat = dm.make_iou_payment(iou_id, float(amount_input), acc_id)
    if success: return False, new_bal, new_stat, (new_stat=='Paid'), generate_iou_table(dm.get_iou_df()), render_summary_cards(), *ui_helpers.mensaje_alerta_exito("success", msg), "", iou_id
    return True, no_update, no_update, no_update, no_update, no_update, False, "", "", html.Span(msg, className="text-danger"), no_update

# 7. Pago Total
@callback(
    [Output("pay-full-confirm-modal", "is_open", allow_duplicate=True), Output("iou-payment-modal", "is_open", allow_duplicate=True), Output("iou-viewing-id", "data", allow_duplicate=True), Output("iou-table-container", "children", allow_duplicate=True), Output("iou-summary-row", "children", allow_duplicate=True), Output("global-iou-toast", "is_open", allow_duplicate=True), Output("global-iou-toast", "children", allow_duplicate=True), Output("global-iou-toast", "icon", allow_duplicate=True)],
    Input("btn-really-pay-full", "n_clicks"), [State("iou-viewing-id", "data"), State("pay-modal-account", "value")], prevent_initial_call=True
)
def execute_full_payment(n_clicks, iou_id, acc_id):
    if not n_clicks or not iou_id: return no_update
    iou = dm.get_iou_by_id(iou_id)
    success, msg, _, _ = dm.make_iou_payment(iou_id, iou['current_amount'], acc_id)
    if success: return False, False, None, generate_iou_table(dm.get_iou_df()), render_summary_cards(), *ui_helpers.mensaje_alerta_exito("success", "Pagado")
    return False, True, no_update, no_update, no_update, *ui_helpers.mensaje_alerta_exito("danger", msg)

# 8. Close detail on None
@callback(Output("iou-detail-modal", "is_open", allow_duplicate=True), Input("iou-viewing-id", "data"), prevent_initial_call=True)
def close_detail_on_none_id(view_id): return False if view_id is None else no_update

# 9. Edit Mode
@callback([Output("iou-detail-person-name", "disabled"), Output("iou-detail-name", "disabled"), Output("iou-detail-amount", "disabled"), Output("iou-detail-current-amount", "disabled"), Output("iou-detail-due-date", "disabled"), Output("iou-detail-description", "disabled"), Output("iou-btn-save", "style")], Input("iou-btn-edit-mode", "n_clicks"), prevent_initial_call=True)
def enable_edit(n): return (False, False, False, False, False, False, {'display': 'inline-block'}) if n and n%2!=0 else (True, True, True, True, True, True, {'display': 'none'})

# 10. Save Edit
@callback([Output("iou-table-container", "children", allow_duplicate=True), Output("iou-summary-row", "children", allow_duplicate=True), Output("global-iou-toast", "is_open", allow_duplicate=True), Output("global-iou-toast", "children", allow_duplicate=True), Output("global-iou-toast", "icon", allow_duplicate=True)], Input("iou-btn-save", "n_clicks"), [State("iou-viewing-id", "data"), State("iou-detail-name", "value"), State("iou-detail-amount", "value"), State("iou-detail-type", "value"), State("iou-detail-due-date", "date"), State("iou-detail-person-name", "value"), State("iou-detail-description", "value"), State("iou-detail-current-amount", "value"), State("iou-detail-status", "value")], prevent_initial_call=True)
def save_edit(n, iou_id, name, amt, type, date, person, desc, curr, stat):
    if not n: return no_update
    success, msg = dm.update_iou(iou_id, name, float(amt), type, date, person, desc, float(curr), stat)
    return generate_iou_table(dm.get_iou_df()), render_summary_cards(), *ui_helpers.mensaje_alerta_exito("success" if success else "danger", msg)

# 11. Delete
@callback(Output("iou-delete-modal", "is_open"), [Input("iou-btn-trigger-delete", "n_clicks"), Input("iou-btn-del-cancel", "n_clicks")], prevent_initial_call=True)
def toggle_del_modal(trig, cancel): return True if ctx.triggered_id == "iou-btn-trigger-delete" else False

@callback([Output("iou-delete-modal", "is_open", allow_duplicate=True), Output("iou-detail-modal", "is_open", allow_duplicate=True), Output("iou-table-container", "children", allow_duplicate=True), Output("iou-summary-row", "children", allow_duplicate=True), Output("global-iou-toast", "is_open", allow_duplicate=True), Output("global-iou-toast", "children", allow_duplicate=True), Output("global-iou-toast", "icon", allow_duplicate=True)], Input("iou-btn-del-confirm", "n_clicks"), State("iou-viewing-id", "data"), prevent_initial_call=True)
def confirm_delete(n, iou_id):
    if not n: return no_update
    dm.delete_iou(iou_id)
>>>>>>> b74f1b0a886c27181c8264a954a4baf9f2b71029
    return False, False, generate_iou_table(dm.get_iou_df()), render_summary_cards(), *ui_helpers.mensaje_alerta_exito("success", "Eliminado")