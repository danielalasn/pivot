import dash
from dash import dcc, html, callback, Input, Output, State, no_update, ctx, ALL
import dash_bootstrap_components as dbc
import backend.data_manager as dm
from utils import ui_helpers 
from datetime import datetime # Necesario para timestamps

# --- MODALES ---

# 1. MODAL DE PAGO (NUEVO)
pay_fc_modal = dbc.Modal([
    dbc.ModalHeader(dbc.ModalTitle("Registrar Pago de Costo Fijo")),
    dbc.ModalBody([
        html.P(id="pay-fc-label", className="text-muted mb-3"),
        
        dbc.Label("Monto a Pagar ($)"),
        dbc.Input(id="pay-fc-amount", type="number", min=0, step=0.01, className="mb-3"),
        
        dbc.Label("Cuenta de Retiro"),
        dcc.Dropdown(id="pay-fc-account", placeholder="Selecciona la cuenta...", className="text-dark mb-3"),
        
        # Store oculto para saber qué ID estamos pagando
        dcc.Store(id="pay-fc-target-id", data=None),
    ]),
    dbc.ModalFooter([
        dbc.Button("Cancelar", id="btn-cancel-pay-fc", outline=True, className="me-2"),
        dbc.Button("Confirmar Pago", id="btn-confirm-pay-fc", color="success")
    ])
], id="pay-fc-modal", is_open=False, centered=True)

# 2. MODAL EDICIÓN (EXISTENTE)
fc_modal = dbc.Modal([
    dbc.ModalHeader(dbc.ModalTitle("Detalle de Costo Fijo")),
    dbc.ModalBody([
        dbc.Label("Nombre del Gasto"),
        dbc.Input(id="fc-name", placeholder="Ej. Seguro Auto...", className="mb-3"),
        dbc.Row([
            dbc.Col(dbc.Switch(id="fc-is-percentage", label="Definir como % del Ingreso", value=False), className="mb-2")
        ]),
        dbc.Row([
            dbc.Col([dbc.Label("Monto ($)", id="fc-lbl-amount"), dbc.Input(id="fc-amount", type="number", placeholder="0.00")], width=6),
            dbc.Col([dbc.Label("Frecuencia (Meses)"), dbc.Input(id="fc-freq", type="number", value=1, min=1)], width=6),
        ], className="mb-3"),
        dbc.Collapse([
            dbc.Alert("El sistema apartará el mayor entre el % calculado y este mínimo.", color="info", className="small p-2 mb-2"),
            dbc.Label("Monto Mínimo ($)"), dbc.Input(id="fc-min-amount", type="number", value=0), html.Hr(),
        ], id="fc-collapse-min", is_open=False),
        dbc.Row([
            dbc.Col([dbc.Label("Día Pago"), dbc.Input(id="fc-day", type="number", min=1, max=31)], width=6),
            dbc.Col([dbc.Label("Ya apartado ($)", className="text-success fw-bold"), dbc.Input(id="fc-initial-saved", type="number", value=0)], width=6),
        ], className="mb-3"),
        dcc.Store(id="fc-edit-id", data=None),
        html.Div(id="fc-modal-feedback", className="text-center mt-2")
    ]),
    dbc.ModalFooter([
        dbc.Button("Cancelar", id="fc-btn-cancel", outline=True),
        dbc.Button("Guardar", id="fc-btn-save", color="primary", className="ms-2"),
    ])
], id="fc-modal", is_open=False, centered=True, size="md")

# 3. MODAL BORRAR (EXISTENTE)
fc_delete_modal = dbc.Modal([
    dbc.ModalHeader("Eliminar Costo Fijo"),
    dbc.ModalBody("¿Seguro? Solo afecta la planificación."),
    dbc.ModalFooter([
        dbc.Button("Cancelar", id="fc-btn-del-cancel", outline=True),
        dbc.Button("Sí, Eliminar", id="fc-btn-del-confirm", color="danger", className="ms-2"),
    ])
], id="fc-delete-modal", is_open=False, centered=True, size="sm")

# --- LAYOUT ---
layout = html.Div([
    ui_helpers.get_feedback_toast("fc-feedback-toast"), 
    dcc.Store(id="fc-update-signal", data=0),
    dcc.Store(id="fc-delete-id", data=None),
    
    # Agregamos los modales al layout
    fc_modal,
    fc_delete_modal,
    pay_fc_modal, # <--- NUEVO

    html.Br(),
    # DASHBOARD SUPERIOR
    dbc.Card([
        dbc.CardBody([
            html.H5("Monitor de Fondos Fijos", className="card-title text-info mb-4"),
            dbc.Row([
                dbc.Col([
                    dbc.Label("Cuenta de Fondos (Real):"),
                    dcc.Dropdown(id="fc-account-selector", placeholder="Selecciona...", className="text-dark mb-2"),
                    html.Small("Saldo Real:", className="text-muted d-block"),
                    html.H3(id="fc-real-balance", className="text-white")
                ], md=4, className="border-end border-secondary"),
                dbc.Col([
                    html.Small("Total Apartado (Virtual):", className="text-muted d-block"),
                    html.H3(id="fc-virtual-total", className="text-warning"),
                    html.H5(id="fc-monthly-need", className="text-info")
                ], md=4, className="border-end border-secondary text-center"),
                dbc.Col([
                    html.Small("Diferencia:", className="text-muted d-block"),
                    html.H3(id="fc-gap", className="fw-bold"),
                    html.Div(id="fc-gap-msg", className="small")
                ], md=4, className="text-center"),
            ])
        ])
    ], className="mb-4 metric-card"),

    # LISTA
    dbc.Row([
        dbc.Col(html.H4("Mis Costos Fijos"), width=True),
        dbc.Col(dbc.Button("+ Agregar Costo", id="fc-btn-add", color="success"), width="auto"),
    ], className="mb-3 align-items-center"),
    html.Div(id="fc-list-container")
])


# ==============================================================================
# CALLBACKS
# ==============================================================================

# 1. Cargar Opciones
@callback(
    [Output("fc-account-selector", "options"), Output("fc-account-selector", "value")],
    Input("url", "pathname")
)
def load_account_options(path):
    if path != "/distribucion": return no_update, no_update
    return dm.get_account_options(), dm.get_user_fc_fund_account()

# 2. Guardar Preferencia
@callback(Output("fc-update-signal", "data", allow_duplicate=True), Input("fc-account-selector", "value"), prevent_initial_call=True)
def save_pref(acc_id):
    if acc_id: dm.update_user_fc_fund_account(acc_id)
    return no_update

# 3. INTERACTIVIDAD DEL MODAL (Mostrar/Ocultar campos de porcentaje)
@callback(
    [Output("fc-collapse-min", "is_open"),
     Output("fc-lbl-amount", "children")],
    Input("fc-is-percentage", "value")
)
def toggle_percentage_fields(is_pct):
    if is_pct:
        return True, "Porcentaje del Ingreso (%)"
    else:
        return False, "Monto Fijo ($)"

# 4. Actualizar Dashboard
@callback(
    [Output("fc-real-balance", "children"), Output("fc-virtual-total", "children"),
     Output("fc-monthly-need", "children"), Output("fc-gap", "children"),
     Output("fc-gap", "className"), Output("fc-gap-msg", "children")],
    [Input("fc-account-selector", "value"), Input("fc-update-signal", "data")],
     prevent_initial_call=True
)
def update_dash(acc_id, sig):
    real_bal = 0.0
    if acc_id:
        conn = dm.get_connection()
        try:
            if acc_id == 'RESERVE': real_bal = dm.get_credit_abono_reserve()
            else:
                res = conn.execute("SELECT current_balance FROM accounts WHERE id=?", (acc_id,)).fetchone()
                if res: real_bal = res[0]
        finally: conn.close()
    
    df = dm.get_fixed_costs_df()
    if df.empty:
        virtual_total, monthly_need = 0.0, 0.0
    else:
        virtual_total = df['current_allocation'].sum()
        def calc_need(row):
            base = row['min_amount'] if row.get('is_percentage', 0) else row['amount']
            return base / row['frequency']
        monthly_need = df.apply(calc_need, axis=1).sum()

    gap = real_bal - virtual_total
    gap_class = "fw-bold text-success" if gap >= 0 else "fw-bold text-danger"
    gap_msg = "¡Cubierto!" if gap >= 0 else f"Falta ${abs(gap):,.2f}"

    return f"${real_bal:,.2f}", f"${virtual_total:,.2f}", f"${monthly_need:,.2f} (Base)", f"${gap:,.2f}", gap_class, gap_msg

# 5. Renderizar Lista (ACTUALIZADO CON BOTÓN DE PAGO)
@callback(Output("fc-list-container", "children"), Input("fc-update-signal", "data"))
def render_list(sig):
    df = dm.get_fixed_costs_df()
    if df.empty: return html.Div("Sin costos registrados.", className="text-center text-muted py-5")

    cards = []
    for _, row in df.iterrows():
        is_pct = row.get('is_percentage', 0)
        current = row['current_allocation']
        
        if is_pct:
            pct_val = row['amount']
            min_val = row.get('min_amount', 0)
            target_desc = f"{pct_val}% del Ingreso"
            detail_desc = f"(Mínimo asegurado: ${min_val:,.2f})"
            target_ref = min_val if min_val > 0 else 1 
        else:
            target_desc = f"${row['amount']:,.2f}"
            detail_desc = "Costo Fijo Total"
            target_ref = row['amount']

        progress_pct = (current / target_ref * 100) if target_ref > 0 else 0
        freq_txt = "Mensual" if row['frequency'] == 1 else f"Cada {row['frequency']} meses"

        card = dbc.Col(dbc.Card([
            dbc.CardBody([
                dbc.Row([
                    dbc.Col([
                        html.H5(row['name'], className="fw-bold mb-0"),
                        html.Small(f"{freq_txt} • Día {row['due_day']}", className="text-muted")
                    ]),
                    # AQUÍ AGREGAMOS EL BOTÓN DE PAGO
                    dbc.Col([
                        dbc.Button(html.I(className="bi bi-wallet2"), id={'type': 'fc-btn-pay', 'index': row['id']}, 
                                   color="success", size="sm", className="me-1", title="Pagar (Descontar de Apartado)"),
                        dbc.Button(html.I(className="bi bi-pencil"), id={'type': 'fc-edit', 'index': row['id']}, 
                                   color="light", size="sm", className="me-1"),
                        dbc.Button(html.I(className="bi bi-trash"), id={'type': 'fc-del', 'index': row['id']}, 
                                   color="danger", outline=True, size="sm"),
                    ], width="auto")
                ], className="mb-3"),

                dbc.Row([
                    dbc.Col([
                        html.Div(target_desc, className="h4 text-info mb-0"),
                        html.Small(detail_desc, className="text-muted")
                    ]),
                    dbc.Col([
                        html.Div("Apartado:", className="text-end small text-muted"),
                        html.Div(f"${current:,.2f}", className="h5 text-end text-success fw-bold")
                    ])
                ], className="mb-3 align-items-center"),

                dbc.Progress(value=progress_pct, label=f"{progress_pct:.0f}% cubierto (del min)", 
                             color="success" if progress_pct>=100 else "warning", className="mb-2", style={"height": "15px"}),
            ])
        ], className="h-100 shadow-sm border-light"), lg=4, md=6, sm=12, className="mb-4")
        cards.append(card)

    return dbc.Row(cards)

# 6. Abrir/Guardar Modal EDICIÓN (Mantenemos igual)
@callback(
    [Output("fc-modal", "is_open"), Output("fc-name", "value"), Output("fc-amount", "value"),
     Output("fc-freq", "value"), Output("fc-day", "value"), Output("fc-initial-saved", "value"),
     Output("fc-is-percentage", "value"), Output("fc-min-amount", "value"),
     Output("fc-edit-id", "data")],
    [Input("fc-btn-add", "n_clicks"), Input("fc-btn-cancel", "n_clicks"), Input({'type': 'fc-edit', 'index': ALL}, 'n_clicks')],
    [State("fc-modal", "is_open")], prevent_initial_call=True
)
def toggle_modal(n_add, n_cancel, n_edit, is_open):
    trig = ctx.triggered_id
    if not trig: return no_update

    if trig == "fc-btn-cancel": return False, "", "", 1, "", 0, False, 0, None
    if trig == "fc-btn-add": return True, "", "", 1, "", 0, False, 0, None
    
    if isinstance(trig, dict) and trig['type'] == 'fc-edit' and ctx.triggered[0]['value']:
        row = dm.get_fixed_costs_df()[dm.get_fixed_costs_df()['id'] == trig['index']].iloc[0]
        return True, row['name'], row['amount'], row['frequency'], row['due_day'], row['current_allocation'], \
               bool(row.get('is_percentage', 0)), row.get('min_amount', 0), row['id']
        
    return no_update

@callback(
    [Output("fc-update-signal", "data", allow_duplicate=True), Output("fc-modal", "is_open", allow_duplicate=True),
     Output("fc-feedback-toast", "is_open", allow_duplicate=True), Output("fc-feedback-toast", "children", allow_duplicate=True), Output("fc-feedback-toast", "icon", allow_duplicate=True)],
    Input("fc-btn-save", "n_clicks"),
    [State("fc-name", "value"), State("fc-amount", "value"), State("fc-freq", "value"),
     State("fc-day", "value"), State("fc-initial-saved", "value"), State("fc-is-percentage", "value"),
     State("fc-min-amount", "value"), State("fc-edit-id", "data"), State("fc-update-signal", "data")],
    prevent_initial_call=True
)
def save_data(n, name, amount, freq, day, saved, is_pct, min_amt, edit_id, sig):
    if not n: return no_update
    if not name or amount is None: return no_update, True, True, "Faltan datos", "warning"

    is_p_int = 1 if is_pct else 0
    m_amt = float(min_amt) if min_amt else 0.0
    
    if edit_id:
        success, msg = dm.update_fixed_cost(edit_id, name, float(amount), int(freq or 1), int(day or 1), float(saved or 0), is_p_int, m_amt)
    else:
        success, msg = dm.add_fixed_cost(name, float(amount), int(freq or 1), int(day or 1), float(saved or 0), is_p_int, m_amt)
        
    if success: return (sig or 0)+1, False, True, "Guardado exitosamente", "success"
    return no_update, True, True, f"Error: {msg}", "danger"

# 7. Borrar (Mantenemos igual)
@callback(
    [Output("fc-delete-modal", "is_open"), Output("fc-delete-id", "data")],
    [Input({'type': 'fc-del', 'index': ALL}, 'n_clicks'), Input("fc-btn-del-cancel", "n_clicks")],
    prevent_initial_call=True
)
def prompt_delete(n_del, n_cancel):
    trig = ctx.triggered_id
    if trig == "fc-btn-del-cancel": return False, None
    if isinstance(trig, dict) and ctx.triggered[0]['value']: return True, trig['index']
    return no_update

@callback(
    [Output("fc-update-signal", "data", allow_duplicate=True), Output("fc-delete-modal", "is_open", allow_duplicate=True)],
    Input("fc-btn-del-confirm", "n_clicks"),
    [State("fc-delete-id", "data"), State("fc-update-signal", "data")], prevent_initial_call=True
)
def exec_delete(n, fc_id, sig):
    if n and fc_id:
        dm.delete_fixed_cost(fc_id)
        return (sig or 0)+1, False
    return no_update


# ==============================================================================
# 8. CALLBACKS NUEVOS: GESTIÓN DE PAGO (OPEN / EXECUTE)
# ==============================================================================

# A. Abrir/Cerrar Modal de Pago
@callback(
    [Output("pay-fc-modal", "is_open"),
     Output("pay-fc-target-id", "data"),
     Output("pay-fc-label", "children"),
     Output("pay-fc-amount", "value"),
     Output("pay-fc-account", "options"),
     Output("pay-fc-account", "value")],
    [Input({"type": "fc-btn-pay", "index": ALL}, "n_clicks"),
     Input("btn-cancel-pay-fc", "n_clicks")],
    [State("pay-fc-modal", "is_open"),
     State("fc-account-selector", "value")],
    prevent_initial_call=True
)
def toggle_pay_fc_modal(n_pay, n_cancel, is_open, default_fc_acc):
    trig = ctx.triggered_id
    if not trig: return no_update

    # Cerrar
    if trig == "btn-cancel-pay-fc":
        return False, no_update, no_update, no_update, no_update, no_update

    # Abrir
    if isinstance(trig, dict) and trig['type'] == "fc-btn-pay":
        # Verificar click real
        if not ctx.triggered[0]['value']: return no_update
        
        fc_id = trig['index']
        
        # Buscar el costo fijo específico para obtener su acumulado y nombre
        df = dm.get_fixed_costs_df()
        row = df[df['id'] == fc_id].iloc[0]
        
        current_alloc = row.get('current_allocation', 0) or 0
        name = row['name']
        
        acc_opts = dm.get_account_options()
        msg = f"Vas a registrar el pago de '{name}'. Tienes apartado: ${current_alloc:,.2f}"
        
        # Pre-llenamos el monto con lo acumulado (puedes cambiar esto si prefieres que empiece en 0)
        # y seleccionamos la cuenta de fondos por defecto
        return True, fc_id, msg, current_alloc, acc_opts, default_fc_acc

    return no_update, no_update, no_update, no_update, no_update, no_update


# B. Confirmar Pago
@callback(
    [Output("pay-fc-modal", "is_open", allow_duplicate=True),
     Output("fc-update-signal", "data", allow_duplicate=True),
     Output("fc-feedback-toast", "is_open", allow_duplicate=True), 
     Output("fc-feedback-toast", "children", allow_duplicate=True), 
     Output("fc-feedback-toast", "icon", allow_duplicate=True)],
    Input("btn-confirm-pay-fc", "n_clicks"),
    [State("pay-fc-target-id", "data"),
     State("pay-fc-amount", "value"),
     State("pay-fc-account", "value"),
     State("fc-update-signal", "data")],
    prevent_initial_call=True
)
def confirm_fc_payment(n, fc_id, amount, acc_id, sig):
    if not n: return no_update
    
    if not amount or amount <= 0:
        return True, no_update, True, "Ingresa un monto válido.", "warning"
    
    if not acc_id:
        return True, no_update, True, "Selecciona una cuenta de pago.", "warning"
        
    # Llamamos a la función que creamos en data_manager.py
    success, msg = dm.pay_fixed_cost_balance(fc_id, float(amount), acc_id)
    
    if success:
        # Éxito: Cerrar modal, actualizar lista (signal + 1) y mostrar toast
        return False, (sig or 0)+1, True, msg, "success"
    else:
        # Error: Mantener modal, mostrar error
        return True, no_update, True, msg, "danger"