# pages/distribution/revenue.py
import dash
from dash import dcc, html, callback, Input, Output, State, no_update, ALL, ctx, MATCH
import dash_bootstrap_components as dbc
import backend.data_manager as dm
from utils import ui_helpers
import pandas as pd
from datetime import date, datetime

# --- ESTILOS ---
CARD_STYLE = {"cursor": "pointer", "transition": "all 0.2s ease"}
SELECTED_STYLE = {"border": "2px solid #0d6efd", "borderRadius": "5px", "backgroundColor": "#f0f8ff", "transform": "scale(1.02)"}

# --- MODAL PARA AGREGAR / EDITAR REGLA ---
rule_modal = dbc.Modal([
    dbc.ModalHeader(dbc.ModalTitle("Configurar Regla")),
    dbc.ModalBody([
        dbc.Label("Nombre (Ej. S&P500, Crypto, Cena)"),
        dbc.Input(id="rule-name", className="mb-3"),
        dbc.Row([
            dbc.Col([
                dbc.Label("Tipo"),
                dbc.Select(id="rule-alloc-type", options=[
                    {"label": "Porcentaje (%)", "value": "Percentage"},
                    {"label": "Monto Fijo ($)", "value": "Fixed"}
                ], value="Percentage")
            ], width=6),
            dbc.Col([
                dbc.Label("Valor"),
                dbc.Input(id="rule-value", type="number", placeholder="10"),
            ], width=6),
        ], className="mb-3"),
        
        dcc.Store(id="rule-category-type", data="Investment"), 
        dcc.Store(id="rule-edit-id", data=None), 
    ]),
    dbc.ModalFooter([
        dbc.Button("Cancelar", id="btn-cancel-rule", outline=True, className="me-2"),
        dbc.Button("Guardar", id="btn-save-rule", color="primary")
    ])
], id="rule-modal", is_open=False, centered=True)


# --- LAYOUT ---
layout = html.Div([
    dcc.Store(id="rev-update-signal", data=0),
    dcc.Store(id="selected-group", data="FC"),
    dcc.Store(id="disabled-items", data=[]),
    
    # Stores para cuentas
    dcc.Store(id="store-acc-fc", data=None),
    dcc.Store(id="store-acc-sv", data=None),
    dcc.Store(id="store-acc-inv", data=None),
    dcc.Store(id="store-acc-gf", data=None),

    ui_helpers.get_feedback_toast("rev-feedback"),
    rule_modal,

    html.Br(),
    # 1. HEADER GLOBAL
    dbc.Card([
        dbc.CardBody([
            dbc.Row([
                dbc.Col([
                    dbc.Label("INGRESO BASE ($)", className="fw-bold text-success mb-0"),
                    dbc.Input(id="input-total-income", type="number", value=0, size="lg", className="fw-bold text-success display-6"),
                    html.Div(id="lbl-extra-income", className="small text-muted mt-1 fst-italic")
                ], md=4),
                dbc.Col([
                    dbc.Label("Cuenta Origen (Entrada)", className="small mb-0"),
                    dcc.Dropdown(id="dd-source-account", placeholder="Selecciona...", className="text-dark", optionHeight=65),
                ], md=4),
                dbc.Col([
                    dbc.Label("Periodicidad", className="small mb-0"),
                    dbc.RadioItems(
                        id="periodicity-selector",
                        options=[{"label": "Mensual", "value": "monthly"}, {"label": "Quincenal", "value": "biweekly"}],
                        value="monthly",
                        inline=True
                    )
                ], md=4, className="text-end align-self-center"),
            ])
        ])
    ], className="mb-4 shadow-sm border-top border-success border-3"),

    # 2. CARDS RESUMEN
    html.Div(id="cards-container", className="mb-4", style={"position": "relative", "zIndex": 10}),

    # 3. ZONA DETALLES
    dbc.Card([
        dbc.CardHeader([
            dbc.Row([
                dbc.Col(html.H5(id="detail-title", className="mb-0 text-primary"), width=True, className="d-flex align-items-center"),
                dbc.Col([html.Div(id="detail-account-container", style={"minWidth": "250px"})], width="auto", className="me-3"),
                dbc.Col(id="detail-actions", width="auto") 
            ], className="align-items-center")
        ], className="bg-light"),
        dbc.CardBody(id="detail-container", className="p-0")
    ], className="shadow-sm mb-5", style={"minHeight": "200px", "position": "relative", "zIndex": 1}),

    # 4. FOOTER
    dbc.Card([
        dbc.CardBody([
            dbc.Row([
                dbc.Col([
                    html.H5("Total a Distribuir:", className="text-muted small mb-0"),
                    html.H3(id="lbl-grand-total", className="mb-0")
                ], width="auto"),
                dbc.Col([
                    dbc.Button("¡Ejecutar Distribución!", id="btn-execute-dist", color="success", size="lg", className="fw-bold w-100")
                ], width=3, className="ms-auto")
            ], className="align-items-center")
        ])
    ], className="sticky-bottom shadow border-top border-success")
])


# ==============================================================================
# CALLBACKS
# ==============================================================================

# 1. INIT
@callback(
    [Output("dd-source-account", "options"),
     Output("store-acc-fc", "data"), 
     Output("store-acc-sv", "data"), 
     Output("store-acc-inv", "data"), 
     Output("store-acc-gf", "data"),
     Output("input-total-income", "value")],
    Input("url", "pathname")
)
def load_initial_data(path):
    opts = dm.get_account_options()
    acc_fc = dm.get_user_fc_fund_account()
    acc_sv = dm.get_user_sv_fund_account()
    acc_inv = dm.get_user_inv_fund_account()
    acc_gf = dm.get_user_gf_fund_account()
    last_income = dm.get_user_last_income()
    return opts, acc_fc, acc_sv, acc_inv, acc_gf, last_income

@callback(
    Output("rev-update-signal", "data", allow_duplicate=True),
    Input("input-total-income", "value"),
    prevent_initial_call=True
)
def save_income_change(val):
    if val is not None: dm.update_user_last_income(float(val))
    return no_update

# 2. UPDATE DASHBOARD
@callback(
    [Output("cards-container", "children"),
     Output("lbl-grand-total", "children"),
     Output("detail-container", "children"),
     Output("detail-title", "children"),
     Output("detail-account-container", "children"),
     Output("detail-actions", "children"),
     Output("lbl-extra-income", "children")],
    [Input("input-total-income", "value"),
     Input("periodicity-selector", "value"),
     Input("selected-group", "data"),
     Input("disabled-items", "data"),
     Input("rev-update-signal", "data"),
     Input("store-acc-fc", "data"), Input("store-acc-sv", "data"), Input("store-acc-inv", "data"), Input("store-acc-gf", "data")]
)
def update_dashboard(income_val, periodicity, selected_grp, disabled_ids, sig, s_fc, s_sv, s_inv, s_gf):
    manual_income = float(income_val) if income_val else 0.0
    factor = 0.5 if periodicity == "biweekly" else 1.0
    disabled_ids = disabled_ids or []
    acc_opts = dm.get_account_options()
    today = date.today()

    # A. CÁLCULO DEL EXTRA
    extra_val = 0.0
    stab_acc_id = dm.get_user_stabilizer_account()
    if stab_acc_id:
        conn = dm.get_connection()
        try:
            res = conn.execute("SELECT current_balance FROM accounts WHERE id=?", (stab_acc_id,)).fetchone()
            stab_bal = res[0] if res else 0.0
        finally: conn.close()
        
        proj = dm.calculate_stabilizer_projection(0, stab_bal, frequency=periodicity)
        extra_val = round(proj['suggested_withdrawal'], 2)

    real_income = round(manual_income + extra_val, 2)

    extra_text = ""
    if extra_val > 0:
        extra_text = f"+ ${extra_val:,.2f} (Extra Caja Chica) = ${real_income:,.2f} Total Real"
    
    # B. CÁLCULOS (REDONDEADOS)
    
    # 1. FC
    df_fc = dm.get_fixed_costs_df()
    total_fc = 0
    if not df_fc.empty:
        for _, r in df_fc.iterrows():
            if str(r['id']) not in disabled_ids:
                val = max((r['amount']/100)*real_income, r.get('min_amount', 0)*factor) if r['is_percentage'] else r['monthly_cost']*factor
                total_fc += round(val, 2)

    # 2. SV
    df_sv = dm.get_savings_goals_df()
    total_sv = 0
    sv_items_processed = []
    if not df_sv.empty:
        for _, r in df_sv.iterrows():
            mode = r.get('contribution_mode', 'Date')
            p_need = 0.0
            if mode == 'Date':
                rem = r['target_amount'] - r['current_saved']
                if rem > 0 and r['target_date']:
                    try:
                        m = max((datetime.strptime(r['target_date'], '%Y-%m-%d').date() - today).days / 30.44, 1)
                        p_need = (rem / m) * factor
                    except: pass
            elif mode == 'Fixed': p_need = r.get('fixed_contribution', 0) * factor
            elif mode == 'Percentage': p_need = (r.get('percentage_contribution', 0) / 100) * real_income
            
            p_need = round(p_need, 2)
            if str(r['id']) not in disabled_ids: total_sv += p_need
            sv_items_processed.append({**r, 'suggested': p_need})

    # 3. INV
    df_inv = dm.get_distribution_rules("Investment")
    total_inv = 0
    if not df_inv.empty:
        for _, r in df_inv.iterrows():
            if str(r['id']) not in disabled_ids:
                val = (r['value']/100)*real_income if r['allocation_type'] == 'Percentage' else r['value']*factor
                total_inv += round(val, 2)

    # 4. GF
    df_gf = dm.get_distribution_rules("GuiltFree")
    total_gf_rules = 0
    if not df_gf.empty:
        for _, r in df_gf.iterrows():
            if str(r['id']) not in disabled_ids:
                val = (r['value']/100)*real_income if r['allocation_type'] == 'Percentage' else r['value']*factor
                total_gf_rules += round(val, 2)

    total_used = round(total_fc + total_sv + total_inv + total_gf_rules, 2)
    remanente = round(max(0, real_income - total_used), 2)
    total_gf_global = round(total_gf_rules + remanente, 2)

    # --- CARDS ---
    def make_card(grp_id, title, total, color):
        pct = (total / real_income * 100) if real_income > 0 else 0
        st = {**CARD_STYLE, **SELECTED_STYLE} if selected_grp == grp_id else CARD_STYLE
        return dbc.Col(html.Div(dbc.Card([dbc.CardBody([
            html.H6(title, className=f"text-{color} fw-bold text-uppercase mb-1"),
            html.H3(f"${total:,.2f}", className="mb-0"),
            html.Small(f"{pct:.1f}% del Total", className="text-muted")
        ], className="p-3 text-center")], className="h-100 shadow-sm"), style=st, id={"type": "grp-card", "group": grp_id}, n_clicks=0), width=6, lg=3, className="mb-3")

    cards = dbc.Row([
        make_card("FC", "Costos Fijos", total_fc, "info"),
        make_card("SV", "Metas Ahorro", total_sv, "success"),
        make_card("INV", "Inversión", total_inv, "warning"),
        make_card("GF", "Guilt Free", total_gf_global, "secondary"),
    ])

    # --- DETALLES ---
    detail_list = []
    actions = []
    title_text = ""
    current_acc_val = None
    
    def make_item_row(item_id, name, amount, hint, is_checked, grp, allow_edit=False):
        amt_style = {"textDecoration": "line-through", "color": "#aaa"} if not is_checked else {"fontWeight": "bold"}
        btns = []
        if allow_edit:
            btns = [
                dbc.Button(html.I(className="bi bi-pencil"), id={"type": "btn-edit-rule", "index": item_id, "cat": grp}, size="sm", color="light", className="me-1 text-primary border-0"),
                dbc.Button(html.I(className="bi bi-trash"), id={"type": "btn-del-rule", "index": item_id}, size="sm", color="light", className="text-danger border-0")
            ]
        return dbc.ListGroupItem([
            dbc.Row([
                dbc.Col([html.Div(name, className="fw-bold"), html.Small(hint, className="text-info small")], width=5),
                dbc.Col(html.Div(f"${amount:,.2f}", style=amt_style, className="text-end"), width=3),
                dbc.Col(html.Div(btns, className="text-end"), width=2),
                dbc.Col(dbc.Switch(id={"type": "item-toggle", "group": grp, "index": item_id}, value=is_checked, className="d-flex justify-content-end"), width=2)
            ], className="align-items-center")
        ], className="px-3 py-2")

    if selected_grp == "FC":
        title_text = "Costos Fijos"
        current_acc_val = s_fc
        if not df_fc.empty:
            for _, r in df_fc.iterrows():
                val = max((r['amount']/100)*real_income, r.get('min_amount', 0)*factor) if r['is_percentage'] else r['monthly_cost']*factor
                is_on = str(r['id']) not in disabled_ids
                hint = f"{r['amount']}%" if r['is_percentage'] else "Fijo"
                detail_list.append(make_item_row(r['id'], r['name'], round(val, 2), hint, is_on, "FC"))
        else: detail_list = html.Div("Sin datos.", className="p-3")

    elif selected_grp == "SV":
        title_text = "Ahorros"
        current_acc_val = s_sv
        if not df_sv.empty:
            for r in sv_items_processed:
                is_on = str(r['id']) not in disabled_ids
                hint = f"Modo: {r.get('contribution_mode', 'Date')}"
                detail_list.append(make_item_row(r['id'], r['name'], r['suggested'], hint, is_on, "SV"))
        else: detail_list = html.Div("Sin metas.", className="p-3")

    elif selected_grp == "INV":
        title_text = "Inversiones"
        current_acc_val = s_inv
        actions = dbc.Button("+ Nueva Regla", id={"type": "btn-add-rule", "cat": "Investment"}, color="warning", size="sm", outline=True)
        if not df_inv.empty:
             for _, r in df_inv.iterrows():
                is_on = str(r['id']) not in disabled_ids
                val = (r['value']/100)*real_income if r['allocation_type'] == 'Percentage' else r['value']*factor
                detail_list.append(make_item_row(r['id'], r['name'], round(val, 2), "Regla Inv", is_on, "INV", allow_edit=True))
        else: detail_list = html.Div("Sin reglas.", className="p-3")

    elif selected_grp == "GF":
        title_text = "Guilt Free"
        current_acc_val = s_gf
        actions = dbc.Button("+ Nueva Regla", id={"type": "btn-add-rule", "cat": "GuiltFree"}, color="secondary", size="sm", outline=True)
        gf_items = []
        if not df_gf.empty:
             for _, r in df_gf.iterrows():
                is_on = str(r['id']) not in disabled_ids
                val = (r['value']/100)*real_income if r['allocation_type'] == 'Percentage' else r['value']*factor
                gf_items.append(make_item_row(r['id'], r['name'], round(val, 2), "Regla GF", is_on, "GF", allow_edit=True))
        
        detail_list = [
            html.Div(gf_items),
            html.Div([
                html.Hr(),
                html.H5("Sobrante Automático", className="text-success text-center"),
                html.H3(f"${remanente:,.2f}", className="text-center fw-bold"),
                html.P("Este monto se suma al total de Guilt Free.", className="text-center text-muted small")
            ], className="p-3 bg-light mt-2 rounded")
        ]

    acc_dropdown = None
    if selected_grp in ["FC", "SV", "INV", "GF"]:
        acc_dropdown = dcc.Dropdown(id="detail-account-dropdown", options=acc_opts, value=current_acc_val, placeholder=f"Cuenta para {title_text}", clearable=True, className="text-dark", optionHeight=65)
    
    grand_total_str = f"${(total_fc + total_sv + total_inv + total_gf_global):,.2f}"
    return cards, grand_total_str, dbc.ListGroup(detail_list, flush=True), title_text, acc_dropdown, actions, extra_text

# 3. SELECT GROUP
@callback(Output("selected-group", "data"), Input({"type": "grp-card", "group": ALL}, "n_clicks"), prevent_initial_call=True)
def select_group(n_clicks):
    if not any(n_clicks): return no_update
    return ctx.triggered_id['group']

# 4. UPDATE STORES
@callback(
    [Output("store-acc-fc", "data", allow_duplicate=True), Output("store-acc-sv", "data", allow_duplicate=True),
     Output("store-acc-inv", "data", allow_duplicate=True), Output("store-acc-gf", "data", allow_duplicate=True)],
    Input("detail-account-dropdown", "value"),
    [State("selected-group", "data"), State("store-acc-fc", "data"), State("store-acc-sv", "data"), State("store-acc-inv", "data"), State("store-acc-gf", "data")],
    prevent_initial_call=True
)
def update_account_stores(new_val, grp, s_fc, s_sv, s_inv, s_gf):
    if grp == "FC": 
        dm.update_user_fc_fund_account(new_val)
        s_fc = new_val
    elif grp == "SV": 
        dm.update_user_sv_fund_account(new_val)
        s_sv = new_val
    elif grp == "INV": 
        dm.update_user_inv_fund_account(new_val)
        s_inv = new_val
    elif grp == "GF": 
        dm.update_user_gf_fund_account(new_val)
        s_gf = new_val
    return s_fc, s_sv, s_inv, s_gf

# 5. TOGGLE
@callback(Output("disabled-items", "data"), Input({"type": "item-toggle", "group": ALL, "index": ALL}, "value"), State("disabled-items", "data"), prevent_initial_call=True)
def toggle_items(values, current):
    trig = ctx.triggered_id
    if not trig: return no_update
    iid = str(trig['index'])
    current = set(current or [])
    if ctx.triggered[0]['value']: current.discard(iid)
    else: current.add(iid)
    return list(current)

# 6. GESTIÓN MODAL REGLA
@callback(
    [Output("rule-modal", "is_open"), Output("rule-name", "value"), Output("rule-alloc-type", "value"),
     Output("rule-value", "value"), Output("rule-category-type", "data"), Output("rule-edit-id", "data")],
    [Input({"type": "btn-add-rule", "cat": ALL}, "n_clicks"), 
     Input({"type": "btn-edit-rule", "index": ALL, "cat": ALL}, "n_clicks"),
     Input("btn-cancel-rule", "n_clicks"), Input("btn-save-rule", "n_clicks")],
    State("rule-modal", "is_open"),
    prevent_initial_call=True
)
def toggle_rule_modal(n_add, n_edit, n_cancel, n_save, is_open):
    trig = ctx.triggered_id
    if not trig: return no_update
    if isinstance(trig, dict) and trig['type'] == "btn-add-rule":
        if not ctx.triggered[0]['value']: return no_update
        return True, "", "Percentage", "", trig['cat'], None
    if isinstance(trig, dict) and trig['type'] == "btn-edit-rule":
        if not ctx.triggered[0]['value']: return no_update
        rule = dm.get_distribution_rule_by_id(trig['index'])
        if rule: return True, rule['name'], rule['allocation_type'], rule['value'], trig['cat'], rule['id']
    if trig in ["btn-cancel-rule", "btn-save-rule"]:
        return False, no_update, no_update, no_update, no_update, no_update
    return no_update, no_update, no_update, no_update, no_update, no_update

# 7. GUARDAR REGLA
@callback(Output("rev-update-signal", "data", allow_duplicate=True), Input("btn-save-rule", "n_clicks"), [State("rule-name", "value"), State("rule-alloc-type", "value"), State("rule-value", "value"), State("rule-category-type", "data"), State("rule-edit-id", "data")], prevent_initial_call=True)
def save_rule(n, name, atype, val, cat, edit_id):
    if n and name:
        if edit_id: dm.update_distribution_rule(edit_id, name, atype, float(val or 0))
        else: dm.add_distribution_rule(cat, name, atype, float(val or 0), None)
        return 1
    return no_update

# 8. BORRAR REGLA
@callback(Output("rev-update-signal", "data", allow_duplicate=True), Input({"type": "btn-del-rule", "index": ALL}, "n_clicks"), prevent_initial_call=True)
def delete_rule(n):
    if not any(n): return no_update
    dm.delete_distribution_rule(ctx.triggered_id['index'])
    return 1

# 9. EJECUTAR (Con lógica de Transferencia Extra y BLINDAJE DE SEGURIDAD)
@callback(
    [Output("rev-feedback", "is_open"), Output("rev-feedback", "children"), Output("rev-feedback", "icon")],
    Input("btn-execute-dist", "n_clicks"),
    [State("input-total-income", "value"), State("periodicity-selector", "value"), State("dd-source-account", "value"), State("disabled-items", "data"),
     State("store-acc-fc", "data"), State("store-acc-sv", "data"), State("store-acc-inv", "data"), State("store-acc-gf", "data")],
    prevent_initial_call=True
)
def execute(n, income_val, periodicity, src_acc, disabled_ids, acc_fc, acc_sv, acc_inv, acc_gf):
    if not n: return no_update
    if not src_acc: return True, "Falta Cuenta Origen", "warning"
    
    manual_income = float(income_val) if income_val else 0.0
    factor = 0.5 if periodicity == "biweekly" else 1.0
    disabled_ids = disabled_ids or []
    dist_data = []

    # 1. CÁLCULO PREVIO DEL EXTRA
    extra_val = 0.0
    stab_acc_id = dm.get_user_stabilizer_account()
    if stab_acc_id:
        conn = dm.get_connection()
        try:
            res = conn.execute("SELECT current_balance FROM accounts WHERE id=?", (stab_acc_id,)).fetchone()
            stab_bal = res[0] if res else 0.0
        finally: conn.close()
        
        proj = dm.calculate_stabilizer_projection(0, stab_bal, frequency=periodicity)
        extra_val = round(proj['suggested_withdrawal'], 2)
    
    # 2. CALCULAR TOTAL REAL DISPONIBLE
    real_income = round(manual_income + extra_val, 2)

    # 3. CONSTRUIR LISTA DE DISTRIBUCIÓN
    def add(grp, row, target, amount):
        if amount > 0: dist_data.append({'type': grp, 'id': row['id'], 'amount': round(amount, 2), 'target_acc': target, 'name': row['name']})

    # FC
    for _, r in dm.get_fixed_costs_df().iterrows():
        if str(r['id']) not in disabled_ids:
            val = max((r['amount']/100)*real_income, r.get('min_amount',0)*factor) if r['is_percentage'] else r['monthly_cost']*factor
            add("FC", r, acc_fc, val)
    # SV
    for _, r in dm.get_savings_goals_df().iterrows():
        if str(r['id']) not in disabled_ids:
            mode = r.get('contribution_mode', 'Date')
            val = 0
            if mode == 'Date':
                rem = r['target_amount'] - r['current_saved']
                if rem > 0 and r['target_date']:
                    try:
                        m = max((datetime.strptime(r['target_date'], '%Y-%m-%d').date() - date.today()).days / 30.44, 1)
                        val = (rem/m)*factor
                    except: pass
            elif mode == 'Fixed': val = r.get('fixed_contribution', 0) * factor
            elif mode == 'Percentage': val = (r.get('percentage_contribution', 0)/100)*real_income
            add("SV", r, acc_sv, val)
    # INV
    for _, r in dm.get_distribution_rules("Investment").iterrows():
        if str(r['id']) not in disabled_ids:
            val = (r['value']/100)*real_income if r['allocation_type'] == 'Percentage' else r['value']*factor
            add("INV", r, acc_inv, val)
    # GF
    rules_val = 0
    for _, r in dm.get_distribution_rules("GuiltFree").iterrows():
        if str(r['id']) not in disabled_ids:
            val = (r['value']/100)*real_income if r['allocation_type'] == 'Percentage' else r['value']*factor
            add("GF", r, acc_gf, val)
            rules_val += round(val, 2)
            
    # GF Sobrante
    curr_total = sum(d['amount'] for d in dist_data)
    
    # 🚨 VALIDACIÓN CRÍTICA (Tolerancia 1 centavo) 🚨
    if curr_total > real_income + 0.01: 
        return True, f"Error: Tus gastos (${curr_total:,.2f}) superan el ingreso total (${real_income:,.2f}). Ajusta tus reglas.", "danger"

    rem = round(max(0, real_income - curr_total), 2)
    if rem > 0: dist_data.append({'type': 'GF', 'id': 0, 'amount': rem, 'target_acc': acc_gf, 'name': 'Guilt Free (Sobrante)'})

    # 4. EJECUCIÓN CON LÓGICA DE MISMA CUENTA
    final_msg_prefix = ""
    is_same_account = (str(stab_acc_id) == str(src_acc))
    
    # Paso A: Mover Extra (Solo si es diferente cuenta)
    if extra_val > 0:
        if not is_same_account:
            success_stab, msg_stab = dm.execute_stabilizer_withdrawal(extra_val, stab_acc_id, src_acc)
            if not success_stab:
                 return True, f"Error moviendo Extra: {msg_stab}", "danger"
            final_msg_prefix = f"Se movieron ${extra_val:,.2f} de Caja Chica. "
        else:
            final_msg_prefix = f"Extra de ${extra_val:,.2f} ya disponible en cuenta. "

    # Paso B: Distribuir (Siempre se distribuye el total real)
    success, msg = dm.execute_distribution_process(real_income, src_acc, dist_data)
    
    return True, final_msg_prefix + msg, "success" if success else "danger"