# accounts_debit.py
import dash
from dash import dcc, html, callback, Input, Output, State, no_update, ctx, ALL
import dash_bootstrap_components as dbc
import backend.data_manager as dm
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd

# --- MODALES ---
reorder_modal = dbc.Modal([
    dbc.ModalHeader("Organizar Cuentas"),
    dbc.ModalBody(dbc.ListGroup(id="deb-reorder-list", flush=True)), # Aquí cargaremos la lista simple
    dbc.ModalFooter(
        dbc.Button("Listo", id="deb-btn-reorder-done", color="primary", className="ms-auto")
    )
], id="deb-reorder-modal", is_open=False, centered=True, scrollable=True)

# Modal 1: Detalles (Ver)
detail_modal = dbc.Modal([
    dbc.ModalHeader(dbc.ModalTitle("Detalle de Cuenta")),
    dbc.ModalBody(id="deb-detail-body"), 
    dbc.ModalFooter([
        dbc.Button("Editar", id="deb-btn-trigger-edit", color="info", className="me-auto"),
        dbc.Button("Eliminar", id="deb-btn-trigger-delete", color="danger"),
        dbc.Button("Cerrar", id="deb-btn-close-detail", color="secondary", outline=True, className="ms-2"),
    ])
], id="deb-detail-modal", is_open=False, centered=True, size="sm")

# Modal 2: Confirmar Borrado
delete_modal = dbc.Modal([
    dbc.ModalHeader("Eliminar Cuenta"),
    dbc.ModalBody("¿Estás seguro que deseas eliminar esta cuenta permanentemente?", id="deb-modal-msg"),
    dbc.ModalFooter([
        dbc.Button("Cancelar", id="deb-btn-cancel-del", className="ms-auto"),
        dbc.Button("Sí, Eliminar", id="deb-btn-confirm-del", color="danger", className="ms-2"),
    ])
], id="deb-modal-delete", is_open=False, centered=True, size="sm")

# Modal 3: Nueva / Editar Cuenta (NUEVO)
add_account_modal = dbc.Modal([
    dbc.ModalHeader(dbc.ModalTitle(id="add-account-modal-title", children="Nueva Cuenta")),
    dbc.ModalBody([
        dbc.Label("Tipo"),
        dbc.Select(
            id="deb-type",
            options=[
                {"label": "Cuenta de Ahorros / Débito", "value": "Debit"},
                {"label": "Efectivo / Wallet", "value": "Cash"},
            ],
            value="Debit",
            className="mb-3"
        ),

        dbc.Label("Nombre"),
        dbc.Input(id="deb-name", placeholder="Ej. Ahorros, Billetera...", className="mb-3"),

        dbc.Collapse([
            dbc.Label("Banco"),
            dbc.Select(
                id="deb-bank",
                options=[
                    {"label": "BAC", "value": "BAC"},
                    {"label": "Cuscatlan", "value": "Cuscatlan"},
                    {"label": "Agricola", "value": "Agricola"},
                    {"label": "Davivienda", "value": "Davivienda"},
                    {"label": "Otro", "value": "Otros"},
                ],
                value=None,
                placeholder="Seleccionar Banco...",
                className="mb-2"
            ),
            dbc.Collapse(
                dbc.Input(id="deb-bank-custom", placeholder="Nombre del banco...", className="mb-3"),
                id="deb-collapse-custom", is_open=False
            )
        ], id="deb-collapse-bank", is_open=True),

        dbc.Label("Saldo Actual ($)"),
        dbc.Input(id="deb-balance", type="number", placeholder="0.00", className="mb-3"),
        
        html.Div(id="deb-form-feedback", className="text-center mt-2")
    ]),
    dbc.ModalFooter([
        dbc.Button("Cancelar", id="deb-btn-cancel", outline=True, className="me-auto"),
        dbc.Button("Guardar Cuenta", id="deb-btn-save", color="primary"),
    ])
], id="add-account-modal", is_open=False, centered=True, backdrop="static", size="sm")


# --- LAYOUT PRINCIPAL ---
layout = dbc.Card([
    dbc.CardBody([
        # Stores y Estados
        dcc.Store(id='deb-editing-id', data=None),
        dcc.Store(id='deb-delete-id', data=None),
        dcc.Store(id='deb-update-signal', data=0),
        dcc.Store(id='deb-reorder-temp-store', data=[]),
        
        # Inclusión de Modales
        reorder_modal,
        detail_modal,
        delete_modal,
        add_account_modal,
        
        # --- MINI DASHBOARD DE DÉBITO ---
        html.H5("Distribución de Activos", className="mb-3 text-primary"),
        dbc.Row([
            dbc.Col(
                dbc.Card(
                    dbc.CardBody([
                        html.H6("Por Nombre de Activo", className="card-title text-muted"),
                        dcc.Graph(id="deb-graph-asset-type", config={'displayModeBar': False}, style={'height': '250px'})
                    ]),
                    className="data-card"
                ),
                lg=6, md=12, sm=12, className="mb-4"
            ),
            dbc.Col(
                dbc.Card(
                    dbc.CardBody([
                        html.H6("Por Banco/Efectivo", className="card-title text-muted"),
                        dcc.Graph(id="deb-graph-bank", config={'displayModeBar': False}, style={'height': '250px'})
                    ]),
                    className="data-card"
                ),
                lg=6, md=12, sm=12, className="mb-4"
            )
        ]),

        html.Hr(),

        # --- BARRA DE HERRAMIENTAS (BUSCADOR + BOTÓN AGREGAR) ---
        dbc.Row([
            dbc.Col(
                dbc.Input(id="deb-search-input", placeholder="🔍 Buscar cuenta...", type="text"),
                width=7, lg=8, className="mb-3"
            ),
            # Botón Organizar (NUEVO)
            dbc.Col(
                dbc.Button(html.I(className="bi bi-arrow-down-up"), id="btn-open-reorder", color="secondary", outline=True, className="w-100"),
                width=2, lg=1, className="mb-3 px-1"
            ),
            # Botón Agregar (EXISTENTE)
            dbc.Col(
                dbc.Button("+ Agregar", id="btn-open-add-account", color="primary", className="w-100 fw-bold"),
                width=3, lg=3, className="mb-3"
            ),
        ], className="align-items-center mb-2"),

        # --- LISTA DE CUENTAS (FULL WIDTH) ---
        dbc.Row([
            dbc.Col([
                html.H5("Mis Cuentas", className="mb-3"),
                # 🚨 CORRECCIÓN: Usamos dbc.Row con g-3 para la cuadrícula sin scroll
                dbc.Row(id="deb-cards-container", className="g-3") 
            ], width=12)
        ]),
        
        html.Div(id="deb-msg", style={"display": "none"}) # Store dummy para mensajes
    ])
])

# ==============================================================================
# CALLBACKS
# ==============================================================================

# 1. Visibilidad Banco (Dentro del Modal)
@callback(
    [Output("deb-collapse-bank", "is_open"), Output("deb-collapse-custom", "is_open")],
    [Input("deb-type", "value"), Input("deb-bank", "value")]
)
def deb_vis(dtype, dbank):
    return (dtype != "Cash"), (dbank == "Otros" and dtype != "Cash")

# 2. Generar Cards con Buscador
# 2. Generar Cards con Buscador (GRID 4x1)
@callback(
    Output("deb-cards-container", "children"), 
    [Input("deb-msg", "children"), Input("url", "pathname"), Input("deb-search-input", "value")]
)
def deb_load_cards(msg, path, search_term):
    df = dm.get_accounts_by_category("Debit")
    if df.empty: return html.Div("No hay cuentas registradas.", className="text-muted fst-italic text-center py-5")

    # Lógica de Filtrado
    if search_term:
        search_lower = search_term.lower()
        df = df[df['name'].str.lower().str.contains(search_lower) | df['bank_name'].str.lower().str.contains(search_lower)]
        if df.empty: return html.Div("No se encontraron cuentas.", className="text-muted fst-italic text-center")

    cards = []
    for i, row in df.iterrows():
        icon = "💰" if row['type'] == "Cash" else "🏦"
        bank_display = row['bank_name'] if row['type'] != "Cash" else "EFECTIVO"
        saldo_fmt = f"${row['current_balance']:,.2f}"

        # DISEÑO DE TARJETA (BOX)
        card_content = dbc.Card([
            dbc.CardBody([
                # Cabecera: Icono + Banco + Flechas
                dbc.Row([
                    dbc.Col(html.Div(icon, className="h5 mb-0"), width="auto"),
                    dbc.Col(html.Small(bank_display, className="text-muted fw-bold text-uppercase small"), className="d-flex align-items-center"),
                ], className="mb-3 align-items-center"),
                
                # Nombre de la Cuenta
                html.H5(row['name'], className="card-title fw-bold text-center text-white text-truncate mb-3"),
                
                html.Hr(className="my-2 border-secondary"),
                
                # Saldo Grande
                html.Div([
                    html.Small("Saldo Actual", className="text-success d-block small"),
                    html.H3(saldo_fmt, className="text-success fw-bold mb-0")
                ], className="text-center mt-3")

            ], className="p-3 d-flex flex-column h-100"),
            
            # Overlay para clic
            html.Div(id={'type': 'deb-card-item', 'index': row['id']}, className="stretched-link", style={"cursor": "pointer"})
        ], className="data-card h-100 zoom-on-hover")

        # 🚨 GRID RESPONSIVO 🚨
        # xs=12 (Móvil), md=6 (Tablet), lg=3 (Desktop: 4 por fila)
        col_wrapper = dbc.Col(card_content, xs=12, md=6, lg=3)
        cards.append(col_wrapper)
        
    return cards


# 3. Reordenar
@callback(
    Output("deb-msg", "children", allow_duplicate=True),
    [Input({'type': 'deb-up', 'index': ALL}, 'n_clicks'), Input({'type': 'deb-down', 'index': ALL}, 'n_clicks')],
    prevent_initial_call=True
)
def deb_reorder(n_up, n_down):
    if not ctx.triggered or not ctx.triggered[0]['value']: return no_update
    trig_id = ctx.triggered_id
    dm.change_account_order(trig_id['index'], 'up' if trig_id['type']=='deb-up' else 'down', "Debit")
    return "Orden actualizado"

# 4. Detalle (Abrir Modal Detalle)
@callback(
    [Output("deb-detail-modal", "is_open"), Output("deb-detail-body", "children"), Output("deb-delete-id", "data")],
    [Input({'type': 'deb-card-item', 'index': ALL}, 'n_clicks'), Input("deb-btn-close-detail", "n_clicks"), Input("deb-btn-trigger-edit", "n_clicks"), Input("deb-btn-trigger-delete", "n_clicks")],
    prevent_initial_call=True
)
def deb_handle_card_click(n, close, edit, delete):
    trig = ctx.triggered_id
    if trig in ["deb-btn-close-detail", "deb-btn-trigger-edit", "deb-btn-trigger-delete"]: return False, no_update, no_update
    
    if isinstance(trig, dict) and trig['type'] == 'deb-card-item':
        if not ctx.triggered[0]['value']: return no_update
        
        cid = trig['index']
        df = dm.get_accounts_by_category("Debit")
        row = df[df['id'] == cid].iloc[0]
        
        content = html.Div([
            html.H2(f"${row['current_balance']:,.2f}", className="text-success text-center mb-4"),
            dbc.Row([dbc.Col("Nombre:", className="fw-bold", width=4), dbc.Col(row['name'], width=8)], className="mb-2 border-bottom pb-2"),
            dbc.Row([dbc.Col("Banco:", className="fw-bold", width=4), dbc.Col(row['bank_name'], width=8)], className="mb-2"),
            dbc.Row([dbc.Col("Tipo:", className="fw-bold", width=4), dbc.Col(row['type'], width=8)], className="mb-2"),
        ])
        return True, content, cid 
    return no_update

# 5. Abrir/Cerrar Modal AGREGAR/EDITAR
@callback(
    [Output("add-account-modal", "is_open"),
     Output("add-account-modal-title", "children")],
    [Input("btn-open-add-account", "n_clicks"), Input("deb-btn-cancel", "n_clicks"), Input("deb-btn-trigger-edit", "n_clicks")],
    State("add-account-modal", "is_open"),
    prevent_initial_call=True
)
def toggle_add_modal(open_click, cancel_click, edit_click, is_open):
    trig = ctx.triggered_id
    if trig == "btn-open-add-account": return True, "Nueva Cuenta"
    if trig == "deb-btn-trigger-edit": return True, "Editar Cuenta" # Abre el modal en modo edición
    if trig == "deb-btn-cancel": return False, "Nueva Cuenta"
    return no_update, no_update

# 6. Poblar Formulario (Edición o Limpieza)
@callback(
    [Output("deb-name", "value"), Output("deb-type", "value"), Output("deb-balance", "value"),
     Output("deb-bank", "value"), Output("deb-bank-custom", "value"),
     Output("deb-btn-save", "children"), 
     Output("deb-editing-id", "data", allow_duplicate=True)], 
    [Input("btn-open-add-account", "n_clicks"), Input("deb-btn-trigger-edit", "n_clicks")],
    [State("deb-delete-id", "data")], # delete-id tiene el ID de la cuenta visualizada actualmente
    prevent_initial_call=True
)
def deb_populate_form(n_add, n_edit, viewed_id):
    trig = ctx.triggered_id
    
    # Modo Nueva Cuenta: Limpiar campos
    if trig == "btn-open-add-account":
        return "", "Debit", "", None, "", "Guardar Cuenta", None
    
    # Modo Edición: Cargar datos
    if trig == "deb-btn-trigger-edit" and viewed_id:
        df = dm.get_accounts_by_category("Debit")
        try:
            row = df[df['id'] == viewed_id].iloc[0]
            bank_sel = row['bank_name'] if row['bank_name'] in ["BAC","Cuscatlan","Agricola","Davivienda"] else "Otros"
            bank_c = row['bank_name'] if bank_sel == "Otros" else ""
            return row['name'], row['type'], row['current_balance'], bank_sel, bank_c, "Actualizar Cuenta", viewed_id
        except: pass
            
    return no_update

# 7. GUARDAR DB (Crear o Actualizar)
@callback(
    [Output("deb-msg", "children"), Output("add-account-modal", "is_open", allow_duplicate=True)], 
    Input("deb-btn-save", "n_clicks"),
    [State("deb-name", "value"), State("deb-type", "value"), State("deb-balance", "value"),
     State("deb-bank", "value"), State("deb-bank-custom", "value"), State("deb-editing-id", "data")],
    prevent_initial_call=True
)
def deb_save_db(n, name, dtype, bal, bank, bank_cust, edit_id):
    if not n: return no_update, no_update
    if not name: return html.Span("Falta nombre", className="text-danger"), True
    
    bank_n = bank_cust if bank == "Otros" and dtype != "Cash" else (bank if dtype != "Cash" else "-")
    val = float(bal) if bal else 0.0

    if edit_id:
        dm.update_account(edit_id, name, dtype, val, bank_n, 0, None, None, 0, 0)
        msg = html.Span("Actualizado", className="text-success")
    else:
        dm.add_account(name, dtype, val, bank_n, 0, None, None, 0, 0)
        msg = html.Span("Creado", className="text-success")
    
    return msg, False # Cierra el modal
# 8. Borrar
@callback(Output("deb-modal-delete", "is_open"), [Input("deb-btn-trigger-delete", "n_clicks"), Input("deb-btn-cancel-del", "n_clicks"), Input("deb-btn-confirm-del", "n_clicks")], prevent_initial_call=True)
def deb_del_modal(trig, cancel, confirm): return True if ctx.triggered_id == "deb-btn-trigger-delete" else False

@callback(
    [Output("deb-msg", "children", allow_duplicate=True), Output("deb-detail-modal", "is_open", allow_duplicate=True)],
    Input("deb-btn-confirm-del", "n_clicks"), State("deb-delete-id", "data"), prevent_initial_call=True
)
def deb_exec_del(n, did):
    if n and did:
        dm.delete_account(did)
        return html.Span("Eliminado", className="text-warning"), False # Cierra modal detalle
    return no_update, no_update

# 9. MINI DASHBOARD
@callback(
    [Output("deb-graph-bank", "figure"),
     Output("deb-graph-asset-type", "figure")],
    [Input("url", "pathname"),
     Input("deb-msg", "children")]
)
def update_debit_dashboard(pathname, msg):
    if pathname != "/cuentas": return no_update, no_update
    
    # Gráfico 1: Banco
    df_bank = dm.get_debit_bank_summary()
    if df_bank.empty or df_bank['total_balance'].sum() <= 0:
        fig_bank = go.Figure().update_layout(template="plotly_dark", title="Sin saldos", plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", font={"color": "gray"})
    else:
        df_bank['display_name'] = df_bank['bank_name'].apply(lambda x: 'Efectivo' if x == '-' else x)
        fig_bank = px.pie(df_bank, names='display_name', values='total_balance', hole=0.4, color_discrete_sequence=px.colors.qualitative.Pastel)
        fig_bank.update_layout(template="plotly_dark", plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", margin=dict(t=30, b=0, l=0, r=0), legend_orientation="h", legend_y=-0.1)
        fig_bank.update_traces(textinfo='percent+label')

    # Gráfico 2: Nombre Cuenta
    df_account_name = dm.get_account_name_summary()
    if df_account_name.empty or df_account_name['total_balance'].sum() <= 0:
        fig_account_name = go.Figure().update_layout(template="plotly_dark", title="Sin activos", plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", font={"color": "gray"})
    else:
        fig_account_name = px.pie(df_account_name, names='name', values='total_balance', hole=0.4, color_discrete_sequence=px.colors.qualitative.Vivid)
        fig_account_name.update_layout(template="plotly_dark", plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", margin=dict(t=30, b=0, l=0, r=0), legend_orientation="h", legend_y=-0.1)
        fig_account_name.update_traces(textinfo='percent+label')

    return fig_bank, fig_account_name

# --- CALLBACKS PARA REORDENAR (Lógica en Memoria) ---

# 1. ABRIR MODAL E INICIALIZAR EL STORE (Carga datos de DB)
@callback(
    [Output("deb-reorder-modal", "is_open"), 
     Output("deb-reorder-temp-store", "data")], 
    [Input("btn-open-reorder", "n_clicks"), 
     Input("deb-btn-reorder-done", "n_clicks")],
    State("deb-reorder-modal", "is_open"),
    prevent_initial_call=True
)
def toggle_reorder_modal_init(n_open, n_done, is_open):
    trig = ctx.triggered_id
    
    # CERRAR: Si apretamos "Listo"
    if trig == "deb-btn-reorder-done":
        return False, no_update

    # ABRIR: Cargamos datos frescos de la DB al Store
    if trig == "btn-open-reorder":
        df = dm.get_accounts_by_category("Debit")
        # Guardamos: [{'id': 1, 'name': 'Ahorro', 'bank_name': 'BAC'}, ...]
        data_list = df[['id', 'name', 'bank_name']].to_dict('records')
        return True, data_list

    return no_update, no_update


# 2. MOVER ITEMS ARRIBA/ABAJO (Solo modifica el Store, NO la DB)
@callback(
    Output("deb-reorder-temp-store", "data", allow_duplicate=True),
    [Input({'type': 'deb-reorder-up', 'index': ALL}, 'n_clicks'), 
     Input({'type': 'deb-reorder-down', 'index': ALL}, 'n_clicks')],
    State("deb-reorder-temp-store", "data"),
    prevent_initial_call=True
)
def update_temp_order_store(n_up, n_down, current_data):
    if not ctx.triggered or not current_data: return no_update
    
    trig_dict = ctx.triggered_id
    clicked_id = trig_dict['index']
    direction = 'up' if trig_dict['type'] == 'deb-reorder-up' else 'down'
    
    # Buscar índice
    idx = next((i for i, item in enumerate(current_data) if item['id'] == clicked_id), -1)
    if idx == -1: return no_update

    new_data = current_data.copy()
    
    # Swap Arriba
    if direction == 'up' and idx > 0:
        new_data[idx], new_data[idx-1] = new_data[idx-1], new_data[idx]
    
    # Swap Abajo
    elif direction == 'down' and idx < len(new_data) - 1:
        new_data[idx], new_data[idx+1] = new_data[idx+1], new_data[idx]
        
    return new_data


# 3. RENDERIZAR LISTA VISUAL (Escucha cambios en el Store)
@callback(
    Output("deb-reorder-list", "children"),
    Input("deb-reorder-temp-store", "data")
)
def render_reorder_list_visual(data_list):
    if not data_list: return []
    
    items = []
    for item in data_list:
        # Mostrar Banco visualmente
        bank_label = item.get('bank_name', '')
        if bank_label == '-': bank_label = 'Efectivo'
        
        li = dbc.ListGroupItem([
            dbc.Row([
                # Nombre y Banco
                dbc.Col([
                    html.Span(item['name'], className="fw-bold d-block"),
                    html.Small(bank_label, className="text-muted fst-italic") 
                ], width=True),
                
                # Botones Flechas
                dbc.Col([
                    dbc.Button("▲", id={'type': 'deb-reorder-up', 'index': item['id']}, size="sm", color="light", className="me-1 border"),
                    dbc.Button("▼", id={'type': 'deb-reorder-down', 'index': item['id']}, size="sm", color="light", className="border")
                ], width="auto")
            ], className="align-items-center")
        ])
        items.append(li)
        
    return items


# 4. GUARDAR CAMBIOS EN DB (Al hacer clic en "Listo")
@callback(
    Output("deb-msg", "children", allow_duplicate=True), # Dispara recarga de cards
    Input("deb-btn-reorder-done", "n_clicks"),
    State("deb-reorder-temp-store", "data"),
    prevent_initial_call=True
)
def save_reorder_to_db(n_clicks, final_data):
    if not n_clicks or not final_data: return no_update
    
    # Extraer IDs en el nuevo orden
    ordered_ids = [item['id'] for item in final_data]
    
    # Guardar en DB de una sola vez
    dm.batch_update_account_orders(ordered_ids)
    
    return "Orden guardado exitosamente"