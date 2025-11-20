import dash
from dash import dcc, html, callback, Input, Output, State, no_update, ctx 
import dash_bootstrap_components as dbc
from dash import dash_table
from datetime import date
import backend.data_manager as dm 
import time 
from utils import ui_helpers 

# LISTA FIJA DE CATEGORÍAS MACRO
MAIN_CATEGORIES = [
    {'label': 'Costos Fijos', 'value': 'Costos Fijos'},
    {'label': 'Libres (Guilt Free)', 'value': 'Libres'},
    {'label': 'Inversión', 'value': 'Inversion'},
    {'label': 'Ahorro', 'value': 'Ahorro'},
    {'label': 'Deudas/Cobros', 'value': 'Deudas/Cobros'},
    {'label': 'Ingresos', 'value': 'Ingresos'} 
]

# --- MODAL 0: CREAR NUEVA CATEGORÍA PRINCIPAL ---
cat_modal = dbc.Modal([
    dbc.ModalHeader("Crear Nueva Categoría Principal"),
    dbc.ModalBody([
        dbc.Label("Nombre de la Categoría:"),
        dbc.Input(id="new-cat-name", placeholder="Ej. Viajes, Mascotas...", className="mb-3"),
    ]),
    dbc.ModalFooter([
        dbc.Button("Cancelar", id="btn-cat-cancel", outline=True),
        dbc.Button("Guardar", id="btn-cat-save", color="success", className="ms-2"),
    ])
], id="cat-modal", is_open=False, centered=True, size="sm")


# --- MODAL 1: CREAR SUBCATEGORÍA ---
subcat_modal = dbc.Modal([
    dbc.ModalHeader("Crear Nueva Subcategoría"),
    dbc.ModalBody([
        dbc.Label("Pertenece a la Categoría:"),
        dcc.Dropdown(id="new-subcat-parent-dd", className="mb-3 text-dark"),
        dbc.Label("Nombre de la Subcategoría:"),
        dbc.Input(id="new-subcat-name", placeholder="Ej. Netflix, Gasolina...", className="mb-3"),
    ]),
    dbc.ModalFooter([
        dbc.Button("Cancelar", id="btn-subcat-cancel", outline=True),
        dbc.Button("Guardar", id="btn-subcat-save", color="success", className="ms-2"),
    ])
], id="subcat-modal", is_open=False, centered=True, size="sm")


# --- MODAL 2: DETALLE / EDICIÓN DE TRANSACCIÓN ---
trans_detail_modal = dbc.Modal([
    dbc.ModalHeader(dbc.ModalTitle("Detalle de Transacción")),
    
    dbc.ModalBody([
        dcc.Store(id="trans-detail-id-store"), 

        dbc.Row([
            dbc.Col(dbc.Label("Fecha:"), width=3),
            dbc.Col(dcc.DatePickerSingle(id='trans-detail-date', display_format='YYYY-MM-DD', className='d-block'), width=9)
        ], className="mb-2"),
        
        dbc.Row([
            dbc.Col(dbc.Label("Tipo:"), width=3),
            dbc.Col(dbc.RadioItems(id="trans-detail-type", 
                                    options=[{"label": "Gasto", "value": "Expense"}, {"label": "Ingreso", "value": "Income"}],
                                    inline=True), width=9)
        ], className="mb-2"),

        dbc.Label("Categoría"),
        dcc.Dropdown(id="trans-detail-category", className="text-dark mb-2"),
        
        dbc.Label("Subcategoría"),
        dcc.Dropdown(id="trans-detail-subcategory", className="text-dark mb-2"),

        dbc.Label("Detalle (Opcional)"),
        dbc.Input(id="trans-detail-name", type="text", className="mb-2"),
        
        dbc.Label("Cuenta"),
        dcc.Dropdown(id="trans-detail-account-dd", className="mb-2 text-dark"),

        dbc.Label("Monto"),
        dbc.Input(id="trans-detail-amount", type="number", className="mb-2"),
        
        html.Div(id="trans-detail-msg", className="mt-2 text-center")
        
    ], id="trans-modal-body", style={"maxHeight": "70vh", "overflowY": "auto"}),

    dbc.ModalFooter([
        dbc.Button("Borrar", id="trans-btn-trigger-delete", color="danger"),
        dbc.Button("Guardar Edición", id="trans-btn-save-edit", color="success", className="ms-auto"),
        dbc.Button("Cerrar", id="trans-btn-close-detail", color="secondary", outline=True, className="ms-2"),
    ])
], id="trans-detail-modal", is_open=False, centered=True, size="md")


# --- MODAL 3: CONFIRMACIÓN BORRADO ---
trans_delete_modal = dbc.Modal([
    dbc.ModalHeader(dbc.ModalTitle("Confirmar Eliminación")),
    dbc.ModalBody("¿Estás seguro? El balance será corregido."),
    dbc.ModalFooter([
        dbc.Button("Cancelar", id="trans-btn-del-cancel", className="ms-auto", outline=True),
        dbc.Button("Sí, Borrar", id="trans-btn-del-confirm", color="danger"),
    ])
], id="trans-delete-modal", is_open=False, centered=True, size="sm")

# --- LAYOUT PRINCIPAL ---
layout = dbc.Container([
    # STORES
    dcc.Store(id='trans-viewing-id', data=None), 
    dcc.Store(id='trans-edit-success', data=0),
    dcc.Store(id='global-update-signal', data=0),
    ui_helpers.get_feedback_toast("trans-feedback-toast"),
    
    # INCLUSIÓN DE MODALES
    cat_modal,
    subcat_modal,
    trans_detail_modal,
    trans_delete_modal,

    html.H2("Registro de Transacciones", className="mb-4"),

    dbc.Row([
        # --- COLUMNA IZQUIERDA: FORMULARIO ---
        dbc.Col([
            dbc.Card([
                dbc.CardHeader("Nueva Transacción"),
                dbc.CardBody([
                    # 1. Fecha y Tipo
                    dbc.Row([
                        dbc.Col([
                            dbc.Label("Fecha"),
                            dcc.DatePickerSingle(id='input-date', date=date.today(), display_format='YYYY-MM-DD', className='mb-3 d-block'),
                        ], width=6),
                        dbc.Col([
                             dbc.Label("Tipo"),
                             dbc.RadioItems(id="input-trans-type", options=[{"label": "Gasto", "value": "Expense"}, {"label": "Ingreso", "value": "Income"}], value="Expense", inline=True, className="mb-3"),
                        ], width=6)
                    ]),

                    # 2. Categoría
                    dbc.Row([
                        dbc.Col([
                            dbc.Label("Categoría"),
                            dcc.Dropdown(id="input-category", placeholder="Seleccionar...", className="text-dark"),
                        ], width=10),
                        dbc.Col([
                            dbc.Button("+", id="btn-open-cat-modal", color="primary", outline=True, size="sm", className="mt-4 w-100", title="Crear categoría"),
                        ], width=2, className="ps-0")
                    ], className="mb-3"),

                    # 3. Subcategoría
                    dbc.Row([
                        dbc.Col([
                            dbc.Label("Subcategoría"),
                            dcc.Dropdown(id="input-subcategory", placeholder="Seleccionar...", className="text-dark"),
                        ], width=10),
                        dbc.Col([
                            dbc.Button("+", id="btn-open-subcat-modal", color="info", outline=True, size="sm", className="mt-4 w-100", title="Crear subcategoría"),
                        ], width=2, className="ps-0")
                    ], className="mb-3"),
                    
                    # 4. Detalle
                    dbc.Label("Detalle / Nota (Opcional)"),
                    dbc.Input(id="input-name", placeholder="Ej. Cena con amigos...", type="text", className="mb-3"),

                    # 5. Cuenta (ROW PROPIA)
                    dbc.Label("Cuenta de Pago/Destino"),
                    dcc.Dropdown(id="input-account-dd", placeholder="Seleccionar cuenta...", className="mb-3 text-dark"),

                    # 6. Monto (ROW PROPIA)
                    dbc.Label("Monto"),
                    dbc.Input(id="input-amount", placeholder="0.00", type="number", className="mb-4"),

                    # 7. Botón Registrar
                    dbc.Button("Registrar Transacción", id="btn-add-trans", color="success", className="w-100 py-2 fw-bold"),
                    html.Div(id="msg-add-trans", className="mt-2 text-center")
                ])
            ], className="data-card")
        ], lg=4, md=12, className="mb-4"),

        # --- COLUMNA DERECHA: TABLA ---
        dbc.Col([
            dbc.Card([
                dbc.CardHeader("Últimos Movimientos"),
                dbc.CardBody(id="trans-table-container")
            ], className="data-card h-100") 
        ], lg=8, md=12)
    ])
], fluid=True, className="page-container")


# --- FUNCIONES AUXILIARES GLOBALES (TABLA ACTUALIZADA) ---
def generate_table(dataframe):
    if dataframe.empty:
        # Placeholder vacío: Usamos 'category' para el mensaje
        data_to_render = [{'id': -1, 'category': 'No hay transacciones registradas.', 'subcategory': '', 'amount': 0.0, 'action': 'N/A'}]
        is_empty = True
    else:
        dataframe['action'] = "ℹ️"
        # Asegurar que si no hay subcategoría, muestre un guion o vacío para que no se rompa
        dataframe['subcategory'] = dataframe['subcategory'].fillna('')
        data_to_render = dataframe.to_dict('records')
        is_empty = False

    style_header_final = {'display': 'none'} if is_empty else {'backgroundColor': '#333', 'color': 'white'}
    style_data_final = {'display': 'none'} if is_empty else {'backgroundColor': '#2A2A2A', 'color': 'white'}

    return dash_table.DataTable(
        id='trans-data-table',
        data=data_to_render,
        columns=[
            {"name": "ID", "id": "id"}, 
            # NUEVAS COLUMNAS
            {"name": "Categoría", "id": "category"},
            {"name": "Subcategoría", "id": "subcategory"},
            {"name": "Monto", "id": "amount", "type": "numeric", "format": {"specifier": "$,.2f"}},
            {"name": "Info", "id": "action", "deletable": False, "selectable": False}
        ],
        style_header=style_header_final,
        style_data=style_data_final,
        style_table={'overflowX': 'auto', 'minWidth': '100%'},
        style_cell={
            'textAlign': 'left', 'border': '1px solid #444', 'whiteSpace': 'normal', 
            'overflow': 'hidden', 'textOverflow': 'ellipsis' 
        },
        style_data_conditional=[
            {'if': {'column_id': 'id'}, 'display': 'none'},
            
            # Estilos para el mensaje "No data" en la primera fila
            {'if': {'row_index': 0, 'filter_query': '{id} = -1'}, 'color': '#888', 'fontStyle': 'italic', 'height': '60px'},
            {'if': {'row_index': 0, 'filter_query': '{id} = -1', 'column_id': 'amount'}, 'display': 'none'},
            {'if': {'row_index': 0, 'filter_query': '{id} = -1', 'column_id': 'action'}, 'display': 'none'},
            
            # Colores de Gasto/Ingreso
            {'if': {'filter_query': '{type} = "Income"'}, 'color': '#00C851', 'fontWeight': 'bold'},
            {'if': {'filter_query': '{type} = "Expense"'}, 'color': '#ff4444', 'fontWeight': 'bold'},
            
            {'if': {'column_id': 'action'}, 'textAlign': 'center', 'cursor': 'pointer', 'fontWeight': 'bold'}
        ],
        style_header_conditional=[{'if': {'column_id': 'id'}, 'display': 'none'}],
        page_size=10,
    )


# ------------------------------------------------------------------------------
# CALLBACKS
# ------------------------------------------------------------------------------

# 1. Cargar Listas
@callback(
    [Output("input-account-dd", "options"),
     Output("input-category", "options"),     
     Output("new-subcat-parent-dd", "options")], 
    [Input("url", "pathname"),
     Input("global-update-signal", "data")]
)
def load_initial_data(pathname, signal):
    if pathname == "/transacciones":
        acc_opts = dm.get_account_options()
        cat_opts = dm.get_all_categories_options()
        return acc_opts, cat_opts, cat_opts
    return [], [], []

# 1A. Sync Listas en Modal
@callback(
    [Output("trans-detail-account-dd", "options"),
     Output("trans-detail-category", "options")],
    [Input("input-account-dd", "options"),
     Input("input-category", "options")]
)
def sync_modal_dropdowns(acc_opts, cat_opts):
    return acc_opts, cat_opts


# --- GESTIÓN DE CATEGORÍAS (MODAL CAT) ---
@callback(
    Output("cat-modal", "is_open"),
    [Input("btn-open-cat-modal", "n_clicks"), Input("btn-cat-cancel", "n_clicks"), Input("global-update-signal", "data")],
    State("cat-modal", "is_open"),
    prevent_initial_call=True
)
def toggle_cat_modal(open_c, cancel_c, signal, is_open):
    if ctx.triggered_id == "global-update-signal": return False
    if ctx.triggered_id == "btn-cat-cancel": return False
    return not is_open

@callback(
    Output("global-update-signal", "data", allow_duplicate=True),
    Output("trans-feedback-toast", "is_open", allow_duplicate=True),
    Output("trans-feedback-toast", "children", allow_duplicate=True),
    Output("trans-feedback-toast", "icon", allow_duplicate=True),
    Input("btn-cat-save", "n_clicks"),
    State("new-cat-name", "value"),
    State("global-update-signal", "data"),
    prevent_initial_call=True
)
def save_new_category(n_clicks, name, signal):
    if not name: return no_update, *ui_helpers.mensaje_alerta_exito("warning", "Escribe un nombre.")
    success, msg = dm.add_custom_category(name)
    if success: return (signal + 1), *ui_helpers.mensaje_alerta_exito("success", msg)
    return no_update, *ui_helpers.mensaje_alerta_exito("danger", msg)


# --- GESTIÓN DE SUBCATEGORÍAS (MODAL SUBCAT) ---
@callback(
    Output("subcat-modal", "is_open"),
    [Input("btn-open-subcat-modal", "n_clicks"), Input("btn-subcat-cancel", "n_clicks"), Input("global-update-signal", "data")],
    State("subcat-modal", "is_open"),
    prevent_initial_call=True
)
def toggle_subcat_modal(open_c, cancel_c, signal, is_open):
    if ctx.triggered_id == "global-update-signal": return False
    if ctx.triggered_id == "btn-subcat-cancel": return False
    return not is_open

@callback(
    Output("global-update-signal", "data", allow_duplicate=True), 
    Output("trans-feedback-toast", "is_open", allow_duplicate=True),
    Output("trans-feedback-toast", "children", allow_duplicate=True),
    Output("trans-feedback-toast", "icon", allow_duplicate=True),
    Input("btn-subcat-save", "n_clicks"),
    State("new-subcat-name", "value"),
    State("new-subcat-parent-dd", "value"),
    State("global-update-signal", "data"),
    prevent_initial_call=True
)
def save_new_subcategory(n_clicks, name, parent, signal):
    if not name or not parent: return no_update, *ui_helpers.mensaje_alerta_exito("warning", "Faltan datos.")
    success, msg = dm.add_custom_subcategory(name, parent)
    if success: return (signal + 1), *ui_helpers.mensaje_alerta_exito("success", msg)
    return no_update, *ui_helpers.mensaje_alerta_exito("danger", msg)


# --- ACTUALIZACIÓN DINÁMICA DE DROPDOWN SUBCATEGORÍA ---
@callback(
    Output("input-subcategory", "options"),
    Input("input-category", "value"),
    Input("global-update-signal", "data")
)
def update_subcats_main(parent, sig):
    if not parent: return []
    return dm.get_subcategories_by_parent(parent)

@callback(
    Output("trans-detail-subcategory", "options"),
    Input("trans-detail-category", "value"),
    Input("global-update-signal", "data")
)
def update_subcats_modal(parent, sig):
    if not parent: return []
    return dm.get_subcategories_by_parent(parent)


# 2. Registrar Transacción
@callback(
    [Output("msg-add-trans", "children"),
     Output("trans-table-container", "children"),
     Output("input-name", "value"),
     Output("input-amount", "value")],
    [Input("btn-add-trans", "n_clicks")],
    [State("input-date", "date"),
     State("input-name", "value"),
     State("input-amount", "value"),
     State("input-category", "value"),
     State("input-trans-type", "value"),
     State("input-account-dd", "value"),
     State("input-subcategory", "value")]
)
def add_transaction_callback(n_clicks, date_val, name, amount, category, t_type, acc_id, subcat):
    df = dm.get_transactions_df()
    if not n_clicks: return "", generate_table(df), no_update, no_update

    if not all([date_val, amount, category, t_type, acc_id]):
        return html.Span("Faltan campos obligatorios.", className="text-danger"), generate_table(df), no_update, no_update
    
    final_name = name if name else "-"

    try: amt = float(amount)
    except: return html.Span("Monto inválido", className="text-danger"), generate_table(df), no_update, no_update

    success, msg = dm.add_transaction(date_val, final_name, amt, category, t_type, acc_id, subcat)
    
    if success:
        df_new = dm.get_transactions_df()
        return html.Span(msg, className="text-success"), generate_table(df_new), "", ""
    else:
        return html.Span(msg, className="text-danger"), generate_table(df), no_update, no_update


# 3. CAPTURAR ID y ABRIR MODAL
@callback(
    [Output('trans-viewing-id', 'data'),
     Output("trans-detail-modal", "is_open", allow_duplicate=True)],
    [Input('trans-data-table', 'active_cell'),
     Input('trans-btn-close-detail', 'n_clicks'),
     Input('trans-edit-success', 'data')],
    [State('trans-data-table', 'data')],
    prevent_initial_call=True
)
def handle_trans_click_and_open_modal(active_cell, close_click, success_signal, table_data):
    trig_id = ctx.triggered_id
    if trig_id in ['trans-btn-close-detail', 'trans-edit-success']: return no_update, False
    
    if trig_id == 'trans-data-table' and active_cell is not None:
        if active_cell['column_id'] == 'action':
            row_index = active_cell['row']
            trans_id = table_data[row_index]['id']
            return trans_id, True 
    return no_update, no_update


# 4. Popular Modal
@callback(
    [Output("trans-detail-id-store", "data"),
     Output("trans-detail-date", "date"),
     Output("trans-detail-type", "value"),
     Output("trans-detail-name", "value"),
     Output("trans-detail-amount", "value"),
     Output("trans-detail-category", "value"),
     Output("trans-detail-account-dd", "value"),
     Output("trans-detail-subcategory", "value")],
    [Input('trans-viewing-id', 'data')],
    prevent_initial_call=True
)
def populate_trans_modal(trans_id):
    if trans_id is not None and ctx.triggered_id == 'trans-viewing-id':
        trans = dm.get_transaction_by_id(trans_id)
        if not trans: return no_update
        
        subcat_val = trans.get('subcategory', None)
        return (trans['id'], trans['date'], trans['type'], trans['name'], 
                trans['amount'], trans['category'], trans['account_id'], subcat_val)
    return [no_update]*8


# 5. Abrir/Cerrar Modal Borrado
@callback(
    [Output("trans-delete-modal", "is_open"),
     Output("trans-detail-modal", "is_open", allow_duplicate=True)],
    [Input("trans-btn-trigger-delete", "n_clicks"),
     Input("trans-btn-del-cancel", "n_clicks")],
    prevent_initial_call=True
)
def open_delete_modal(trigger_del, cancel_del):
    trig_id = ctx.triggered_id
    if trig_id == "trans-btn-trigger-delete": return True, False 
    if trig_id == "trans-btn-del-cancel": return False, True 
    return no_update, no_update


# 6. GUARDAR EDICIÓN o CONFIRMAR BORRADO
@callback(
    [Output('trans-edit-success', 'data'), 
     Output("trans-delete-modal", "is_open", allow_duplicate=True),
     Output("trans-table-container", "children", allow_duplicate=True),
     Output("trans-feedback-toast", "is_open"),
     Output("trans-feedback-toast", "children"),
     Output("trans-feedback-toast", "icon")],
    [Input("trans-btn-save-edit", "n_clicks"),
     Input("trans-btn-del-confirm", "n_clicks")],
    [State('trans-detail-id-store', 'data'),
     State('trans-detail-date', 'date'),
     State('trans-detail-name', 'value'),
     State('trans-detail-amount', 'value'),
     State('trans-detail-category', 'value'),
     State('trans-detail-type', 'value'),
     State("trans-detail-account-dd", "value"),
     State("trans-detail-subcategory", "value")],
    prevent_initial_call=True
)
def handle_save_delete_flow(save_click, delete_click, trans_id, date, name, amount, category, t_type, acc_id, subcat):
    trig_id = ctx.triggered_id
    ts = int(time.time() * 1000)

    if not trans_id: return no_update, no_update, no_update, *ui_helpers.mensaje_alerta_exito("danger", "Error ID.")
    
    final_name = name if name else "-"

    if trig_id == "trans-btn-save-edit":
        if not all([date, amount, category, t_type, acc_id]):
            return no_update, no_update, no_update, *ui_helpers.mensaje_alerta_exito("warning", "Faltan campos.")
        try: amt = float(amount)
        except: return no_update, no_update, no_update, *ui_helpers.mensaje_alerta_exito("danger", "Monto inválido.")

        success, msg = dm.update_transaction(trans_id, date, final_name, amt, category, t_type, acc_id, subcat)
        
        if success: return ts, False, generate_table(dm.get_transactions_df()), *ui_helpers.mensaje_alerta_exito("success", msg)
        else: return no_update, no_update, no_update, *ui_helpers.mensaje_alerta_exito("danger", msg)

    if trig_id == "trans-btn-del-confirm":
        success, msg = dm.delete_transaction(trans_id)
        if success: return ts, False, generate_table(dm.get_transactions_df()), *ui_helpers.mensaje_alerta_exito("success", msg)
        else: return no_update, False, no_update, *ui_helpers.mensaje_alerta_exito("danger", msg)

    return no_update, no_update, no_update, no_update, no_update, no_update