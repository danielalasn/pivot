# pages/debts.py
import dash
from dash import dcc, html, callback, Input, Output, State, no_update, ctx
import dash_bootstrap_components as dbc
from dash import dash_table
from datetime import date
import backend.data_manager as dm
from utils import ui_helpers

# -----------------------------------------------------------------------------
# 1. FUNCIONES AUXILIARES (Definidas ANTES del Layout)
# -----------------------------------------------------------------------------

# pages/debts.py

def generate_summary_cards():
    """
    Genera las tarjetas de resumen calculando directamente desde la tabla de IOUs.
    """
    # 1. OBTENER DATOS DE LA TABLA IOU (Corrección)
    df_iou = dm.get_iou_df()
    
    if df_iou.empty:
        informal_debt = 0.0
        informal_collectible = 0.0
    else:
        # Sumar lo que YO DEBO (Payable)
        informal_debt = df_iou[df_iou['type'] == 'Payable']['current_amount'].sum()
        # Sumar lo que ME DEBEN (Receivable)
        informal_collectible = df_iou[df_iou['type'] == 'Receivable']['current_amount'].sum()

    # 2. Obtener Deuda Exigible de Tarjetas (Para la Card 1)
    try:
        credit_exigible_net = dm.get_net_exigible_credit_debt()
    except:
        credit_exigible_net = 0.0

    # 3. CÁLCULOS
    # Total Pasivos (Lo que debo informal + Tarjeta Exigible)
    total_liabilities = informal_debt + credit_exigible_net
    
    # Exposición Neta (Total Pasivos - Total Activos Informales)
    net_exposure = total_liabilities - informal_collectible
    
    # Saldo Neto Informal (Solo IOU: Cobros - Deudas)
    informal_net_balance = informal_collectible - informal_debt

    # 4. Determinación de Colores e Iconos
    if informal_net_balance > 0:
        net_color = "text-success" # Verde
        net_icon = "bi bi-arrow-up-circle-fill me-2"
    elif informal_net_balance < 0:
        net_color = "text-danger" # Rojo
        net_icon = "bi bi-arrow-down-circle-fill me-2"
    else:
        net_color = "text-primary" # Azul (Neutro)
        net_icon = "bi bi-check-circle-fill me-2"

    return [
        # CARD 1: Exposición de Deuda Total
        dbc.Col(
            dbc.Card(
                dbc.CardBody([
                    html.H5("Exposición Neta a Deuda", className="card-title text-warning"),
                    html.H2(f"${net_exposure:,.2f}", className=f"card-value {'text-danger' if net_exposure > 0 else 'text-success'} mb-3"),
                    html.Small("Detalle:", className="d-block text-muted"),
                    html.Ul([
                        html.Li(f"Debo (Informal + TC Exigible): ${total_liabilities:,.2f}", className="text-danger mb-1"),
                        html.Li(f"Me deben (Informal): -${informal_collectible:,.2f}", className="text-success"),
                    ], className="list-unstyled small ps-3")
                ]),
                className="metric-card h-100 shadow-sm"
            ),
            lg=6, md=12, className="mb-4"
        ),
        # CARD 2: Saldo Neto Informal (IOU)
        dbc.Col(
            dbc.Card(
                dbc.CardBody([
                    html.H5("Saldo Neto de Cuentas Informales", className="card-title"),
                    html.H2([
                        html.I(className=net_icon),
                        f"${informal_net_balance:,.2f}"
                    ], className=f"card-value {net_color} mb-3"),
                    html.Small("Detalle:", className="d-block text-muted"),
                    html.Ul([
                        html.Li(f"Cobros a mi favor: ${informal_collectible:,.2f}", className="text-success mb-1"),
                        html.Li(f"Deudas mías: -${informal_debt:,.2f}", className="text-danger"),
                    ], className="list-unstyled small ps-3")
                ]),
                className="metric-card h-100 shadow-sm"
            ),
            lg=6, md=12, className="mb-4"
        ),
    ]


def generate_iou_table(dataframe):
    """
    Genera la tabla de Dash con los datos de deudas.
    """
    if dataframe.empty:
        return html.Div("No hay cuentas pendientes registradas.", className="text-muted fst-italic text-center py-4")
        
    # Añadimos una columna para el botón de acción
    dataframe = dataframe.copy() # Buena práctica para evitar SettingWithCopyWarning
    dataframe['action'] = "ℹ️"

    return dash_table.DataTable(
        id='iou-data-table',
        data=dataframe.to_dict('records'),
        style_table={'overflowX': 'auto', 'minWidth': '100%'},
        columns=[
            {"name": "ID", "id": "id", "deletable": False, "selectable": False}, 
            {"name": "Persona/Entidad", "id": "person_name"}, 
            {"name": "Concepto", "id": "name"},
            {"name": "Monto", "id": "current_amount", "type": "numeric", "format": {"specifier": "$,.2f"}},
            {"name": "Info", "id": "action", "deletable": False, "selectable": False}
        ],
        style_header={'backgroundColor': '#333', 'color': 'white'},
        style_header_conditional=[{'if': {'column_id': 'id'}, 'display': 'none'}],
        style_data={'backgroundColor': '#1E1E1E', 'color': '#E0E0E0'},
        style_data_conditional=[
            {'if': {'column_id': 'id'}, 'display': 'none'},
            {'if': {'filter_query': '{type} = "Receivable"'}, 'color': '#28a745', 'fontWeight': 'bold'},
            {'if': {'filter_query': '{type} = "Payable"'}, 'color': '#dc3545', 'fontWeight': 'bold'},
            {'if': {'column_id': 'action'}, 'textAlign': 'center', 'cursor': 'pointer', 'fontWeight': 'bold'}
        ],
        style_cell={'border': '1px solid #444'},
        page_action='native',
        page_size=10,
    )

# -----------------------------------------------------------------------------
# 2. LAYOUT DE LA PÁGINA
# -----------------------------------------------------------------------------
layout = dbc.Container([
    # --- Stores y Estados ---
    dcc.Store(id='iou-viewing-id', data=None),
    dcc.Store(id='iou-edit-signal', data=0), 

    # --- COMPONENTE DE MENSAJES (TOAST) ---
    ui_helpers.get_feedback_toast("global-iou-toast"),

    # --- MODAL 1: DETALLE / EDICIÓN ---
    dbc.Modal([
        dbc.ModalHeader(dbc.ModalTitle("Detalle y Edición de Cuenta Pendiente")),
        dbc.ModalBody([
            dbc.Row([
                dbc.Col([
                    dbc.Label("Tipo:"),
                    dbc.RadioItems(
                        id="iou-detail-type",
                        options=[
                            {"label": "Me deben (Cobro)", "value": "Receivable"},
                            {"label": "Yo debo (Deuda)", "value": "Payable"},
                        ],
                        inline=True,
                        className="mb-3",
                    )
                ], width=10),
                dbc.Col([
                    dcc.Store(id="iou-detail-id-store") 
                ], width=0)
            ]),
            
            dbc.Label("Persona/Entidad"),
            dbc.Input(id="iou-detail-person-name", type="text", className="mb-3", disabled=True),
            
            dbc.Label("Concepto"),
            dbc.Input(id="iou-detail-name", type="text", className="mb-3", disabled=True),

            dbc.Label("Descripción"),
            dbc.Textarea(id="iou-detail-description", className="mb-3", disabled=True),

            dbc.Row([
                dbc.Col([
                    dbc.Label("Monto Original"),
                    dbc.Input(id="iou-detail-amount", type="number", className="mb-3", disabled=True),
                ], width=6),
                dbc.Col([
                    dbc.Label("Saldo Pendiente"),
                    dbc.Input(id="iou-detail-current-amount", type="number", className="mb-3", disabled=True),
                ], width=6)
            ]),

            dbc.Row([
                dbc.Col([
                    dbc.Label("Fecha Límite"),
                    dcc.DatePickerSingle(
                        id='iou-detail-due-date',
                        display_format='YYYY-MM-DD',
                        className='mb-3 d-block',
                        disabled=True
                    ),
                ], width=6),
                dbc.Col([
                    dbc.Label("Estado"),
                    dbc.Select(
                        id="iou-detail-status",
                        options=[
                            {"label": "Pendiente", "value": "Pending"},
                            {"label": "Pagado/Cerrado", "value": "Paid"},
                            {"label": "Parcial", "value": "Partial"},
                        ],
                        value="Pending",
                        className="mb-3",
                        disabled=True
                    )
                ], width=6)
            ]),

            html.Div(id="iou-detail-msg", className="mt-2 text-center")
            
        ]),
        dbc.ModalFooter([
            dbc.Button("Modo Edición", id="iou-btn-edit-mode", color="info", className="me-2", outline=True),
            dbc.Button("Guardar Cambios", id="iou-btn-save", color="success", className="me-2", style={'display': 'none'}),
            dbc.Button("✅ Marcar como Pagado", id="iou-btn-mark-paid", color="success", className="me-auto ms-2"),
            dbc.Button("Borrar", id="iou-btn-trigger-delete", color="danger"),
            dbc.Button("Cerrar", id="iou-btn-close-detail", color="secondary", outline=True, className="ms-2"),
        ])
    ], id="iou-detail-modal", is_open=False, size="lg", centered=True),

    # --- MODAL 2: CONFIRMACIÓN BORRADO ---
    dbc.Modal([
        dbc.ModalHeader(dbc.ModalTitle("Confirmar Eliminación")),
        dbc.ModalBody("¿Estás seguro de eliminar esta cuenta pendiente permanentemente?"),
        dbc.ModalFooter([
            dbc.Button("Cancelar", id="iou-btn-del-cancel", className="ms-auto", outline=True),
            dbc.Button("Confirmar Borrado", id="iou-btn-del-confirm", color="danger"),
        ])
    ], id="iou-delete-modal", is_open=False, centered=True),

    html.H2("Deudas y Cobros Informales (IOU)", className="mb-4"),

    # --- ROW DE RESUMEN (Dashboard) ---
    # Ahora sí funciona porque generate_summary_cards ya está definida arriba
    dbc.Row(id="iou-summary-row", children=generate_summary_cards(), className="mb-4"),

    dbc.Row([
        # Formulario de Registro
        dbc.Col([
            dbc.Card([
                dbc.CardHeader("Registrar Cuenta Pendiente"),
                dbc.CardBody([
                    dbc.Label("Tipo de Cuenta"),
                    dbc.RadioItems(
                        id="iou-type",
                        options=[
                            {"label": "Me deben (Cobro / Receivable)", "value": "Receivable"},
                            {"label": "Yo debo (Deuda / Payable)", "value": "Payable"},
                        ],
                        value="Receivable",
                        inline=True,
                        className="mb-3"
                    ),
                    dbc.Label("Nombre de la Persona/Entidad"),
                    dbc.Input(id="iou-person-name", placeholder="Ej. Juan Pérez", type="text", className="mb-3"),
                    dbc.Label("Concepto (Ej. Pago de Alquiler)"),
                    dbc.Input(id="iou-name", placeholder="Ej. Préstamo de carro...", type="text", className="mb-3"),
                    dbc.Label("Descripción (Opcional)"),
                    dbc.Textarea(id="iou-description", placeholder="Detalles o acuerdos del préstamo...", className="mb-3"),
                    dbc.Label("Monto Original"),
                    dbc.Input(id="iou-amount", placeholder="0.00", type="number", className="mb-3"),
                    dbc.Row([
                        dbc.Col([
                            dbc.Label("Fecha Límite (Opcional)"),
                            dcc.DatePickerSingle(
                                id='iou-due-date',
                                date=None,
                                display_format='YYYY-MM-DD',
                                className='mb-3 d-block' 
                            ),
                        ], width=6),
                    ], className="mb-3"),
                    dbc.Button("Registrar Pendiente", id="btn-add-iou", color="primary", className="w-100"),
                    html.Div(id="msg-add-iou", className="mt-2 text-center")
                ])
            ], className="data-card")
        ], lg=5, md=12),

        # Tabla de Historial
        dbc.Col([
            dbc.Card([
                dbc.CardHeader("Cuentas Pendientes"),
                # Ahora sí funciona porque generate_iou_table ya está definida arriba
                dbc.CardBody(id="iou-table-container", children=generate_iou_table(dm.get_iou_df())) 
            ], className="data-card")
        ], lg=7, md=12)
    ])
], fluid=True, className="page-container")


# -----------------------------------------------------------------------------
# 3. CALLBACKS
# -----------------------------------------------------------------------------

# Callback para Registrar Deuda/Cobro
@callback(
    [Output("msg-add-iou", "children"),
     Output("iou-table-container", "children"),
     Output("iou-summary-row", "children"),
     Output("iou-name", "value"),
     Output("iou-amount", "value")],
    [Input("btn-add-iou", "n_clicks")],
    [State("iou-name", "value"),
     State("iou-amount", "value"),
     State("iou-type", "value"),
     State("iou-due-date", "date"),
     State("iou-person-name", "value"),
     State("iou-description", "value")]
)
def add_iou_callback(n_clicks, name, amount, iou_type, due_date, person_name, description):
    if not n_clicks:
        # Inicialización por defecto (aunque el layout ya lo hace, esto cubre actualizaciones espontáneas si las hubiera)
        return "", generate_iou_table(dm.get_iou_df()), generate_summary_cards(), dash.no_update, dash.no_update

    # Validaciones
    if not all([name, amount, iou_type, person_name]):
        return html.Span("Faltan campos obligatorios.", className="text-danger"), generate_iou_table(dm.get_iou_df()), generate_summary_cards(), dash.no_update, dash.no_update

    try:
        amt = float(amount)
        if amt <= 0:
             return html.Span("El monto debe ser positivo.", className="text-danger"), generate_iou_table(dm.get_iou_df()), generate_summary_cards(), dash.no_update, dash.no_update
    except:
        return html.Span("Monto inválido", className="text-danger"), generate_iou_table(dm.get_iou_df()), generate_summary_cards(), dash.no_update, dash.no_update

    # Guardar
    success, msg = dm.add_iou(name, amt, iou_type, due_date, person_name, description)
    
    df_new = dm.get_iou_df()
    cards_new = generate_summary_cards()
    
    if success:
        return html.Span(msg, className="text-success"), generate_iou_table(df_new), cards_new, "", ""
    else:
        return html.Span(msg, className="text-danger"), generate_iou_table(df_new), cards_new, dash.no_update, dash.no_update


# Callback para Capturar el Clic en la Fila
@callback(
    Output("iou-viewing-id", "data"),
    [Input("iou-data-table", "active_cell")],
    [State("iou-data-table", "data")],
    prevent_initial_call=True
)
def handle_iou_click(active_cell, table_data):
    if active_cell is None:
        return no_update
    
    row_index = active_cell['row']
    col_id = active_cell['column_id']
    
    if col_id == 'action':
        iou_id = table_data[row_index]['id']
        return iou_id
    return no_update


# Callback para Abrir el Modal de Detalle
@callback(
    [Output("iou-detail-modal", "is_open"),
     Output("iou-detail-id-store", "data"),
     Output("iou-detail-type", "value"),
     Output("iou-detail-person-name", "value"),
     Output("iou-detail-name", "value"),
     Output("iou-detail-description", "value"),
     Output("iou-detail-amount", "value"),
     Output("iou-detail-current-amount", "value"),
     Output("iou-detail-due-date", "date"),
     Output("iou-detail-status", "value"),
     Output("iou-btn-save", "style"),
     Output("iou-btn-edit-mode", "style"),
     Output("iou-detail-msg", "children"),
     Output("iou-btn-mark-paid", "style")],
    [Input("iou-viewing-id", "data"),
     Input("iou-btn-close-detail", "n_clicks")],
    prevent_initial_call=True
)
def open_detail_modal(iou_id, close_click):
    trig_id = ctx.triggered_id
    
    if trig_id == "iou-btn-close-detail" or iou_id is None:
        return False, no_update, no_update, no_update, no_update, no_update, no_update, no_update, no_update, no_update, no_update, no_update, no_update, no_update
    
    if iou_id and trig_id == "iou-viewing-id":
        item = dm.get_iou_by_id(iou_id)
        if not item:
            return no_update
            
        save_style = {'display': 'none'}
        edit_style = {'display': 'inline-block'}
        paid_btn_style = {'display': 'none'} if item['status'] == 'Paid' else {'display': 'inline-block'}
        
        return (True, item['id'], item['type'], item['person_name'], item['name'], item['description'], item['amount'], item['current_amount'], item['due_date'], item['status'], save_style, edit_style, "", paid_btn_style)


# Callback Modo Edición
@callback(
    [Output("iou-detail-type", "disabled"),
     Output("iou-detail-person-name", "disabled"),
     Output("iou-detail-name", "disabled"),
     Output("iou-detail-description", "disabled"),
     Output("iou-detail-amount", "disabled"),
     Output("iou-detail-current-amount", "disabled"),
     Output("iou-detail-due-date", "disabled"),
     Output("iou-detail-status", "disabled"),
     Output("iou-btn-save", "style", allow_duplicate=True),
     Output("iou-btn-edit-mode", "style", allow_duplicate=True)],
    [Input("iou-btn-edit-mode", "n_clicks")],
    prevent_initial_call=True
)
def toggle_edit_mode(n_clicks):
    if n_clicks and n_clicks % 2 == 1:
        return (False, False, False, False, False, False, False, False, {'display': 'inline-block'}, {'display': 'none'})          
    else:
        return (True, True, True, True, True, True, True, True, {'display': 'none'}, {'display': 'inline-block'}) 


# Callback Borrar Trigger
@callback(
    [Output("iou-delete-modal", "is_open"),
     Output("iou-detail-modal", "is_open", allow_duplicate=True)],
    [Input("iou-btn-trigger-delete", "n_clicks"),
     Input("iou-btn-del-cancel", "n_clicks")],
    prevent_initial_call=True
)
def open_delete_modal(trigger_del, cancel_del):
    trig_id = ctx.triggered_id
    if trig_id == "iou-btn-trigger-delete": return True, False 
    if trig_id == "iou-btn-del-cancel": return False, True 
    return no_update, no_update


# Callback para GUARDAR o CONFIRMAR BORRADO (Actualiza Resumen)
@callback(
    [Output("iou-detail-modal", "is_open", allow_duplicate=True),
     Output("iou-delete-modal", "is_open", allow_duplicate=True),
     Output("iou-table-container", "children", allow_duplicate=True),
     Output("iou-summary-row", "children", allow_duplicate=True),
     Output("global-iou-toast", "is_open"), 
     Output("global-iou-toast", "children"),
     Output("global-iou-toast", "icon")],
    [Input("iou-btn-save", "n_clicks"),
     Input("iou-btn-del-confirm", "n_clicks"),
     Input("iou-btn-mark-paid", "n_clicks")],
    [State("iou-detail-id-store", "data"),
     State("iou-detail-name", "value"),
     State("iou-detail-amount", "value"),
     State("iou-detail-type", "value"),
     State("iou-detail-due-date", "date"),
     State("iou-detail-person-name", "value"),
     State("iou-detail-description", "value"),
     State("iou-detail-current-amount", "value"),
     State("iou-detail-status", "value")],
    prevent_initial_call=True
)
def handle_save_delete_flow(save_click, delete_click, paid_click, iou_id, name, amount, iou_type, due_date, person_name, description, current_amount, status):
    trig_id = ctx.triggered_id
    
    if not iou_id:
        return no_update, no_update, no_update, no_update, *ui_helpers.mensaje_alerta_exito("danger", "Error: ID no encontrado.")

    def refresh_all():
        return generate_iou_table(dm.get_iou_df()), generate_summary_cards()

    if trig_id == "iou-btn-mark-paid":
        success, msg = dm.update_iou(iou_id, name, amount, iou_type, due_date, person_name, description, 0.0, 'Paid')
        if success:
            table, cards = refresh_all()
            return False, False, table, cards, *ui_helpers.mensaje_alerta_exito("success", "Deuda marcada como pagada.")
        else:
            return no_update, no_update, no_update, no_update, *ui_helpers.mensaje_alerta_exito("danger", msg)

    if trig_id == "iou-btn-save":
        if not all([name, amount, iou_type, person_name]):
            return no_update, no_update, no_update, no_update, *ui_helpers.mensaje_alerta_exito("warning", "Faltan campos.")
        try:
            amt = float(amount)
            curr_amt = float(current_amount)
        except ValueError:
            return no_update, no_update, no_update, no_update, *ui_helpers.mensaje_alerta_exito("danger", "Monto inválido.")

        success, msg = dm.update_iou(iou_id, name, amt, iou_type, due_date, person_name, description, curr_amt, status)
        if success:
            table, cards = refresh_all()
            return False, False, table, cards, *ui_helpers.mensaje_alerta_exito("success", msg)
        else:
            return no_update, no_update, no_update, no_update, *ui_helpers.mensaje_alerta_exito("danger", msg)

    if trig_id == "iou-btn-del-confirm":
        success, msg = dm.delete_iou(iou_id)
        if success:
            table, cards = refresh_all()
            return False, False, table, cards, *ui_helpers.mensaje_alerta_exito("success", "Eliminada correctamente.")
        else:
            return no_update, False, no_update, no_update, *ui_helpers.mensaje_alerta_exito("danger", msg)

    return no_update, no_update, no_update, no_update, no_update, no_update, no_update