# accounts_debit.py
import dash
from dash import dcc, html, callback, Input, Output, State, no_update, ctx, ALL
import dash_bootstrap_components as dbc
import backend.data_manager as dm
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd

# --- MODALES ---

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
        
        # Inclusión de Modales
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
                dbc.Input(id="deb-search-input", placeholder="🔍 Buscar cuenta por nombre...", type="text"),
                width=8, lg=9, className="mb-3"
            ),
            dbc.Col(
                dbc.Button("+ Agregar Cuenta", id="btn-open-add-account", color="primary", className="w-100 fw-bold"),
                width=4, lg=3, className="mb-3"
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

        # Botones de Orden (Horizontales)
        up_btn = dbc.Button("◀", id={'type': 'deb-up', 'index': row['id']}, size="sm", color="link", className="p-0 text-decoration-none text-muted me-1")
        down_btn = dbc.Button("▶", id={'type': 'deb-down', 'index': row['id']}, size="sm", color="link", className="p-0 text-decoration-none text-muted")

        # DISEÑO DE TARJETA (BOX)
        card_content = dbc.Card([
            dbc.CardBody([
                # Cabecera: Icono + Banco + Flechas
                dbc.Row([
                    dbc.Col(html.Div(icon, className="h5 mb-0"), width="auto"),
                    dbc.Col(html.Small(bank_display, className="text-muted fw-bold text-uppercase small"), className="d-flex align-items-center"),
                    dbc.Col([up_btn, down_btn], width="auto", className="text-end")
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