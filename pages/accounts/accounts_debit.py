# accounts_debit.py
import dash
from dash import dcc, html, callback, Input, Output, State, no_update, ctx, ALL
import dash_bootstrap_components as dbc
import backend.data_manager as dm
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd

# Layout para Cuentas de Ahorro y Efectivo
layout = dbc.Card([
    dbc.CardBody([
        # --- Stores y Estados ---
        dcc.Store(id='deb-editing-id', data=None),
        dcc.Store(id='deb-delete-id', data=None),
        dcc.Store(id='deb-update-signal', data=0),
        
        # --- MINI DASHBOARD DE DÉBITO ---
        html.H5("Distribución de Activos", className="mb-3 text-primary"),
        dbc.Row([
            # Gráfico 1: Distribución por Banco/Efectivo (Dona de Saldo Actual)
            dbc.Col(
                dbc.Card(
                    dbc.CardBody([
                        html.H6("Distribución por Nombre de Activo", className="card-title text-muted"),
                        dcc.Graph(id="deb-graph-asset-type", config={'displayModeBar': False}, style={'height': '300px'})
                    ]),
                    className="data-card"
                ),
                lg=6, md=12, sm=12, className="mb-4"
            ),
            dbc.Col(
                dbc.Card(
                    dbc.CardBody([
                        html.H6("Activos por Banco/Efectivo", className="card-title text-muted"),
                        dcc.Graph(id="deb-graph-bank", config={'displayModeBar': False}, style={'height': '300px'})
                    ]),
                    className="data-card"
                ),
                lg=6, md=12, sm=12, className="mb-4"
            )
        ]),

        # --- MODAL 1: DETALLES (VER) ---
        dbc.Modal([
            dbc.ModalHeader(dbc.ModalTitle("Detalle de Cuenta")),
            dbc.ModalBody(id="deb-detail-body"), 
            dbc.ModalFooter([
                dbc.Button("Editar", id="deb-btn-trigger-edit", color="info", className="me-auto"),
                dbc.Button("Eliminar", id="deb-btn-trigger-delete", color="danger"),
                dbc.Button("Cerrar", id="deb-btn-close-detail", color="secondary", outline=True, className="ms-2"),
            ])
        ], id="deb-detail-modal", is_open=False, centered=True, size="sm"),

        # --- MODAL 2: CONFIRMAR BORRADO ---
        dbc.Modal([
            dbc.ModalHeader("Eliminar Cuenta"),
            dbc.ModalBody("¿Estás seguro que deseas eliminar esta cuenta permanentemente?", id="deb-modal-msg"),
            dbc.ModalFooter([
                dbc.Button("Cancelar", id="deb-btn-cancel-del", className="ms-auto"),
                dbc.Button("Sí, Eliminar", id="deb-btn-confirm-del", color="danger", className="ms-2"),
            ])
        ], id="deb-modal-delete", is_open=False, centered=True, size="sm"),

        dbc.Row([
            # --- COLUMNA IZQUIERDA: FORMULARIO ---
            dbc.Col([
                html.H5("Gestión de Cuentas", className="mb-3 text-primary"),
                
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

                dbc.Label("Saldo Actual"),
                dbc.Input(id="deb-balance", type="number", placeholder="0.00", className="mb-3"),

                dbc.Button("Guardar Cambios", id="deb-btn-save", color="primary", className="w-100"),
                dbc.Button("Cancelar Edición", id="deb-btn-cancel", color="secondary", outline=True, className="w-100 mt-2", style={"display": "none"}),
                html.Div(id="deb-msg", className="mt-2 text-center")

            ], md=4, className="border-end border-secondary pe-4"),

            # --- COLUMNA DERECHA: LISTA DE CARDS ---
            dbc.Col([
                html.H5("Mis Cuentas", className="mb-3"),
                html.Div(id="deb-cards-container", 
                         className="d-grid gap-3",
                         style={
                        "maxHeight": "55vh",
                        "overflowY": "auto" 
                    }
                    ) 
                
            ], md=8, className="ps-4")
        ])
    ])
])

# --- CALLBACKS ---

# 1. Visibilidad Banco
@callback(
    [Output("deb-collapse-bank", "is_open"), Output("deb-collapse-custom", "is_open")],
    [Input("deb-type", "value"), Input("deb-bank", "value")]
)
def deb_vis(dtype, dbank):
    return (dtype != "Cash"), (dbank == "Otros" and dtype != "Cash")

# 2. Generar Cards (Triggered por url y deb-msg)
@callback(Output("deb-cards-container", "children"), [Input("deb-msg", "children"), Input("url", "pathname")])
def deb_load_cards(msg, path):
    df = dm.get_accounts_by_category("Debit")
    if df.empty: return html.Div("No hay cuentas.", className="text-muted fst-italic")

    cards = []
    for i, row in df.iterrows():
        icon = "💰" if row['type'] == "Cash" else "🏦"
        saldo_fmt = f"${row['current_balance']:,.2f}"
        bank_display = row['bank_name'] if row['type'] != "Cash" else "Efectivo"

        up_btn = dbc.Button("⬆️", id={'type': 'deb-up', 'index': row['id']}, size="sm", color="link", className="p-0 text-decoration-none text-muted")
        down_btn = dbc.Button("⬇️", id={'type': 'deb-down', 'index': row['id']}, size="sm", color="link", className="p-0 text-decoration-none text-muted")

        card_wrapper = html.Div([
            dbc.Card(
                dbc.CardBody([
                    dbc.Row([
                        # ÁREA 1: Flechas
                        dbc.Col([
                            up_btn, 
                            html.Div(style={"height": "2px"}), 
                            down_btn
                        ], width="auto", className="d-flex flex-column border-end pe-2 me-2"),
                        
                        # ÁREA 2: Contenido Clickeable
                        dbc.Col(
                            html.Div([
                                dbc.Row([
                                    dbc.Col(html.Div(icon, className="display-6"), width="auto", className="d-flex align-items-center pe-0"),
                                    dbc.Col([html.H5(row['name'], className="mb-0 fw-bold"), html.Small(bank_display, className="text-muted")], className="d-flex flex-column justify-content-center"),
                                    dbc.Col([html.H4(saldo_fmt, className="mb-0 text-success text-end"), html.Small("Saldo", className="text-muted d-block text-end")], width="auto", className="d-flex flex-column justify-content-center")
                                ])
                            ], 
                            id={'type': 'deb-card-item', 'index': row['id']}, 
                            n_clicks=0,
                            style={"cursor": "pointer", "height": "100%", "width": "100%"}
                            ),
                            className="flex-grow-1"
                        )
                    ], className="g-0 align-items-center")
                ]), 
                className="data-card zoom-on-hover"
            )
        ], id={'type': 'deb-card-item', 'index': row['id']}, n_clicks=0, style={"cursor": "pointer"})
        cards.append(card_wrapper)
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

# 4. Detalle (Abrir Modal)
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
        ])
        return True, content, cid 
    return no_update

# 5. Limpiar ID de edición
@callback(Output("deb-editing-id", "data", allow_duplicate=True), Input("deb-btn-close-detail", "n_clicks"), prevent_initial_call=True)
def deb_clear_id_on_close(n): return None

# 6. Borrar
@callback(Output("deb-modal-delete", "is_open"), [Input("deb-btn-trigger-delete", "n_clicks"), Input("deb-btn-cancel-del", "n_clicks"), Input("deb-btn-confirm-del", "n_clicks")], prevent_initial_call=True)
def deb_del_modal(trig, cancel, confirm): return True if ctx.triggered_id == "deb-btn-trigger-delete" else False

@callback(Output("deb-msg", "children", allow_duplicate=True), Input("deb-btn-confirm-del", "n_clicks"), State("deb-delete-id", "data"), prevent_initial_call=True)
def deb_exec_del(n, did):
    if n and did:
        dm.delete_account(did)
        return html.Span("Eliminado", className="text-warning")
    return no_update

# 7. Poblar Formulario
@callback(
    [Output("deb-name", "value"), Output("deb-type", "value"), Output("deb-balance", "value"),
     Output("deb-bank", "value"), Output("deb-bank-custom", "value"),
     Output("deb-btn-save", "children"), Output("deb-btn-cancel", "style"),
     Output("deb-editing-id", "data", allow_duplicate=True)], 
    [Input("deb-btn-trigger-edit", "n_clicks"), Input("deb-btn-cancel", "n_clicks"), Input("deb-btn-save", "n_clicks")],
    [State("deb-delete-id", "data"), State("deb-editing-id", "data")],
    prevent_initial_call=True
)
def deb_populate_form(n_edit, n_cancel, n_save, viewed_id, current_edit_id):
    trig = ctx.triggered_id
    if trig == "deb-btn-cancel" or trig == "deb-btn-save":
        return "", "Debit", "", None, "", "Guardar Cambios", {"display": "none"}, None
    
    if trig == "deb-btn-trigger-edit" and viewed_id:
        df = dm.get_accounts_by_category("Debit")
        try:
            row = df[df['id'] == viewed_id].iloc[0]
            bank_sel = row['bank_name'] if row['bank_name'] in ["BAC","Cuscatlan","Agricola","Davivienda"] else "Otros"
            bank_c = row['bank_name'] if bank_sel == "Otros" else ""
            return row['name'], row['type'], row['current_balance'], bank_sel, bank_c, "Actualizar Cuenta", {"display": "block"}, viewed_id
        except: pass
            
    return no_update

# 8. GUARDAR DB (CORREGIDO)
@callback(
    Output("deb-msg", "children"), Input("deb-btn-save", "n_clicks"),
    [State("deb-name", "value"), State("deb-type", "value"), State("deb-balance", "value"),
     State("deb-bank", "value"), State("deb-bank-custom", "value"), State("deb-editing-id", "data")],
    prevent_initial_call=True
)
def deb_save_db(n, name, dtype, bal, bank, bank_cust, edit_id):
    if not n: return no_update
    if not name: return html.Span("Falta nombre", className="text-danger")
    bank_n = bank_cust if bank == "Otros" and dtype != "Cash" else (bank if dtype != "Cash" else "-")
    val = float(bal) if bal else 0.0
    
    if edit_id:
        dm.update_account(edit_id, name, dtype, val, bank_n, 0, None, None, 0, 0, 0, 0, 0)
        return html.Span("Actualizado", className="text-success")
    else:
        dm.add_account(name, dtype, val, bank_n, 0, None, None, 0, 0, 0, 0, 0)
        return html.Span("Creado", className="text-success")

# 9. --- CALLBACKS DEL MINI-DASHBOARD ---
@callback(
    [Output("deb-graph-bank", "figure"),
     Output("deb-graph-asset-type", "figure")], # CAMBIAMOS EL OUTPUT
    [Input("url", "pathname"),
     Input("deb-msg", "children")]
)
def update_debit_dashboard(pathname, msg):
    if pathname != "/cuentas":
        return no_update, no_update
    
    # --- GRÁFICO 1: BANCO/EFECTIVO (Dona de Distribución de Saldo) ---
    df_bank = dm.get_debit_bank_summary()
    
    if df_bank.empty or df_bank['total_balance'].sum() <= 0:
        fig_bank = go.Figure()
        fig_bank.update_layout(template="plotly_dark", title="Sin saldos activos", plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", font={"color": "gray"})
    else:
        df_bank['display_name'] = df_bank['bank_name'].apply(lambda x: 'Efectivo' if x == '-' else x)
        fig_bank = px.pie(
            df_bank, 
            names='display_name', 
            values='total_balance',
            hole=0.4, 
            # title='Distribución de Saldo por Banco',
            color_discrete_sequence=px.colors.qualitative.Pastel
        )
        fig_bank.update_layout(
            template="plotly_dark",
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            margin=dict(t=30, b=0, l=0, r=0),
            legend_orientation="h",
            legend_y=-0.1
        )
        fig_bank.update_traces(textinfo='percent+label')

    # --- GRÁFICO 2: DISTRIBUCIÓN POR TIPO DE ACTIVO (NUEVO) ---
    df_account_name = dm.get_account_name_summary() # <<-- USAMOS LA NUEVA FUNCIÓN -->>
    
    if df_account_name.empty or df_account_name['total_balance'].sum() <= 0:
        fig_account_name = go.Figure()
        fig_account_name.update_layout(template="plotly_dark", title="Sin activos registrados", plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", font={"color": "gray"})
    else:
        # Usamos la columna 'name' para los nombres y 'total_balance' para los valores
        fig_account_name = px.pie(
            df_account_name, 
            names='name',
            values='total_balance',
            hole=0.4, 
            # title='Distribución por Nombre de Cuenta',
            color_discrete_sequence=px.colors.qualitative.Vivid
        )
        fig_account_name.update_layout(
            template="plotly_dark",
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            margin=dict(t=30, b=0, l=0, r=0),
            legend_orientation="h",
            legend_y=-0.1
        )
        fig_account_name.update_traces(textinfo='percent+label')

    # Aseguramos que el retorno use la nueva variable fig_account_name
    return fig_bank, fig_account_name