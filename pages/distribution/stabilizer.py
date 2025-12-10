# pages/distribution/stabilizer.py
import dash
from dash import dcc, html, callback, Input, Output, State, no_update, ctx, ALL
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
import backend.data_manager as dm
from utils import ui_helpers 
from datetime import date

# --- MODAL AGREGAR/EDITAR EVENTO ---
event_modal = dbc.Modal([
    dbc.ModalHeader(html.Div("Gestión de Ingreso Extra", id="modal-header-text")),
    dbc.ModalBody([
        dbc.Label("Nombre"),
        dbc.Input(id="ev-name", placeholder="Bono, Aguinaldo...", className="mb-3"),
        dbc.Row([
            dbc.Col([dbc.Label("Monto ($)"), dbc.Input(id="ev-amount", type="number")], width=6),
            dbc.Col([dbc.Label("Fecha de Pago"), dcc.DatePickerSingle(id="ev-date", date=date.today(), display_format='YYYY-MM-DD', className="d-block")], width=6),
        ]),
    ]),
    dbc.ModalFooter([
        dbc.Button("Guardar", id="ev-btn-save", color="success"),
    ])
], id="event-modal", is_open=False, centered=True)

# --- LAYOUT ---
layout = html.Div([
    ui_helpers.get_feedback_toast("stab-feedback"),
    dcc.Store(id="stab-update-signal", data=0),
    # NUEVO: Store para guardar el ID que estamos editando (None si es nuevo)
    dcc.Store(id="stab-edit-id", data=None), 
    event_modal,

    html.Br(),
    # 1. CONFIGURACIÓN SUPERIOR
    dbc.Card([
        dbc.CardHeader([
            dbc.Row([
                dbc.Col(html.H5("Distribuidor de Caja Chica", className="mb-0 text-primary"), width=True),
                dbc.Col(
                    dbc.RadioItems(
                        id="stab-frequency",
                        options=[
                            {"label": "Vista Mensual", "value": "monthly"},
                            {"label": "Vista Quincenal", "value": "biweekly"},
                        ],
                        value="monthly",
                        inline=True,
                        className="mb-0"
                    ), width="auto"
                )
            ], className="align-items-center")
        ]),
        dbc.CardBody([
            dbc.Row([
                dbc.Col([
                    dbc.Label("Cuenta 'Caja Chica'"),
                    dcc.Dropdown(id="stab-account-selector", placeholder="Selecciona cuenta...", className="text-dark"),
                    html.Small(id="stab-current-balance-lbl", className="text-muted")
                ], md=6),
                
                dbc.Col([
                    dbc.Label("Resumen de Extras"),
                    html.Div(id="stab-summary-box", className="p-2 bg-light rounded text-center border")
                ], md=6),
            ], className="align-items-center")
        ])
    ], className="mb-4 shadow-sm"),

    # 2. GRÁFICA Y RESULTADOS
    dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardHeader("Proyección de Saldo en Caja Chica"),
                dbc.CardBody([
                    dcc.Graph(id="stab-projection-chart", style={"height": "300px"}),
                    html.Div(id="stab-sustainability-msg", className="text-center mt-2 fw-bold")
                ])
            ], className="h-100 shadow-sm")
        ], md=8),
        
        dbc.Col([
            dbc.Card([
                dbc.CardHeader("Retiro Sugerido"),
                dbc.CardBody([
                    html.Div([
                        html.Small("Puedes retirar de tu Caja Chica:", className="text-muted text-uppercase fw-bold"),
                        html.H2(id="stab-total-pay-display", className="text-success fw-bold display-5 my-2"),
                        
                        html.Div(id="stab-breakdown-box", className="bg-light p-2 rounded mb-3 small"),
                        
                        html.Hr(),
                        dbc.Button("+ Programar Ingreso Futuro", id="stab-btn-add-event", color="secondary", outline=True, size="sm", className="w-100 mt-2"),
                    ], className="text-center py-2")
                ])
            ], className="h-100 shadow-sm")
        ], md=4)
    ], className="mb-4"),

    # 3. LISTA DE EVENTOS
    dbc.Card([
        dbc.CardHeader("Ingresos Extras Futuros"),
        dbc.CardBody(html.Div(id="stab-events-list"))
    ], className="shadow-sm")
])


# ==============================================================================
# CALLBACKS
# ==============================================================================

# 1. INIT
@callback(
    [Output("stab-account-selector", "options"), 
     Output("stab-account-selector", "value")],
    Input("url", "pathname")
)
def load_init(path):
    if not path or "distribucion" not in path: return no_update, no_update
    opts = dm.get_account_options()
    sel_acc = dm.get_user_stabilizer_account()
    return opts, sel_acc

# 2. GUARDAR CUENTA
@callback(Output("stab-update-signal", "data", allow_duplicate=True), Input("stab-account-selector", "value"), prevent_initial_call=True)
def save_acc(val):
    if val: dm.update_user_stabilizer_account(val)
    return no_update

# 3. DASHBOARD PRINCIPAL
# En pages/distribution/stabilizer.py

# En pages/distribution/stabilizer.py

# ... (imports y layout igual) ...

@callback(
    [Output("stab-summary-box", "children"),
     Output("stab-projection-chart", "figure"),
     Output("stab-sustainability-msg", "children"),
     Output("stab-sustainability-msg", "className"),
     Output("stab-total-pay-display", "children"),
     Output("stab-breakdown-box", "children"),
     Output("stab-current-balance-lbl", "children")],
    [Input("stab-account-selector", "value"),
     Input("stab-frequency", "value"),
     Input("stab-update-signal", "data")]
)
def update_stabilizer(acc_id, freq, sig):
    base_monthly = 0.0 
    
    real_bal = 0.0
    if acc_id:
        conn = dm.get_connection()
        try:
            if acc_id == 'RESERVE': real_bal = dm.get_credit_abono_reserve()
            else:
                res = conn.execute("SELECT current_balance FROM accounts WHERE id=?", (acc_id,)).fetchone()
                if res: real_bal = res[0]
        finally: conn.close()
    
    data = dm.calculate_stabilizer_projection(base_monthly, real_bal, frequency=freq)
    
    ideal_amt = data['supplement_ideal']
    suggested_amt = data['suggested_withdrawal']
    df_proj = data['projection']
    is_capped = data['is_capped']
    bottleneck = data.get('bottleneck_period', 'Futuro')
    
    lbl_freq = "Mes" if freq == "monthly" else "Quincena"
    
    # Summary
    summary = [
        html.Div(f"Total Extras: ${data['total_annual_income']:,.2f}", className="fw-bold"),
        html.Small(f"Meta Ideal: ${ideal_amt:,.2f}/{lbl_freq}", className="text-muted"),
    ]
    
    # Chart
    fig = go.Figure()
    
    # Línea de Saldo (Azul Neón)
    fig.add_trace(go.Scatter(
        x=df_proj['Month'], y=df_proj['Balance'],
        mode='lines+markers', name='Saldo Proyectado',
        line=dict(color='#375a7f', width=3, shape='hv'), # Azul un poco más sobrio o neón (#0d6efd)
        fill='tozeroy', 
        fillcolor='rgba(55, 90, 127, 0.2)' # Transparencia sutil para dark mode
    ))
    
    # Línea de referencia del 0 (Rojo brillante)
    fig.add_trace(go.Scatter(
        x=df_proj['Month'], y=[0]*len(df_proj),
        mode='lines', name='Límite',
        line=dict(color='#ff5555', dash='dot', width=1)
    ))

    fig.update_layout(
        margin=dict(l=20, r=20, t=30, b=20),
        yaxis_title="Saldo ($)",
        # --- AQUÍ ESTÁ LA MAGIA ---
        template="plotly_dark",         # Cambia letras a blanco
        paper_bgcolor='rgba(0,0,0,0)',  # Fondo transparente (contenedor)
        plot_bgcolor='rgba(0,0,0,0)',   # Fondo transparente (gráfica)
        # --------------------------
        showlegend=True, 
        legend=dict(orientation="h", y=1.1, font=dict(color="white")),
        font=dict(family="sans-serif", size=12, color="#e0e0e0"),
        xaxis=dict(showgrid=False, gridcolor='rgba(255, 255, 255, 0.1)'),
        yaxis=dict(gridcolor='rgba(255, 255, 255, 0.1)') # Líneas de guía sutiles
    )

    # Mensajes Inteligentes
    if is_capped:
        # CASO: Estamos retirando menos del ideal (ej. $207 en vez de $461)
        sus_msg = "⚠️ Retiro Sostenible (Fase 1)"
        sus_cls = "text-warning small fw-bold"
        
        breakdown = [
            html.Div(f"Retiro Seguro Actual: ${suggested_amt:,.2f}", className="fw-bold text-success"),
            html.Div(
                f"Estás limitado por el flujo de caja en {bottleneck}.", 
                className="text-muted small mt-1"
            ),
            html.Div(
                f"📈 Una vez pases {bottleneck}, vuelve a calcular para subir a ${ideal_amt:,.2f}.", 
                className="text-primary small fst-italic mt-1 border-top pt-1"
            )
        ]
        display_color = "text-success" # Verde porque ES dinero seguro
        
    else:
        # CASO: Tenemos suficiente para el retiro ideal completo
        sus_msg = "✅ Flujo Óptimo"
        sus_cls = "text-success small fw-bold"
        breakdown = [
            html.Div(f"¡Excelente! Tienes liquidez para el retiro máximo de ${ideal_amt:,.2f}.", className="text-muted")
        ]
        display_color = "text-success"

    total_pay_comp = html.H2(f"${suggested_amt:,.2f}", className=f"{display_color} fw-bold display-5 my-2")

    return summary, fig, sus_msg, sus_cls, total_pay_comp, breakdown, f"Saldo Actual: ${real_bal:,.2f}"


# 5. RENDER LISTA EVENTOS (Actualizado con botón Editar)
@callback(Output("stab-events-list", "children"), Input("stab-update-signal", "data"))
def render_events(sig):
    df = dm.get_income_events_df()
    if df.empty: return html.Div("No hay ingresos extra programados.", className="text-muted text-center py-3")
    items = []
    for _, row in df.iterrows():
        item = dbc.ListGroupItem([
            dbc.Row([
                dbc.Col([
                    html.H6(row['name'], className="mb-0 fw-bold"),
                    html.Small(row['event_date'], className="text-muted")
                ], width=True),
                dbc.Col(html.H5(f"+${row['amount']:,.2f}", className="text-success mb-0 text-end"), width="auto"),
                dbc.Col([
                    # BOTÓN EDITAR (Azul)
                    dbc.Button(html.I(className="bi bi-pencil"), id={'type': 'ev-edit', 'index': row['id']}, color="info", outline=True, size="sm", className="me-2"),
                    # BOTÓN BORRAR (Rojo)
                    dbc.Button(html.I(className="bi bi-trash"), id={'type': 'ev-del', 'index': row['id']}, color="danger", outline=True, size="sm")
                ], width="auto", className="ps-2")
            ], className="align-items-center")
        ])
        items.append(item)
    return dbc.ListGroup(items, flush=True)

# 6. GESTIÓN INTEGRAL DEL MODAL (Abrir, Cargar Datos, Guardar)
@callback(
    [Output("event-modal", "is_open"), 
     Output("stab-update-signal", "data", allow_duplicate=True),
     Output("ev-name", "value"), 
     Output("ev-amount", "value"), 
     Output("ev-date", "date"),
     Output("stab-edit-id", "data"),
     Output("modal-header-text", "children")],
    [Input("stab-btn-add-event", "n_clicks"), 
     Input("ev-btn-save", "n_clicks"),
     Input({'type': 'ev-edit', 'index': ALL}, 'n_clicks')],
    [State("event-modal", "is_open"), 
     State("ev-name", "value"), 
     State("ev-amount", "value"), 
     State("ev-date", "date"), 
     State("stab-edit-id", "data"),
     State("stab-update-signal", "data")],
    prevent_initial_call=True
)
def manage_event_modal(n_add, n_save, n_edit, is_open, name, amount, date_val, edit_id, sig):
    trig = ctx.triggered_id
    
    # CASO 1: ABRIR PARA CREAR NUEVO
    if trig == "stab-btn-add-event":
        # Limpiamos campos y ponemos ID a None
        return True, no_update, "", None, date.today(), None, "Nuevo Ingreso Extra"

    # CASO 2: ABRIR PARA EDITAR (Detectamos click en botón dinámico)
    if isinstance(trig, dict) and trig.get('type') == 'ev-edit':
        # --- AGREGA ESTA LÍNEA DE PROTECCIÓN ---
        # Si la lista de clicks está vacía o son puros None/0, no hagas nada.
        if not any(click for click in n_edit if click): return no_update 
        # ---------------------------------------

        ev_id = trig['index']
        data = dm.get_income_event_by_id(ev_id)
        if data:
            return True, no_update, data['name'], data['amount'], data['event_date'], ev_id, "Editar Ingreso Extra"
        return no_update, no_update, no_update, no_update, no_update, no_update, no_update

    # CASO 3: GUARDAR (Crear o Actualizar)
    if trig == "ev-btn-save":
        if name and amount:
            if edit_id:
                # Actualizar existente
                dm.update_income_event(edit_id, name, float(amount), date_val)
            else:
                # Crear nuevo
                dm.add_income_event(name, float(amount), date_val)
            
            # Cerramos modal, actualizamos señal y limpiamos ID
            return False, (sig or 0)+1, "", None, date.today(), None, "Nuevo Ingreso Extra"
    
    return no_update, no_update, no_update, no_update, no_update, no_update, no_update

# 7. BORRAR EVENTO
@callback(
    Output("stab-update-signal", "data", allow_duplicate=True),
    Input({'type': 'ev-del', 'index': ALL}, 'n_clicks'),
    State("stab-update-signal", "data"), prevent_initial_call=True
)
def delete_event(n, sig):
    if not any(n): return no_update
    eid = ctx.triggered_id['index']
    dm.delete_income_event(eid)
    return (sig or 0)+1 