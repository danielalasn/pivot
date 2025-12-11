# transactions.py
import dash
from dash import dcc, html, callback, Input, Output, State, no_update, ctx 
import dash_bootstrap_components as dbc
from dash import dash_table
from datetime import date, datetime
import backend.data_manager as dm 
import time 
from utils import ui_helpers 
import pandas as pd

# LISTA FIJA DE CATEGORÍAS MACRO
MAIN_CATEGORIES = [
    {'label': 'Libres', 'value': 'Libres'},
    {'label': 'Costos Fijos', 'value': 'Costos Fijos'},
    {'label': 'Inversión', 'value': 'Inversion'},
    {'label': 'Ahorro', 'value': 'Ahorro'},
    {'label': 'Deuda/Cobro', 'value': 'Deuda/Cobro'},
    {'label': 'Salario', 'value': 'Salario'},
    # 'Transferencia' se oculta visualmente pero existe en sistema
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
        dcc.Dropdown(
            id="new-subcat-parent-dd", 
            className="mb-3 text-dark"),
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
# transactions.py

# ... (imports y modales siguen igual) ...

layout = dbc.Container([
    # STORES y TOASTS
    dcc.Store(id='trans-viewing-id', data=None), 
    dcc.Store(id='trans-edit-success', data=0),
    dcc.Store(id='global-update-signal', data=0),
    ui_helpers.get_feedback_toast("trans-feedback-toast"),
    
    # MODALES
    cat_modal,
    subcat_modal,
    trans_detail_modal,
    trans_delete_modal,

    # 1. ENCABEZADO
    html.Div([
        html.H2("Registro de Transacciones", className="mb-0 text-primary"),
    ], className="px-4 pt-4 pb-3"),

    # 2. CONTENIDO PRINCIPAL
    html.Div([
        dbc.Row([
            
            # --- COLUMNA IZQUIERDA: FORMULARIO (ALTURA AUTOMÁTICA) ---
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader("Nueva Transacción"),
                    dbc.CardBody([
                        # ... CONTENIDO DEL FORMULARIO (Se mantiene igual) ...
                        dbc.Row([
                            dbc.Col([dbc.Label("Fecha", className="small mb-0"), dcc.DatePickerSingle(id='input-date', date=date.today(), display_format='YYYY-MM-DD', className='d-block w-100 small-date-picker')], width=6, className="pe-1"),
                            dbc.Col([dbc.Label("Hora", className="small mb-0"), dbc.Input(id="input-time", type="time", value=datetime.now().strftime("%H:%M"), size="sm")], width=6, className="ps-1"),
                        ], className="mb-2"), 

                        dbc.Row([
                            dbc.Col([dbc.Label("Tipo", className="small mb-0"), dcc.Dropdown(id="input-trans-type", options=[{"label": "Gasto", "value": "Expense"}, {"label": "Ingreso", "value": "Income"}, {"label": "Mov. Interno", "value": "Transfer"}], value="Expense", clearable=False, className="text-dark small-dropdown")], width=6),
                            dbc.Col([dbc.Label("Monto $", className="small mb-0 fw-bold text-info"), dbc.Input(id="input-amount", placeholder="0.00", type="number", size="sm")], width=6),
                        ], className="mb-2"),

                        dbc.Row([
                            dbc.Col([dbc.Label(id="label-account-src", children="Cuenta", className="small mb-0"), dcc.Dropdown(id="input-account-dd", placeholder="Origen...", className="text-dark small-dropdown", optionHeight=65)], width=6),
                            dbc.Col([html.Div(id="dest-account-container", children=[dbc.Label("Hacia (Destino)", className="small mb-0 fw-bold text-primary"), dcc.Dropdown(id="input-account-dest-dd", placeholder="Destino...", className="text-dark small-dropdown", optionHeight=65)], style={"display": "none"})], width=6),
                        ], className="mb-3 g-2"),

                        html.Div(id="category-input-container", children=[
                            dbc.Row([
                                dbc.Col([dbc.Label("Categoría", className="small mb-0"), dbc.Row([dbc.Col(dcc.Dropdown(id="input-category", placeholder="Ver...", className="text-dark small-dropdown"), width=10), dbc.Col(dbc.Button("+", id="btn-open-cat-modal", color="primary", outline=True, size="sm", className="w-100"), width=2, className="d-grid ps-1")], className="g-0 align-items-end")], width=6),
                                dbc.Col([dbc.Label("Subcategoría", className="small mb-0"), dbc.Row([dbc.Col(dcc.Dropdown(id="input-subcategory", placeholder="Ver...", className="text-dark small-dropdown"), width=10), dbc.Col(dbc.Button("+", id="btn-open-subcat-modal", color="info", outline=True, size="sm", className="w-100"), width=2, className="d-grid ps-1")], className="g-0 align-items-end")], width=6),
                            ], className="mb-3 g-2"),
                        ]),

                        dbc.Row([dbc.Col([dbc.Label("Nota / Detalle", className="small mb-0"), dbc.Input(id="input-name", placeholder="Ej. Pago de tarjeta...", type="text", size="sm")], width=12)], className="mb-4"),

                        dbc.Button("Registrar", id="btn-add-trans", color="success", className="w-100 fw-bold", size="md"),
                        html.Div(id="msg-add-trans", className="mt-1 text-center small")
                        # ... FIN CONTENIDO FORMULARIO ...

                    ]) # Quitamos clases de scroll aquí porque la tarjeta ya no es fija
                ], className="data-card shadow-sm") # 🚨 CAMBIO: QUITE 'h-100'. Ahora se ajusta al contenido.
            
            # Agregamos estilo inline para que si la pantalla es MUY pequeña, el formulario tenga su propio scroll
            ], lg=5, md=12, style={"maxHeight": "100%", "overflowY": "auto"}), 

            # --- COLUMNA DERECHA: TABLA (ALTURA COMPLETA) ---
            dbc.Col([
                dbc.Card([
                    dbc.CardBody(id="trans-table-container", 
                                style={"padding": "0", "height": "100%", "overflowY": "auto"},
                                className="custom-scrollbar") 
                ], className="data-card shadow-sm") # 🚨 CAMBIO: MANTUVE 'h-100'. La tabla sí debe llegar al fondo.
            ], lg=7, md=12, className="h-100") 

        ], className="h-100 g-3") 

    ], className="px-4 pb-4 flex-grow-1 overflow-hidden") 

], fluid=True, className="p-0 page-container d-flex flex-column vh-100 overflow-hidden")


def generate_table(dataframe):
    if dataframe.empty:
        # Fila dummy para evitar errores visuales
        data_to_render = [{
            'id': -1, 'date_display': '-', 'type_label': '', 
            'category': 'No hay transacciones registradas.', 
            'subcategory': '', 'amount': 0.0, 'action': 'N/A', 'type': 'Expense'
        }]
        is_empty = True
    else:
        # 1. ASEGURAR ORDEN CRONOLÓGICO (FECHA + HORA)
        # Convertimos a datetime real para que el ordenamiento respete la hora
        dataframe['date'] = pd.to_datetime(dataframe['date'], format='mixed')
        
        # Ordenamos descendente (Lo más reciente arriba)
        dataframe = dataframe.sort_values(by='date', ascending=False)

        # 2. CREAR COLUMNA VISUAL (CON HORA)
        # Cambiamos el formato para incluir hora y minuto
        dataframe['date_display'] = dataframe['date'].dt.strftime('%Y-%m-%d %H:%M')

        dataframe['action'] = "ℹ️"
        dataframe['subcategory'] = dataframe['subcategory'].fillna('')
        
        # Mapeo de tipos
        type_map = {'Expense': 'Gasto', 'Income': 'Ingreso', 'Transfer': 'Mov. Interno'}
        dataframe['type_label'] = dataframe['type'].map(type_map).fillna(dataframe['type'])
        
        data_to_render = dataframe.to_dict('records')
        is_empty = False

    style_header_final = {'display': 'none'} if is_empty else {'backgroundColor': '#333', 'color': 'white'}
    style_data_final = {'display': 'none'} if is_empty else {'backgroundColor': '#2A2A2A', 'color': 'white'}

    return dash_table.DataTable(
        id='trans-data-table',
        data=data_to_render,
        columns=[
            {"name": "ID", "id": "id"}, 
            # --- AQUÍ MOSTRAMOS LA FECHA LIMPIA (date_display) ---
            {"name": "Fecha", "id": "date_display"}, 
            {"name": "Tipo", "id": "type_label"}, 
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
            'overflow': 'hidden', 'textOverflow': 'ellipsis', 'padding': '8px'
        },
        style_data_conditional=[
            {'if': {'column_id': 'id'}, 'display': 'none'},
            
            # Ajustes para la fila "No data"
            {'if': {'row_index': 0, 'filter_query': '{id} = -1'}, 'color': '#888', 'fontStyle': 'italic', 'height': '60px'},
            {'if': {'row_index': 0, 'filter_query': '{id} = -1', 'column_id': 'amount'}, 'display': 'none'},
            {'if': {'row_index': 0, 'filter_query': '{id} = -1', 'column_id': 'action'}, 'display': 'none'},
            {'if': {'row_index': 0, 'filter_query': '{id} = -1', 'column_id': 'date_display'}, 'display': 'none'}, # Ocultar fecha en vacío
            
            # Colores según tipo
            {'if': {'filter_query': '{type} = "Income"'}, 'color': '#00C851', 'fontWeight': 'bold'},
            {'if': {'filter_query': '{type} = "Expense"'}, 'color': '#ff4444', 'fontWeight': 'bold'},
            {'if': {'filter_query': '{type} = "Transfer"'}, 'color': '#33b5e5', 'fontWeight': 'bold'}, 
            
            {'if': {'column_id': 'action'}, 'textAlign': 'center', 'cursor': 'pointer', 'fontWeight': 'bold', 'color': '#33b5e5'}
        ],
        style_header_conditional=[{'if': {'column_id': 'id'}, 'display': 'none'}],
        page_size=10,
    )

# ------------------------------------------------------------------------------
# CALLBACKS
# ------------------------------------------------------------------------------

# 1. Cargar Listas (ACTUALIZADO: Carga Destination Dropdown)
@callback(
    [Output("input-account-dd", "options"),
     Output("input-category", "options"),     
     Output("new-subcat-parent-dd", "options"),
     Output("input-account-dest-dd", "options")], # <--- NUEVO OUTPUT
    [Input("url", "pathname"),
     Input("global-update-signal", "data")]
)
def load_initial_data(pathname, signal):
    if pathname == "/transacciones":
        acc_opts = dm.get_account_options()
        cat_opts = dm.get_all_categories_options()
        return acc_opts, cat_opts, cat_opts, acc_opts # Regresamos acc_opts para el destino también
    return [], [], [], []

# 1A. Sync Listas en Modal
@callback(
    [Output("trans-detail-account-dd", "options"),
     Output("trans-detail-category", "options")],
    [Input("input-account-dd", "options"),
     Input("input-category", "options")]
)
def sync_modal_dropdowns(acc_opts, cat_opts):
    return acc_opts, cat_opts

# --- NUEVO: CONTROL VISIBILIDAD PARA TRANSFERENCIAS ---
@callback(
    [Output("dest-account-container", "style"),
     Output("category-input-container", "style"),
     Output("label-account-src", "children")],
    Input("input-trans-type", "value")
)
def toggle_transfer_controls(trans_type):
    if trans_type == "Transfer":
        # Mostrar destino, Ocultar categorías, cambiar etiqueta
        return {"display": "block"}, {"display": "none"}, "Desde (Origen)"
    else:
        # Ocultar destino, Mostrar categorías, etiqueta normal
        return {"display": "none"}, {"display": "block"}, "Cuenta"

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


# 2. Registrar Transacción (ACTUALIZADO CON LÓGICA DE TRANSFERENCIA)
@callback(
    [Output("msg-add-trans", "children"),
     Output("trans-table-container", "children"),
     Output("input-name", "value"),
     Output("input-amount", "value")],
    [Input("btn-add-trans", "n_clicks")],
    [State("input-date", "date"),
     State("input-time", "value"),
     State("input-name", "value"),
     State("input-amount", "value"),
     State("input-category", "value"),
     State("input-trans-type", "value"),
     State("input-account-dd", "value"),
     State("input-subcategory", "value"),
     State("input-account-dest-dd", "value")] # <--- NUEVO ESTADO: Destino
)
def add_transaction_callback(n_clicks, date_val, time_val, name, amount, category, t_type, acc_id, subcat, dest_acc_id):
    df = dm.get_transactions_df()
    if not n_clicks: return "", generate_table(df), no_update, no_update

    # Validaciones básicas
    if not all([date_val, amount, t_type, acc_id]):
        return html.Span("Faltan campos obligatorios.", className="text-danger"), generate_table(df), no_update, no_update
    
    # --- COMBINAR FECHA Y HORA ---
    final_time = time_val if time_val else "00:00"
    full_date_str = f"{date_val} {final_time}" # <--- ¡Aquí creaste la variable correcta!

    try: amt = float(amount)
    except: return html.Span("Monto inválido", className="text-danger"), generate_table(df), no_update, no_update
    
    final_name = name if name else "-"

    # --- LÓGICA DIFERENCIADA ---
    if t_type == "Transfer":
        # CASO: TRANSFERENCIA
        if not dest_acc_id:
             return html.Span("Selecciona la cuenta destino.", className="text-danger"), generate_table(df), no_update, no_update
        if str(acc_id) == str(dest_acc_id):
             return html.Span("Origen y destino son iguales.", className="text-danger"), generate_table(df), no_update, no_update

        # Llamada a función backend de transferencia
        success, msg = dm.add_transfer(full_date_str, final_name, amt, acc_id, dest_acc_id)

    else:
        # CASO: INGRESO O GASTO NORMAL
        if not category:
            return html.Span("Falta la categoría.", className="text-danger"), generate_table(df), no_update, no_update
        
        success, msg = dm.add_transaction(full_date_str, final_name, amt, category, t_type, acc_id, subcat)
    # RESPUESTA
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