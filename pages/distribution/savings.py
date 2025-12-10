<<<<<<< HEAD
# pages/distribution/savings.py
import dash
from dash import dcc, html, callback, Input, Output, State, no_update, ctx, ALL
import dash_bootstrap_components as dbc
import backend.data_manager as dm
from utils import ui_helpers 
from datetime import date, datetime

# ==============================================================================
# 1. MODALES
# ==============================================================================

# --- MODAL: AGREGAR / EDITAR META (TU CÓDIGO ORIGINAL) ---
sv_modal = dbc.Modal([
    dbc.ModalHeader(dbc.ModalTitle("Configurar Ahorro")),
    dbc.ModalBody([
        dbc.Label("Nombre"),
        dbc.Input(id="sv-name", placeholder="Ej. Viaje, Fondo de Emergencia...", className="mb-3"),

        dbc.Label("Tipo de Ahorro", className="fw-bold text-primary"),
        dbc.RadioItems(
            id="sv-mode",
            options=[
                {"label": "Meta con Fecha (Objetivo Fijo)", "value": "Date"},
                {"label": "Hábito / Recurrente ($ Fijo)", "value": "Fixed"},
                {"label": "Hábito / Proporcional (% Ingreso)", "value": "Percentage"},
            ],
            value="Date",
            inline=False,
            className="mb-3"
        ),
        
        # Inputs Dinámicos (Tu lógica original)
        html.Div([
            dbc.Row([
                dbc.Col([dbc.Label("Monto Objetivo ($)"), dbc.Input(id="sv-target", type="number", placeholder="0.00")], width=6),
                dbc.Col([dbc.Label("Fecha Límite"), dcc.DatePickerSingle(id="sv-date", display_format='YYYY-MM-DD', className="d-block", placeholder="Seleccionar...")], width=6),
            ], className="mb-3"),
        ], id="div-sv-goal-inputs"),

        html.Div([
            dbc.Label("Monto a guardar mensualmente ($)"),
            dbc.Input(id="sv-fixed-val", type="number", placeholder="Ej. 50.00"),
            dbc.FormText("Este monto se sugerirá cada mes indefinidamente."),
        ], id="div-sv-fixed", style={"display": "none"}),

        html.Div([
            dbc.Label("Porcentaje del Ingreso a guardar (%)"),
            dbc.Input(id="sv-pct-val", type="number", placeholder="Ej. 10"),
            dbc.FormText("Calculado sobre el ingreso que registres cada vez."),
        ], id="div-sv-pct", style={"display": "none"}),

        html.Hr(),
        dbc.Label("Dinero ya acumulado (Saldo Actual)"),
        dbc.Input(id="sv-saved", type="number", placeholder="0.00", value=0),

        dcc.Store(id="sv-edit-id", data=None),
        html.Div(id="sv-modal-feedback", className="text-center mt-2")
    ]),
    dbc.ModalFooter([
        dbc.Button("Cancelar", id="sv-btn-cancel", outline=True),
        dbc.Button("Guardar", id="sv-btn-save", color="primary", className="ms-2"),
    ])
], id="sv-modal", is_open=False, centered=True, size="md")


# --- MODAL: RETIRAR / USAR DINERO (NUEVO) ---
withdraw_modal = dbc.Modal([
    dbc.ModalHeader(dbc.ModalTitle("Usar / Retirar Ahorros")),
    dbc.ModalBody([
        html.H5(id="wd-title-label", className="text-primary text-center mb-3"),
        
        # 1. Monto y Cuenta Origen
        dbc.Row([
            dbc.Col([dbc.Label("Monto a sacar ($)"), dbc.Input(id="wd-amount", type="number", min=0, className="mb-2")], width=6),
            dbc.Col([dbc.Label("Desde Cuenta"), dcc.Dropdown(id="wd-source-acc", placeholder="Donde está el dinero", className="text-dark")], width=6),
        ], className="mb-3"),

        # 2. Selector de Tipo: Gasto vs Transferencia
        dbc.Label("¿Qué harás con el dinero?"),
        dbc.RadioItems(
            id="wd-type-selector",
            options=[
                {"label": "Gastar (Compra)", "value": "expense"},
                {"label": "Mover a otra cuenta", "value": "transfer"},
            ],
            value="expense",
            inline=True,
            className="mb-3"
        ),

        # 3. Campos dinámicos para GASTO
        dbc.Collapse([
            dbc.Card([dbc.CardBody([
                dbc.Row([
                    dbc.Col([dbc.Label("Categoría"), dcc.Dropdown(id="wd-category", placeholder="Ej. Guilt Free...", className="text-dark")], width=6),
                    dbc.Col([dbc.Label("Subcategoría"), dcc.Dropdown(id="wd-subcategory", placeholder="Opcional", className="text-dark")], width=6),
                ], className="mb-2"),
                dbc.Label("Nota / Descripción"),
                dbc.Input(id="wd-note", placeholder="Ej. Boletos de avión", type="text"),
            ])], className="bg-light border-0")
        ], id="wd-collapse-expense", is_open=True),

        # 4. Campos dinámicos para TRANSFERENCIA
        dbc.Collapse([
            dbc.Card([dbc.CardBody([
                dbc.Label("Cuenta Destino"),
                dcc.Dropdown(id="wd-dest-acc", placeholder="A dónde va el dinero...", className="text-dark"),
            ])], className="bg-light border-0")
        ], id="wd-collapse-transfer", is_open=False),
        
        dcc.Store(id="wd-target-id", data=None),
    ]),
    dbc.ModalFooter([
        dbc.Button("Cancelar", id="wd-btn-cancel", outline=True),
        dbc.Button("Confirmar Retiro", id="wd-btn-confirm", color="danger"),
    ])
], id="withdraw-modal", is_open=False, centered=True)


# --- MODAL BORRAR (TU CÓDIGO ORIGINAL) ---
sv_delete_modal = dbc.Modal([
    dbc.ModalHeader("Eliminar Ahorro"),
    dbc.ModalBody("¿Seguro? Se borrará el registro de la meta."),
    dbc.ModalFooter([
        dbc.Button("Cancelar", id="sv-btn-del-cancel", outline=True),
        dbc.Button("Sí, Eliminar", id="sv-btn-del-confirm", color="danger", className="ms-2"),
    ])
], id="sv-delete-modal", is_open=False, centered=True, size="sm")


# ==============================================================================
# 2. LAYOUT
# ==============================================================================
layout = html.Div([
    ui_helpers.get_feedback_toast("sv-feedback-toast"), 
    dcc.Store(id="sv-update-signal", data=0),
    dcc.Store(id="sv-delete-id", data=None),
    
    # Modales
    sv_modal,
    sv_delete_modal,
    withdraw_modal, # <--- Agregado el nuevo modal

    html.Br(),
    
    # --- DASHBOARD GLOBAL (TU CÓDIGO ORIGINAL) ---
    dbc.Card([
        dbc.CardBody([
            html.H5("Monitor de Ahorros", className="card-title text-success mb-4"),
            dbc.Row([
                # Col 1: Dinero Real
                dbc.Col([
                    dbc.Label("Cuenta de Ahorros (Real):"),
                    dcc.Dropdown(id="sv-account-selector", placeholder="Selecciona...", className="text-dark mb-2"),
                    html.Small("Saldo Real:", className="text-muted d-block"),
                    html.H3(id="sv-real-balance", className="text-white")
                ], md=4, className="border-end border-secondary"),

                # Col 2: Metas (Virtual)
                dbc.Col([
                    html.Small("Total Acumulado (Todas las categorías):", className="text-muted d-block"),
                    html.H3(id="sv-virtual-total", className="text-warning mb-0"),
                    
                    html.Div([
                        html.Span("Meta Global Definida: ", className="text-muted small me-1"),
                        html.Span(id="sv-total-target", className="fw-bold text-info"),
                    ], className="mb-3"),

                    dbc.Progress(id="sv-global-progress", value=0, label="0%", color="success", className="mt-1", style={"height": "10px"})
                ], md=4, className="border-end border-secondary text-center"),

                # Col 3: Diferencia
                dbc.Col([
                    html.Small("Diferencia (Real vs Virtual):", className="text-muted d-block"),
                    html.H3(id="sv-gap", className="fw-bold"),
                    html.Div(id="sv-gap-msg", className="small")
                ], md=4, className="text-center"),
            ])
        ])
    ], className="mb-4 metric-card"),

    # LISTA DE CARDS
    dbc.Row([
        dbc.Col(html.H4("Mis Ahorros & Metas"), width=True),
        dbc.Col(dbc.Button("+ Nuevo Ahorro", id="sv-btn-add", color="success"), width="auto"),
    ], className="mb-3 align-items-center"),
    
    html.Div(id="sv-list-container")
])


# ==============================================================================
# 3. CALLBACKS ORIGINALES (Manteniendo tu lógica)
# ==============================================================================

# 1. MOSTRAR/OCULTAR INPUTS SEGÚN TIPO
@callback(
    [Output("div-sv-goal-inputs", "style"), Output("div-sv-fixed", "style"), Output("div-sv-pct", "style")],
    Input("sv-mode", "value")
)
def toggle_inputs(mode):
    hide = {"display": "none"}
    show = {"display": "block", "marginBottom": "1rem"}
    if mode == 'Date': return show, hide, hide
    if mode == 'Fixed': return hide, show, hide
    if mode == 'Percentage': return hide, hide, show
    return show, hide, hide


# 2. CARGAR CUENTAS Y DASHBOARD (Incluye carga de categorías para retiro)
@callback(
    [Output("sv-account-selector", "options"), 
     Output("sv-account-selector", "value"),
     Output("wd-category", "options")], # <--- NUEVO: Cargar opciones para el modal de retiro
    Input("url", "pathname")
)
def load_sv_options(path):
    if not path or "distribucion" not in path: return no_update, no_update, no_update
    acc_opts = dm.get_account_options()
    sv_acc = dm.get_user_sv_fund_account()
    cat_opts = dm.get_all_categories_options() # <--- NUEVO
    return acc_opts, sv_acc, cat_opts

@callback(
    Output("sv-update-signal", "data", allow_duplicate=True), 
    Input("sv-account-selector", "value"), 
    prevent_initial_call=True
)
def save_sv_pref(acc_id):
    if acc_id: dm.update_user_sv_fund_account(acc_id)
    return no_update

@callback(
    [Output("sv-real-balance", "children"), Output("sv-virtual-total", "children"),
     Output("sv-total-target", "children"), Output("sv-global-progress", "value"), 
     Output("sv-global-progress", "label"), Output("sv-gap", "children"), 
     Output("sv-gap", "className"), Output("sv-gap-msg", "children")],
    [Input("sv-account-selector", "value"), Input("sv-update-signal", "data")]
)
def update_sv_dashboard(acc_id, sig):
    # Lógica original tuya preservada
    real_bal = 0.0
    if acc_id:
        conn = dm.get_connection()
        try:
            if acc_id == 'RESERVE': real_bal = dm.get_credit_abono_reserve()
            else:
                res = conn.execute("SELECT current_balance FROM accounts WHERE id=?", (acc_id,)).fetchone()
                if res: real_bal = res[0]
        finally: conn.close()

    df = dm.get_savings_goals_df()
    if df.empty:
        virtual_total, total_target_defined = 0.0, 0.0
    else:
        virtual_total = df['current_saved'].sum()
        total_target_defined = df[df['contribution_mode'] == 'Date']['target_amount'].sum()
    
    if total_target_defined > 0:
        saved_in_goals = df[df['contribution_mode'] == 'Date']['current_saved'].sum()
        global_pct = (saved_in_goals / total_target_defined * 100)
    else:
        global_pct = 0
        
    gap = real_bal - virtual_total
    gap_cls = "fw-bold text-success" if gap >= 0 else "fw-bold text-danger"
    gap_msg = "¡Fondos suficientes!" if gap >= 0 else f"Faltan ${abs(gap):,.2f} reales"

    return (f"${real_bal:,.2f}", f"${virtual_total:,.2f}", f"${total_target_defined:,.2f}",
            global_pct, f"{global_pct:.1f}%", f"${gap:,.2f}", gap_cls, gap_msg)


# 3. RENDERIZAR LISTA (AGREGADO BOTÓN "RETIRAR")
@callback(Output("sv-list-container", "children"), Input("sv-update-signal", "data"))
def render_sv_list(sig):
    df = dm.get_savings_goals_df()
    if df.empty: return html.Div("No hay ahorros configurados.", className="text-center text-muted py-5")

    cards = []
    today = date.today()

    for _, row in df.iterrows():
        saved = row['current_saved']
        mode = row.get('contribution_mode', 'Date')
        
        # --- TU LÓGICA VISUAL ORIGINAL (INTACTA) ---
        if mode == 'Date':
            target = row['target_amount']
            pct = (saved / target * 100) if target > 0 else 0
            
            monthly_txt = html.Small("Sin fecha definida", className="text-muted")
            if row['target_date']:
                try:
                    t_date = datetime.strptime(row['target_date'], '%Y-%m-%d').date()
                    remaining = max(0, target - saved)
                    if t_date <= today:
                        if remaining <= 0: monthly_txt = html.Small("¡Completado! 🎉", className="text-success fw-bold")
                        else: monthly_txt = html.Small("¡Vencida!", className="text-danger fw-bold")
                    else:
                        months = max((t_date - today).days / 30.44, 1)
                        effort = remaining / months
                        monthly_txt = html.Div([
                            html.Span(f"${effort:,.2f}", className="text-info fw-bold"),
                            html.Span("/mes", className="text-muted small ms-1")
                        ])
                except: pass

            card_content = [
                dbc.Row([
                    dbc.Col([html.Small("Meta:", className="text-muted"), html.Div(f"${target:,.2f}", className="fw-bold")]),
                    dbc.Col([html.Small("Ahorrado:", className="text-muted"), html.Div(f"${saved:,.2f}", className="fw-bold text-success text-end")])
                ]),
                dbc.Progress(value=pct, label=f"{pct:.0f}%", color="info" if pct<100 else "success", className="mt-2 mb-2", style={"height": "12px"}),
                html.Div(monthly_txt, className="text-center mt-1 bg-light rounded p-1 border")
            ]
            badge = dbc.Badge("Meta", color="primary", className="ms-2")

        else:
            if mode == 'Fixed':
                strategy_txt = f"Aporte: ${row.get('fixed_contribution', 0):,.2f}/mes"
            else:
                strategy_txt = f"Aporte: {row.get('percentage_contribution', 0)}% del Ingreso"

            card_content = [
                html.Div([
                    html.Small("Acumulado Total:", className="text-muted d-block"),
                    html.H3(f"${saved:,.2f}", className="text-success fw-bold"),
                ], className="text-center py-2"),
                html.Div(html.Small(strategy_txt, className="text-muted"), className="text-center border-top pt-2")
            ]
            badge = dbc.Badge("Hábito", color="success", className="ms-2")

        # --- HEADER CON BOTONES VISIBLES (CAMBIO AQUÍ) ---
        card = dbc.Col(dbc.Card([
            dbc.CardBody([
                dbc.Row([
                    # Título y Badge
                    dbc.Col([
                        html.H5([row['name'], badge], className="fw-bold mb-0 text-truncate"),
                    ], width=True, className="d-flex align-items-center"),
                    
                    # Botones de Acción (Directos, sin menú)
                    dbc.Col([
                        # Botón Retirar (Amarillo/Warning para diferenciar de "Pagar" gasto fijo)
                        dbc.Button(html.I(className="bi bi-wallet2"), 
                                   id={'type': 'sv-btn-wd', 'index': row['id']}, 
                                   color="warning", size="sm", className="me-1", 
                                   title="Retirar / Usar Fondos"),
                        
                        # Botón Editar
                        dbc.Button(html.I(className="bi bi-pencil"), 
                                   id={'type': 'sv-edit', 'index': row['id']}, 
                                   color="light", size="sm", className="me-1", 
                                   title="Editar"),
                        
                        # Botón Borrar
                        dbc.Button(html.I(className="bi bi-trash"), 
                                   id={'type': 'sv-del', 'index': row['id']}, 
                                   color="danger", outline=True, size="sm", 
                                   title="Eliminar"),
                    ], width="auto")
                ], className="mb-3"),
                
                html.Div(card_content)
            ])
        ], className="h-100 shadow-sm border-light"), lg=4, md=6, sm=12, className="mb-4")
        cards.append(card)

    return dbc.Row(cards)


# 4. ABRIR MODAL EDICIÓN (Tu lógica original)
@callback(
    [Output("sv-modal", "is_open"), Output("sv-name", "value"), Output("sv-target", "value"),
     Output("sv-saved", "value"), Output("sv-date", "date"), 
     Output("sv-mode", "value"), Output("sv-fixed-val", "value"), Output("sv-pct-val", "value"),
     Output("sv-edit-id", "data")],
    [Input("sv-btn-add", "n_clicks"), Input("sv-btn-cancel", "n_clicks"), Input({'type': 'sv-edit', 'index': ALL}, 'n_clicks')],
    [State("sv-modal", "is_open")], prevent_initial_call=True
)
def toggle_sv_modal(n_add, n_cancel, n_edit, is_open):
    trig = ctx.triggered_id
    if not trig: return no_update

    if trig == "sv-btn-cancel": return False, "", "", 0, None, "Date", "", "", None
    if trig == "sv-btn-add": 
        if not n_add: return no_update
        return True, "", "", 0, None, "Date", "", "", None
    
    if isinstance(trig, dict) and trig['type'] == 'sv-edit':
        if not ctx.triggered[0]['value']: return no_update
        row = dm.get_savings_goals_df()[dm.get_savings_goals_df()['id'] == trig['index']].iloc[0]
        return True, row['name'], row['target_amount'], row['current_saved'], row['target_date'], \
               row.get('contribution_mode', 'Date'), row.get('fixed_contribution', 0), row.get('percentage_contribution', 0), \
               row['id']
    return no_update


# 5. GUARDAR (Tu lógica original)
@callback(
    [Output("sv-update-signal", "data", allow_duplicate=True), Output("sv-modal", "is_open", allow_duplicate=True),
     Output("sv-feedback-toast", "is_open"), Output("sv-feedback-toast", "children"), Output("sv-feedback-toast", "icon")],
    Input("sv-btn-save", "n_clicks"),
    [State("sv-name", "value"), State("sv-target", "value"), State("sv-saved", "value"),
     State("sv-date", "date"), State("sv-mode", "value"), 
     State("sv-fixed-val", "value"), State("sv-pct-val", "value"),
     State("sv-edit-id", "data"), State("sv-update-signal", "data")],
    prevent_initial_call=True
)
def save_sv(n, name, target, saved, date_val, mode, fixed_v, pct_v, edit_id, sig):
    if not n: return no_update
    if not name: return no_update, True, True, "Nombre requerido", "warning"
    
    t_val = float(target) if target else 0.0
    s_val = float(saved) if saved else 0.0
    f_val = float(fixed_v) if fixed_v else 0.0
    p_val = float(pct_v) if pct_v else 0.0
    
    if mode == 'Date' and t_val <= 0:
        return no_update, True, True, "Una meta con fecha requiere monto objetivo.", "warning"

    if edit_id:
        success, msg = dm.update_saving_goal(edit_id, name, t_val, s_val, date_val, mode, f_val, p_val)
    else:
        success, msg = dm.add_saving_goal(name, t_val, s_val, date_val, mode, f_val, p_val)
    
    if success: return (sig or 0)+1, False, True, "Guardado", "success"
    return no_update, True, True, f"Error: {msg}", "danger"


# 6. BORRAR (Tu lógica original)
@callback(
    [Output("sv-delete-modal", "is_open"), Output("sv-delete-id", "data")],
    [Input({'type': 'sv-del', 'index': ALL}, 'n_clicks'), Input("sv-btn-del-cancel", "n_clicks")],
    prevent_initial_call=True
)
def prompt_sv_del(n_del, n_cancel):
    trig = ctx.triggered_id
    if trig == "sv-btn-del-cancel": return False, None
    if isinstance(trig, dict) and ctx.triggered[0]['value']: return True, trig['index']
    return no_update

@callback(
    [Output("sv-update-signal", "data", allow_duplicate=True), Output("sv-delete-modal", "is_open", allow_duplicate=True)],
    Input("sv-btn-del-confirm", "n_clicks"),
    [State("sv-delete-id", "data"), State("sv-update-signal", "data")], prevent_initial_call=True
)
def exec_sv_del(n, del_id, sig):
    if n and del_id:
        dm.delete_saving_goal(del_id)
        return (sig or 0)+1, False
    return no_update


# ==============================================================================
# 7. CALLBACKS NUEVOS: LÓGICA DE RETIRO (WITHDRAW)
# ==============================================================================

# A. ABRIR MODAL RETIRO
@callback(
    [Output("withdraw-modal", "is_open"),
     Output("wd-target-id", "data"),
     Output("wd-title-label", "children"),
     Output("wd-source-acc", "options"),
     Output("wd-source-acc", "value"),
     Output("wd-dest-acc", "options"),
     Output("wd-amount", "value")],
    [Input({'type': 'sv-btn-wd', 'index': ALL}, 'n_clicks'),
     Input("wd-btn-cancel", "n_clicks")],
    [State("sv-account-selector", "value")], # Cuenta por defecto
    prevent_initial_call=True
)
def toggle_withdraw(n_wd, n_cancel, default_acc):
    trig = ctx.triggered_id
    if not trig: return no_update
    if trig == "wd-btn-cancel": return False, no_update, no_update, no_update, no_update, no_update, no_update

    if isinstance(trig, dict) and ctx.triggered[0]['value']:
        s_id = trig['index']
        # Buscar nombre
        df = dm.get_savings_goals_df()
        row = df[df['id'] == s_id].iloc[0]
        title = f"Sacar dinero de: {row['name']}"
        
        accs = dm.get_account_options()
        return True, s_id, title, accs, default_acc, accs, "" 
        
    return no_update

# B. CAMBIAR TIPO (GASTO vs TRANSFERENCIA)
@callback(
    [Output("wd-collapse-expense", "is_open"),
     Output("wd-collapse-transfer", "is_open")],
    Input("wd-type-selector", "value")
)
def toggle_wd_type(val):
    if val == "transfer": return False, True
    return True, False

# C. CARGAR SUBCATEGORIAS
@callback(
    Output("wd-subcategory", "options"),
    Input("wd-category", "value"),
    prevent_initial_call=True
)
def update_wd_subcats(cat):
    if not cat: return []
    return dm.get_subcategories_by_parent(cat)

# D. CONFIRMAR RETIRO
@callback(
    [Output("withdraw-modal", "is_open", allow_duplicate=True),
     Output("sv-update-signal", "data", allow_duplicate=True),
     Output("sv-feedback-toast", "is_open", allow_duplicate=True),
     Output("sv-feedback-toast", "children", allow_duplicate=True),
     Output("sv-feedback-toast", "icon", allow_duplicate=True)],
    Input("wd-btn-confirm", "n_clicks"),
    [State("wd-target-id", "data"),
     State("wd-amount", "value"),
     State("wd-source-acc", "value"),
     State("wd-type-selector", "value"),
     State("wd-dest-acc", "value"),
     State("wd-category", "value"),
     State("wd-subcategory", "value"),
     State("wd-note", "value"),
     State("sv-update-signal", "data")],
    prevent_initial_call=True
)
def execute_withdraw(n, s_id, amt, src_acc, type_sel, dest_acc, cat, subcat, note, sig):
    if not n: return no_update
    if not amt or amt <= 0: return no_update, no_update, True, "Monto inválido", "warning"
    if not src_acc: return no_update, no_update, True, "Selecciona cuenta origen", "warning"

    is_transfer = (type_sel == "transfer")
    
    if is_transfer and not dest_acc:
        return no_update, no_update, True, "Selecciona cuenta destino", "warning"
    if not is_transfer and not cat:
        return no_update, no_update, True, "Selecciona una categoría", "warning"

    success, msg = dm.process_savings_withdrawal(
        goal_id=s_id, amount=float(amt), account_id=src_acc, 
        is_transfer=is_transfer, dest_acc_id=dest_acc, 
        category=cat, subcategory=subcat, note=note
    )

    if success:
        return False, (sig or 0)+1, True, msg, "success"
    else:
=======
# pages/distribution/savings.py
import dash
from dash import dcc, html, callback, Input, Output, State, no_update, ctx, ALL
import dash_bootstrap_components as dbc
import backend.data_manager as dm
from utils import ui_helpers 
from datetime import date, datetime

# ==============================================================================
# 1. MODALES
# ==============================================================================

# --- MODAL: AGREGAR / EDITAR META (TU CÓDIGO ORIGINAL) ---
sv_modal = dbc.Modal([
    dbc.ModalHeader(dbc.ModalTitle("Configurar Ahorro")),
    dbc.ModalBody([
        dbc.Label("Nombre"),
        dbc.Input(id="sv-name", placeholder="Ej. Viaje, Fondo de Emergencia...", className="mb-3"),

        dbc.Label("Tipo de Ahorro", className="fw-bold text-primary"),
        dbc.RadioItems(
            id="sv-mode",
            options=[
                {"label": "Meta con Fecha (Objetivo Fijo)", "value": "Date"},
                {"label": "Hábito / Recurrente ($ Fijo)", "value": "Fixed"},
                {"label": "Hábito / Proporcional (% Ingreso)", "value": "Percentage"},
            ],
            value="Date",
            inline=False,
            className="mb-3"
        ),
        
        # Inputs Dinámicos (Tu lógica original)
        html.Div([
            dbc.Row([
                dbc.Col([dbc.Label("Monto Objetivo ($)"), dbc.Input(id="sv-target", type="number", placeholder="0.00")], width=6),
                dbc.Col([dbc.Label("Fecha Límite"), dcc.DatePickerSingle(id="sv-date", display_format='YYYY-MM-DD', className="d-block", placeholder="Seleccionar...")], width=6),
            ], className="mb-3"),
        ], id="div-sv-goal-inputs"),

        html.Div([
            dbc.Label("Monto a guardar mensualmente ($)"),
            dbc.Input(id="sv-fixed-val", type="number", placeholder="Ej. 50.00"),
            dbc.FormText("Este monto se sugerirá cada mes indefinidamente."),
        ], id="div-sv-fixed", style={"display": "none"}),

        html.Div([
            dbc.Label("Porcentaje del Ingreso a guardar (%)"),
            dbc.Input(id="sv-pct-val", type="number", placeholder="Ej. 10"),
            dbc.FormText("Calculado sobre el ingreso que registres cada vez."),
        ], id="div-sv-pct", style={"display": "none"}),

        html.Hr(),
        dbc.Label("Dinero ya acumulado (Saldo Actual)"),
        dbc.Input(id="sv-saved", type="number", placeholder="0.00", value=0),

        dcc.Store(id="sv-edit-id", data=None),
        html.Div(id="sv-modal-feedback", className="text-center mt-2")
    ]),
    dbc.ModalFooter([
        dbc.Button("Cancelar", id="sv-btn-cancel", outline=True),
        dbc.Button("Guardar", id="sv-btn-save", color="primary", className="ms-2"),
    ])
], id="sv-modal", is_open=False, centered=True, size="md")


# --- MODAL: RETIRAR / USAR DINERO (NUEVO) ---
withdraw_modal = dbc.Modal([
    dbc.ModalHeader(dbc.ModalTitle("Usar / Retirar Ahorros")),
    dbc.ModalBody([
        html.H5(id="wd-title-label", className="text-primary text-center mb-3"),
        
        # 1. Monto y Cuenta Origen
        dbc.Row([
            dbc.Col([dbc.Label("Monto a sacar ($)"), dbc.Input(id="wd-amount", type="number", min=0, className="mb-2")], width=6),
            dbc.Col([dbc.Label("Desde Cuenta"), dcc.Dropdown(id="wd-source-acc", placeholder="Donde está el dinero", className="text-dark")], width=6),
        ], className="mb-3"),

        # 2. Selector de Tipo: Gasto vs Transferencia
        dbc.Label("¿Qué harás con el dinero?"),
        dbc.RadioItems(
            id="wd-type-selector",
            options=[
                {"label": "Gastar (Compra)", "value": "expense"},
                {"label": "Mover a otra cuenta", "value": "transfer"},
            ],
            value="expense",
            inline=True,
            className="mb-3"
        ),

        # 3. Campos dinámicos para GASTO
        dbc.Collapse([
            dbc.Card([dbc.CardBody([
                dbc.Row([
                    dbc.Col([dbc.Label("Categoría"), dcc.Dropdown(id="wd-category", placeholder="Ej. Guilt Free...", className="text-dark")], width=6),
                    dbc.Col([dbc.Label("Subcategoría"), dcc.Dropdown(id="wd-subcategory", placeholder="Opcional", className="text-dark")], width=6),
                ], className="mb-2"),
                dbc.Label("Nota / Descripción"),
                dbc.Input(id="wd-note", placeholder="Ej. Boletos de avión", type="text"),
            ])], className="bg-light border-0")
        ], id="wd-collapse-expense", is_open=True),

        # 4. Campos dinámicos para TRANSFERENCIA
        dbc.Collapse([
            dbc.Card([dbc.CardBody([
                dbc.Label("Cuenta Destino"),
                dcc.Dropdown(id="wd-dest-acc", placeholder="A dónde va el dinero...", className="text-dark"),
            ])], className="bg-light border-0")
        ], id="wd-collapse-transfer", is_open=False),
        
        dcc.Store(id="wd-target-id", data=None),
    ]),
    dbc.ModalFooter([
        dbc.Button("Cancelar", id="wd-btn-cancel", outline=True),
        dbc.Button("Confirmar Retiro", id="wd-btn-confirm", color="danger"),
    ])
], id="withdraw-modal", is_open=False, centered=True)


# --- MODAL BORRAR (TU CÓDIGO ORIGINAL) ---
sv_delete_modal = dbc.Modal([
    dbc.ModalHeader("Eliminar Ahorro"),
    dbc.ModalBody("¿Seguro? Se borrará el registro de la meta."),
    dbc.ModalFooter([
        dbc.Button("Cancelar", id="sv-btn-del-cancel", outline=True),
        dbc.Button("Sí, Eliminar", id="sv-btn-del-confirm", color="danger", className="ms-2"),
    ])
], id="sv-delete-modal", is_open=False, centered=True, size="sm")


# ==============================================================================
# 2. LAYOUT
# ==============================================================================
layout = html.Div([
    ui_helpers.get_feedback_toast("sv-feedback-toast"), 
    dcc.Store(id="sv-update-signal", data=0),
    dcc.Store(id="sv-delete-id", data=None),
    
    # Modales
    sv_modal,
    sv_delete_modal,
    withdraw_modal, # <--- Agregado el nuevo modal

    html.Br(),
    
    # --- DASHBOARD GLOBAL (TU CÓDIGO ORIGINAL) ---
    dbc.Card([
        dbc.CardBody([
            html.H5("Monitor de Ahorros", className="card-title text-success mb-4"),
            dbc.Row([
                # Col 1: Dinero Real
                dbc.Col([
                    dbc.Label("Cuenta de Ahorros (Real):"),
                    dcc.Dropdown(id="sv-account-selector", placeholder="Selecciona...", className="text-dark mb-2"),
                    html.Small("Saldo Real:", className="text-muted d-block"),
                    html.H3(id="sv-real-balance", className="text-white")
                ], md=4, className="border-end border-secondary"),

                # Col 2: Metas (Virtual)
                dbc.Col([
                    html.Small("Total Acumulado (Todas las categorías):", className="text-muted d-block"),
                    html.H3(id="sv-virtual-total", className="text-warning mb-0"),
                    
                    html.Div([
                        html.Span("Meta Global Definida: ", className="text-muted small me-1"),
                        html.Span(id="sv-total-target", className="fw-bold text-info"),
                    ], className="mb-3"),

                    dbc.Progress(id="sv-global-progress", value=0, label="0%", color="success", className="mt-1", style={"height": "10px"})
                ], md=4, className="border-end border-secondary text-center"),

                # Col 3: Diferencia
                dbc.Col([
                    html.Small("Diferencia (Real vs Virtual):", className="text-muted d-block"),
                    html.H3(id="sv-gap", className="fw-bold"),
                    html.Div(id="sv-gap-msg", className="small")
                ], md=4, className="text-center"),
            ])
        ])
    ], className="mb-4 metric-card"),

    # LISTA DE CARDS
    dbc.Row([
        dbc.Col(html.H4("Mis Ahorros & Metas"), width=True),
        dbc.Col(dbc.Button("+ Nuevo Ahorro", id="sv-btn-add", color="success"), width="auto"),
    ], className="mb-3 align-items-center"),
    
    html.Div(id="sv-list-container")
])


# ==============================================================================
# 3. CALLBACKS ORIGINALES (Manteniendo tu lógica)
# ==============================================================================

# 1. MOSTRAR/OCULTAR INPUTS SEGÚN TIPO
@callback(
    [Output("div-sv-goal-inputs", "style"), Output("div-sv-fixed", "style"), Output("div-sv-pct", "style")],
    Input("sv-mode", "value")
)
def toggle_inputs(mode):
    hide = {"display": "none"}
    show = {"display": "block", "marginBottom": "1rem"}
    if mode == 'Date': return show, hide, hide
    if mode == 'Fixed': return hide, show, hide
    if mode == 'Percentage': return hide, hide, show
    return show, hide, hide


# 2. CARGAR CUENTAS Y DASHBOARD (Incluye carga de categorías para retiro)
@callback(
    [Output("sv-account-selector", "options"), 
     Output("sv-account-selector", "value"),
     Output("wd-category", "options")], # <--- NUEVO: Cargar opciones para el modal de retiro
    Input("url", "pathname")
)
def load_sv_options(path):
    if not path or "distribucion" not in path: return no_update, no_update, no_update
    acc_opts = dm.get_account_options()
    sv_acc = dm.get_user_sv_fund_account()
    cat_opts = dm.get_all_categories_options() # <--- NUEVO
    return acc_opts, sv_acc, cat_opts

@callback(
    Output("sv-update-signal", "data", allow_duplicate=True), 
    Input("sv-account-selector", "value"), 
    prevent_initial_call=True
)
def save_sv_pref(acc_id):
    if acc_id: dm.update_user_sv_fund_account(acc_id)
    return no_update

@callback(
    [Output("sv-real-balance", "children"), Output("sv-virtual-total", "children"),
     Output("sv-total-target", "children"), Output("sv-global-progress", "value"), 
     Output("sv-global-progress", "label"), Output("sv-gap", "children"), 
     Output("sv-gap", "className"), Output("sv-gap-msg", "children")],
    [Input("sv-account-selector", "value"), Input("sv-update-signal", "data")]
)
def update_sv_dashboard(acc_id, sig):
    # Lógica original tuya preservada
    real_bal = 0.0
    if acc_id:
        conn = dm.get_connection()
        try:
            if acc_id == 'RESERVE': real_bal = dm.get_credit_abono_reserve()
            else:
                res = conn.execute("SELECT current_balance FROM accounts WHERE id=?", (acc_id,)).fetchone()
                if res: real_bal = res[0]
        finally: conn.close()

    df = dm.get_savings_goals_df()
    if df.empty:
        virtual_total, total_target_defined = 0.0, 0.0
    else:
        virtual_total = df['current_saved'].sum()
        total_target_defined = df[df['contribution_mode'] == 'Date']['target_amount'].sum()
    
    if total_target_defined > 0:
        saved_in_goals = df[df['contribution_mode'] == 'Date']['current_saved'].sum()
        global_pct = (saved_in_goals / total_target_defined * 100)
    else:
        global_pct = 0
        
    gap = real_bal - virtual_total
    gap_cls = "fw-bold text-success" if gap >= 0 else "fw-bold text-danger"
    gap_msg = "¡Fondos suficientes!" if gap >= 0 else f"Faltan ${abs(gap):,.2f} reales"

    return (f"${real_bal:,.2f}", f"${virtual_total:,.2f}", f"${total_target_defined:,.2f}",
            global_pct, f"{global_pct:.1f}%", f"${gap:,.2f}", gap_cls, gap_msg)


# 3. RENDERIZAR LISTA (AGREGADO BOTÓN "RETIRAR")
@callback(Output("sv-list-container", "children"), Input("sv-update-signal", "data"))
def render_sv_list(sig):
    df = dm.get_savings_goals_df()
    if df.empty: return html.Div("No hay ahorros configurados.", className="text-center text-muted py-5")

    cards = []
    today = date.today()

    for _, row in df.iterrows():
        saved = row['current_saved']
        mode = row.get('contribution_mode', 'Date')
        
        # --- TU LÓGICA VISUAL ORIGINAL (INTACTA) ---
        if mode == 'Date':
            target = row['target_amount']
            pct = (saved / target * 100) if target > 0 else 0
            
            monthly_txt = html.Small("Sin fecha definida", className="text-muted")
            if row['target_date']:
                try:
                    t_date = datetime.strptime(row['target_date'], '%Y-%m-%d').date()
                    remaining = max(0, target - saved)
                    if t_date <= today:
                        if remaining <= 0: monthly_txt = html.Small("¡Completado! 🎉", className="text-success fw-bold")
                        else: monthly_txt = html.Small("¡Vencida!", className="text-danger fw-bold")
                    else:
                        months = max((t_date - today).days / 30.44, 1)
                        effort = remaining / months
                        monthly_txt = html.Div([
                            html.Span(f"${effort:,.2f}", className="text-info fw-bold"),
                            html.Span("/mes", className="text-muted small ms-1")
                        ])
                except: pass

            card_content = [
                dbc.Row([
                    dbc.Col([html.Small("Meta:", className="text-muted"), html.Div(f"${target:,.2f}", className="fw-bold")]),
                    dbc.Col([html.Small("Ahorrado:", className="text-muted"), html.Div(f"${saved:,.2f}", className="fw-bold text-success text-end")])
                ]),
                dbc.Progress(value=pct, label=f"{pct:.0f}%", color="info" if pct<100 else "success", className="mt-2 mb-2", style={"height": "12px"}),
                html.Div(monthly_txt, className="text-center mt-1 bg-light rounded p-1 border")
            ]
            badge = dbc.Badge("Meta", color="primary", className="ms-2")

        else:
            if mode == 'Fixed':
                strategy_txt = f"Aporte: ${row.get('fixed_contribution', 0):,.2f}/mes"
            else:
                strategy_txt = f"Aporte: {row.get('percentage_contribution', 0)}% del Ingreso"

            card_content = [
                html.Div([
                    html.Small("Acumulado Total:", className="text-muted d-block"),
                    html.H3(f"${saved:,.2f}", className="text-success fw-bold"),
                ], className="text-center py-2"),
                html.Div(html.Small(strategy_txt, className="text-muted"), className="text-center border-top pt-2")
            ]
            badge = dbc.Badge("Hábito", color="success", className="ms-2")

        # --- HEADER CON BOTONES VISIBLES (CAMBIO AQUÍ) ---
        card = dbc.Col(dbc.Card([
            dbc.CardBody([
                dbc.Row([
                    # Título y Badge
                    dbc.Col([
                        html.H5([row['name'], badge], className="fw-bold mb-0 text-truncate"),
                    ], width=True, className="d-flex align-items-center"),
                    
                    # Botones de Acción (Directos, sin menú)
                    dbc.Col([
                        # Botón Retirar (Amarillo/Warning para diferenciar de "Pagar" gasto fijo)
                        dbc.Button(html.I(className="bi bi-wallet2"), 
                                   id={'type': 'sv-btn-wd', 'index': row['id']}, 
                                   color="warning", size="sm", className="me-1", 
                                   title="Retirar / Usar Fondos"),
                        
                        # Botón Editar
                        dbc.Button(html.I(className="bi bi-pencil"), 
                                   id={'type': 'sv-edit', 'index': row['id']}, 
                                   color="light", size="sm", className="me-1", 
                                   title="Editar"),
                        
                        # Botón Borrar
                        dbc.Button(html.I(className="bi bi-trash"), 
                                   id={'type': 'sv-del', 'index': row['id']}, 
                                   color="danger", outline=True, size="sm", 
                                   title="Eliminar"),
                    ], width="auto")
                ], className="mb-3"),
                
                html.Div(card_content)
            ])
        ], className="h-100 shadow-sm border-light"), lg=4, md=6, sm=12, className="mb-4")
        cards.append(card)

    return dbc.Row(cards)


# 4. ABRIR MODAL EDICIÓN (Tu lógica original)
@callback(
    [Output("sv-modal", "is_open"), Output("sv-name", "value"), Output("sv-target", "value"),
     Output("sv-saved", "value"), Output("sv-date", "date"), 
     Output("sv-mode", "value"), Output("sv-fixed-val", "value"), Output("sv-pct-val", "value"),
     Output("sv-edit-id", "data")],
    [Input("sv-btn-add", "n_clicks"), Input("sv-btn-cancel", "n_clicks"), Input({'type': 'sv-edit', 'index': ALL}, 'n_clicks')],
    [State("sv-modal", "is_open")], prevent_initial_call=True
)
def toggle_sv_modal(n_add, n_cancel, n_edit, is_open):
    trig = ctx.triggered_id
    if not trig: return no_update

    if trig == "sv-btn-cancel": return False, "", "", 0, None, "Date", "", "", None
    if trig == "sv-btn-add": 
        if not n_add: return no_update
        return True, "", "", 0, None, "Date", "", "", None
    
    if isinstance(trig, dict) and trig['type'] == 'sv-edit':
        if not ctx.triggered[0]['value']: return no_update
        row = dm.get_savings_goals_df()[dm.get_savings_goals_df()['id'] == trig['index']].iloc[0]
        return True, row['name'], row['target_amount'], row['current_saved'], row['target_date'], \
               row.get('contribution_mode', 'Date'), row.get('fixed_contribution', 0), row.get('percentage_contribution', 0), \
               row['id']
    return no_update


# 5. GUARDAR (Tu lógica original)
@callback(
    [Output("sv-update-signal", "data", allow_duplicate=True), Output("sv-modal", "is_open", allow_duplicate=True),
     Output("sv-feedback-toast", "is_open"), Output("sv-feedback-toast", "children"), Output("sv-feedback-toast", "icon")],
    Input("sv-btn-save", "n_clicks"),
    [State("sv-name", "value"), State("sv-target", "value"), State("sv-saved", "value"),
     State("sv-date", "date"), State("sv-mode", "value"), 
     State("sv-fixed-val", "value"), State("sv-pct-val", "value"),
     State("sv-edit-id", "data"), State("sv-update-signal", "data")],
    prevent_initial_call=True
)
def save_sv(n, name, target, saved, date_val, mode, fixed_v, pct_v, edit_id, sig):
    if not n: return no_update
    if not name: return no_update, True, True, "Nombre requerido", "warning"
    
    t_val = float(target) if target else 0.0
    s_val = float(saved) if saved else 0.0
    f_val = float(fixed_v) if fixed_v else 0.0
    p_val = float(pct_v) if pct_v else 0.0
    
    if mode == 'Date' and t_val <= 0:
        return no_update, True, True, "Una meta con fecha requiere monto objetivo.", "warning"

    if edit_id:
        success, msg = dm.update_saving_goal(edit_id, name, t_val, s_val, date_val, mode, f_val, p_val)
    else:
        success, msg = dm.add_saving_goal(name, t_val, s_val, date_val, mode, f_val, p_val)
    
    if success: return (sig or 0)+1, False, True, "Guardado", "success"
    return no_update, True, True, f"Error: {msg}", "danger"


# 6. BORRAR (Tu lógica original)
@callback(
    [Output("sv-delete-modal", "is_open"), Output("sv-delete-id", "data")],
    [Input({'type': 'sv-del', 'index': ALL}, 'n_clicks'), Input("sv-btn-del-cancel", "n_clicks")],
    prevent_initial_call=True
)
def prompt_sv_del(n_del, n_cancel):
    trig = ctx.triggered_id
    if trig == "sv-btn-del-cancel": return False, None
    if isinstance(trig, dict) and ctx.triggered[0]['value']: return True, trig['index']
    return no_update

@callback(
    [Output("sv-update-signal", "data", allow_duplicate=True), Output("sv-delete-modal", "is_open", allow_duplicate=True)],
    Input("sv-btn-del-confirm", "n_clicks"),
    [State("sv-delete-id", "data"), State("sv-update-signal", "data")], prevent_initial_call=True
)
def exec_sv_del(n, del_id, sig):
    if n and del_id:
        dm.delete_saving_goal(del_id)
        return (sig or 0)+1, False
    return no_update


# ==============================================================================
# 7. CALLBACKS NUEVOS: LÓGICA DE RETIRO (WITHDRAW)
# ==============================================================================

# A. ABRIR MODAL RETIRO
@callback(
    [Output("withdraw-modal", "is_open"),
     Output("wd-target-id", "data"),
     Output("wd-title-label", "children"),
     Output("wd-source-acc", "options"),
     Output("wd-source-acc", "value"),
     Output("wd-dest-acc", "options"),
     Output("wd-amount", "value")],
    [Input({'type': 'sv-btn-wd', 'index': ALL}, 'n_clicks'),
     Input("wd-btn-cancel", "n_clicks")],
    [State("sv-account-selector", "value")], # Cuenta por defecto
    prevent_initial_call=True
)
def toggle_withdraw(n_wd, n_cancel, default_acc):
    trig = ctx.triggered_id
    if not trig: return no_update
    if trig == "wd-btn-cancel": return False, no_update, no_update, no_update, no_update, no_update, no_update

    if isinstance(trig, dict) and ctx.triggered[0]['value']:
        s_id = trig['index']
        # Buscar nombre
        df = dm.get_savings_goals_df()
        row = df[df['id'] == s_id].iloc[0]
        title = f"Sacar dinero de: {row['name']}"
        
        accs = dm.get_account_options()
        return True, s_id, title, accs, default_acc, accs, "" 
        
    return no_update

# B. CAMBIAR TIPO (GASTO vs TRANSFERENCIA)
@callback(
    [Output("wd-collapse-expense", "is_open"),
     Output("wd-collapse-transfer", "is_open")],
    Input("wd-type-selector", "value")
)
def toggle_wd_type(val):
    if val == "transfer": return False, True
    return True, False

# C. CARGAR SUBCATEGORIAS
@callback(
    Output("wd-subcategory", "options"),
    Input("wd-category", "value"),
    prevent_initial_call=True
)
def update_wd_subcats(cat):
    if not cat: return []
    return dm.get_subcategories_by_parent(cat)

# D. CONFIRMAR RETIRO
@callback(
    [Output("withdraw-modal", "is_open", allow_duplicate=True),
     Output("sv-update-signal", "data", allow_duplicate=True),
     Output("sv-feedback-toast", "is_open", allow_duplicate=True),
     Output("sv-feedback-toast", "children", allow_duplicate=True),
     Output("sv-feedback-toast", "icon", allow_duplicate=True)],
    Input("wd-btn-confirm", "n_clicks"),
    [State("wd-target-id", "data"),
     State("wd-amount", "value"),
     State("wd-source-acc", "value"),
     State("wd-type-selector", "value"),
     State("wd-dest-acc", "value"),
     State("wd-category", "value"),
     State("wd-subcategory", "value"),
     State("wd-note", "value"),
     State("sv-update-signal", "data")],
    prevent_initial_call=True
)
def execute_withdraw(n, s_id, amt, src_acc, type_sel, dest_acc, cat, subcat, note, sig):
    if not n: return no_update
    if not amt or amt <= 0: return no_update, no_update, True, "Monto inválido", "warning"
    if not src_acc: return no_update, no_update, True, "Selecciona cuenta origen", "warning"

    is_transfer = (type_sel == "transfer")
    
    if is_transfer and not dest_acc:
        return no_update, no_update, True, "Selecciona cuenta destino", "warning"
    if not is_transfer and not cat:
        return no_update, no_update, True, "Selecciona una categoría", "warning"

    success, msg = dm.process_savings_withdrawal(
        goal_id=s_id, amount=float(amt), account_id=src_acc, 
        is_transfer=is_transfer, dest_acc_id=dest_acc, 
        category=cat, subcategory=subcat, note=note
    )

    if success:
        return False, (sig or 0)+1, True, msg, "success"
    else:
>>>>>>> b74f1b0a886c27181c8264a954a4baf9f2b71029
        return True, no_update, True, msg, "danger"