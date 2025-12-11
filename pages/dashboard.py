# pages/dashboard.py
import dash
from dash import dcc, html, callback, Input, Output, ctx, State, no_update
import plotly.graph_objects as go
import plotly.express as px
import dash_bootstrap_components as dbc
import backend.data_manager as dm
import utils.ui_helpers as ui_helpers
import pandas as pd
from datetime import date
from dateutil.relativedelta import relativedelta

# --- CONFIGURACIÓN DE ESTILO COMÚN PARA GRÁFICOS ---
# Esto asegura que los tooltips (las etiquetas al pasar el mouse) sean oscuros y legibles
HOVER_STYLE = dict(
    bgcolor="#1a1a1a",  # Fondo casi negro
    font_size=13, 
    font_family="sans-serif", 
    font_color="white", # Letra blanca
    bordercolor="#444"  # Borde gris
)

# ------------------------------------------------------------------------------
# LAYOUT DEL DASHBOARD
# ------------------------------------------------------------------------------

layout = dbc.Container(
    [
        # Stores para señales y Toast de notificaciones
        dcc.Store(id='date-range-store', storage_type='local'),
        dcc.Store(id="dashboard-update-signal", data=0), 
        ui_helpers.get_feedback_toast("dashboard-toast"),

        # --- TÍTULO Y REFRESH ---
       dbc.Row([
        dbc.Col(
            html.H2("Resumen Financiero Global", className="mb-0 text-primary"), 
            width="auto", 
            className="d-flex align-items-center"
        ),
        dbc.Col([
            dcc.Loading(
                id="loading-refresh-dash",
                type="circle",
                color="#2A9FD6",
                children=[
                    html.Div([
                        dbc.Button(
                            html.I(className="bi bi-arrow-clockwise"), 
                            id="btn-refresh-dashboard", 
                            color="link", 
                            size="sm", 
                            className="p-0 ms-2 text-decoration-none text-muted fs-4",
                            title="Actualizar datos financieros ahora"
                        ),
                        html.Small(id="last-updated-dash-label", className="text-muted ms-2 small fst-italic"),
                        html.Div(id="dummy-dash-spinner-target", style={"display": "none"})
                    ], className="d-flex align-items-center")
                ]
            )
        ], width="auto", className="d-flex align-items-center ms-auto"),
    ], className="mb-4 align-items-center"),

        # ---------------------------------------------------------
        # 1. CARDS DE PATRIMONIO, ACTIVOS Y DEUDAS (Arriba)
        # ---------------------------------------------------------
        dbc.Row([
            # 1. PATRIMONIO NETO
             dbc.Col(
                dbc.Card(
                    dbc.CardBody([
                        html.H5("Patrimonio Neto Total", className="card-title text-primary"),
                        html.H1(id="nw-total", className="card-value display-4 fw-bold"),
                        html.Small("Activos Reales - Pasivos Totales", className="text-muted")
                    ]),
                    className="metric-card h-100 shadow-sm border-primary"
                ),
                lg=4, md=12, sm=12, className="mb-4"
            ),
            # 2. ACTIVOS
            dbc.Col(
                dbc.Card(
                    dbc.CardBody([
                        html.H5("🟢 Lo que tienes (Activos)", className="card-title text-success"),
                        html.H3(id="nw-assets-total", className="card-value text-success mb-3"),
                        dbc.Row([
                            dbc.Col("Bancos/Efectivo:", className="text-muted"),
                            dbc.Col(id="nw-assets-liquid", className="text-end fw-bold")
                        ], className="mb-1"),
                        html.Div(id="nw-assets-investments-container", className="mb-1"),
                        dbc.Row([
                            dbc.Col("Por Cobrar (IOU):", className="text-muted"),
                            dbc.Col(id="nw-assets-receivable", className="text-end fw-bold")
                        ]),
                    ]),
                    className="metric-card h-100 shadow-sm"
                ),
                lg=4, md=6, sm=12, className="mb-4"
            ),
            # 3. PASIVOS
            dbc.Col(
                dbc.Card(
                    dbc.CardBody([
                        html.H5("🔴 Lo que debes (Pasivos)", className="card-title text-danger"),
                        html.H3(id="nw-liabilities-total", className="card-value text-danger mb-3"),
                        html.Div(id="nw-liabilities-credit-container", className="mb-2"),
                        dbc.Row([
                            dbc.Col("Por Pagar (IOU):", className="text-muted"),
                            dbc.Col(id="nw-liabilities-payable", className="text-end fw-bold")
                        ]),
                    ]),
                    className="metric-card h-100 shadow-sm"
                ),
                lg=4, md=6, sm=12, className="mb-4"
            ),
        ], className="mb-4"),

        # ---------------------------------------------------------
        # 2. MONITOR DEL MES (Ingresos, Gastos, Ahorro)
        # ---------------------------------------------------------
        html.H5("Monitor del Mes Actual", className="text-info mb-3"),
        dbc.Row([
            dbc.Col(
                dbc.Card(dbc.CardBody([
                        html.H6("Ingresos Reales", className="card-title text-success"),
                        html.H2(id="kpi-month-income", className="card-value text-success"),
                        html.Small(id="kpi-month-label-inc", className="text-muted")
                    ]), className="metric-card h-100 shadow-sm"), lg=4, md=6, sm=12, className="mb-4"
            ),
            dbc.Col(
                dbc.Card(dbc.CardBody([
                        html.H6("Gastos Reales", className="card-title text-danger"),
                        html.H2(id="kpi-month-expense", className="card-value text-danger"),
                        html.Small(id="kpi-month-label-exp", className="text-muted")
                    ]), className="metric-card h-100 shadow-sm"), lg=4, md=6, sm=12, className="mb-4"
            ),
            dbc.Col(
                dbc.Card(dbc.CardBody([
                        html.H6("Tasa de Ahorro", className="card-title text-info"),
                        html.H2(id="kpi-savings-rate", className="card-value text-info"),
                        html.Div(id="kpi-savings-bar-container", className="mt-2")
                    ]), className="metric-card h-100 shadow-sm"), lg=4, md=12, sm=12, className="mb-4"
            ),
        ]),
        
        # ---------------------------------------------------------
        # 3. HISTÓRICOS (Patrimonio + Flujo de Caja)
        # ---------------------------------------------------------
        html.H5("Historicos", className="text-info mb-3"),
        # A) EVOLUCIÓN PATRIMONIO
        dbc.Row([
            dbc.Col(
                dbc.Card(
                    dbc.CardBody([
                        dbc.Row([
                            dbc.Col(html.H5("Evolución del Patrimonio", className="card-title"), width=12, md=5),
                            dbc.Col(
                                html.Div([
                                    dbc.ButtonGroup([
                                        dbc.Button("1M", id="btn-1m", n_clicks=0),
                                        dbc.Button("6M", id="btn-6m", n_clicks=0),
                                        dbc.Button("1Y", id="btn-1y", n_clicks=0),
                                        dbc.Button("YTD", id="btn-ytd", n_clicks=0),
                                        dbc.Button("Todo", id="btn-all", n_clicks=0),
                                    ], size="sm", className="me-2"),
                                    dcc.DatePickerRange(
                                        id='nw-date-picker',
                                        display_format='DD/MM/YYYY', 
                                        start_date=None, end_date=date.today(),
                                        style={'zIndex': 100}
                                    )
                                ], className="d-flex justify-content-md-end justify-content-start align-items-center flex-wrap gap-2"), 
                                width=12, md=7
                            )
                        ], className="align-items-center mb-3"),
                        
                        dcc.Loading(
                            type="circle", color="#2A9FD6",
                            children=dcc.Graph(id="graph-networth-history", config={'displayModeBar': False}, style={'height': '350px'})
                        )
                    ]),
                    className="data-card shadow-sm mb-4"
                ),
                width=12
            )
        ]),

        # B) FLUJO DE CAJA (Ahora ocupa todo el ancho, sin gastos al lado)
        dbc.Row([
            dbc.Col(
                dbc.Card(dbc.CardBody([
                        html.H5("Flujo de Caja", className="card-title"),
                        dcc.Graph(id="graph-cashflow", config={'displayModeBar': False}, style={'height': '350px'})
                    ]), className="data-card shadow-sm"), lg=12, md=12, sm=12, className="mb-4" # <-- Cambiado lg=8 a lg=12
            ),
        ]),

        # ---------------------------------------------------------
        # 4. DESGLOSE DETALLADO (TABS)
        # ---------------------------------------------------------
        html.H5("Desglose Ingresos y Gastos", className="text-info mb-3 mt-4"),
        
        dbc.Card([
            dbc.CardBody([
                dbc.Tabs([
                    dbc.Tab(label="Ingresos", tab_id="tab-inc", children=[
                        dbc.Row([
                            dbc.Col([
                                html.H6("Por Categoría", className="text-center text-success mt-3"),
                                dcc.Graph(id="pie-inc-cat", config={'displayModeBar': False}, style={'height': '350px'})
                            ], md=6),
                            dbc.Col([
                                html.H6("Por Subcategoría", className="text-center text-success mt-3"),
                                dcc.Graph(id="pie-inc-sub", config={'displayModeBar': False}, style={'height': '350px'})
                            ], md=6),
                        ])
                    ]),
                    dbc.Tab(label="Gastos", tab_id="tab-exp", children=[
                        dbc.Row([
                            dbc.Col([
                                html.H6("Por Categoría", className="text-center text-danger mt-3"),
                                dcc.Graph(id="pie-exp-cat", config={'displayModeBar': False}, style={'height': '350px'})
                            ], md=6),
                            dbc.Col([
                                html.H6("Por Subcategoría", className="text-center text-danger mt-3"),
                                dcc.Graph(id="pie-exp-sub", config={'displayModeBar': False}, style={'height': '350px'})
                            ], md=6),
                        ])
                    ]),
                ], active_tab="tab-exp") 
            ])
        ], className="data-card shadow-sm mb-5"),

    ], fluid=True, className="page-container"
)
# ------------------------------------------------------------------------------
# CALLBACKS DE CONTROL
# ------------------------------------------------------------------------------

@callback(
    Output('date-range-store', 'data'),
    [Input('btn-1m', 'n_clicks'), Input('btn-6m', 'n_clicks'), Input('btn-1y', 'n_clicks'),
     Input('btn-ytd', 'n_clicks'), Input('btn-all', 'n_clicks')],
    prevent_initial_call=True
)
def save_date_preference(b1, b6, b1y, by, ba):
    trigger = ctx.triggered_id
    if trigger == 'btn-1m': return '1M'
    if trigger == 'btn-6m': return '6M'
    if trigger == 'btn-1y': return '1Y'
    if trigger == 'btn-ytd': return 'YTD'
    if trigger == 'btn-all': return 'ALL'
    return no_update

@callback(
    [Output('nw-date-picker', 'start_date'), Output('nw-date-picker', 'end_date'),
     Output('btn-1m', 'active'), Output('btn-6m', 'active'), Output('btn-1y', 'active'),
     Output('btn-ytd', 'active'), Output('btn-all', 'active')],
    Input('date-range-store', 'data')
)
def load_date_preference(saved_option):
    today = date.today()
    if not saved_option: saved_option = 'YTD' 
    start_date = date(today.year, 1, 1)
    if saved_option == '1M': start_date = today - relativedelta(months=1)
    elif saved_option == '6M': start_date = today - relativedelta(months=6)
    elif saved_option == "1Y": start_date = today - relativedelta(months=12)
    elif saved_option == 'YTD': start_date = date(today.year, 1, 1)
    elif saved_option == 'ALL':
        try:
            df_hist = dm.get_historical_networth_trend(start_date="1900-01-01")
            if not df_hist.empty: start_date = df_hist['date'].min()
            else: start_date = date(today.year, 1, 1)
        except: start_date = date(today.year, 1, 1)
    return (start_date, today, saved_option == '1M', saved_option == '6M', saved_option == '1Y',saved_option == 'YTD', saved_option == 'ALL')

@callback(
    [Output("dashboard-update-signal", "data"), Output("dashboard-toast", "is_open"),
     Output("dashboard-toast", "children"), Output("dashboard-toast", "icon"),
     Output("dummy-dash-spinner-target", "children")], 
    Input("btn-refresh-dashboard", "n_clicks"), State("dashboard-update-signal", "data"),
    prevent_initial_call=True
)
def manual_dashboard_refresh(n_clicks, signal):
    # print(f"BOTÓN PRESIONADO. Clicks: {n_clicks}")
    if not n_clicks: return no_update, no_update, no_update, no_update, no_update
    success, msg = dm.manual_price_refresh()
    new_signal = (signal or 0) + 1
    if success: return new_signal, *ui_helpers.mensaje_alerta_exito("success", msg), ""
    else: return new_signal, *ui_helpers.mensaje_alerta_exito("danger", msg), ""

# ------------------------------------------------------------------------------
# 4. CALLBACK DE ELEMENTOS ESTÁTICOS
# ------------------------------------------------------------------------------
# --- EN pages/dashboard.py ---

@callback(
    [Output("nw-total", "children"), Output("nw-total", "className"),
     Output("nw-assets-total", "children"), Output("nw-assets-liquid", "children"),
     Output("nw-assets-investments-container", "children"), Output("nw-assets-receivable", "children"),
     Output("nw-liabilities-total", "children"), Output("nw-liabilities-credit-container", "children"),
     Output("nw-liabilities-payable", "children"), Output("kpi-month-income", "children"),
     Output("kpi-month-label-inc", "children"), Output("kpi-month-expense", "children"),
     Output("kpi-month-label-exp", "children"), Output("kpi-savings-rate", "children"),       
     Output("kpi-savings-bar-container", "children"), Output("graph-cashflow", "figure"),
     Output("pie-inc-cat", "figure"),
     Output("pie-inc-sub", "figure"), Output("pie-exp-cat", "figure"),
     Output("pie-exp-sub", "figure"), Output("last-updated-dash-label", "children")],
    [Input("url", "pathname"), Input("dashboard-update-signal", "data")] 
)
def update_static_dashboard_elements(pathname, update_signal):
    if pathname != "/": return [no_update] * 21
    
    # 1. OBTENER EL ID DEL USUARIO ACTUAL (CRÍTICO PARA SEGURIDAD)
    uid = dm.get_uid()
    if not uid: return [no_update] * 21 
    
    # 2. PASAR EL UID A TODAS LAS FUNCIONES (AQUÍ ESTABA EL ERROR)
    df_trans = dm.get_transactions_df(uid) # <--- AQUÍ
    nw_data = dm.get_net_worth_breakdown(uid, force_refresh=False) # <--- AQUÍ (Line 315)
    
    last_ts = dm.get_data_timestamp()
    update_label = f"Precios: {last_ts}"
    
    net_worth = nw_data['net_worth']
    nw_str = f"${net_worth:,.2f}"
    if net_worth == 0: nw_class = "card-value display-4 fw-bold text-muted"
    elif net_worth > 0: nw_class = "card-value display-4 fw-bold text-success"
    else: nw_class = "card-value display-4 fw-bold text-danger"

    assets_str = f"${nw_data['assets']['total']:,.2f}"
    liquid_str = f"${nw_data['assets']['liquid']:,.2f}"
    recv_str = f"${nw_data['assets']['receivables']:,.2f}"
    liab_str = f"${nw_data['liabilities']['total']:,.2f}"
    pay_str = f"${nw_data['liabilities']['payables']:,.2f}"

    # 3. PASAR UID TAMBIÉN A STOCKS
    stocks = dm.get_stocks_data(uid, force_refresh=False) # <--- AQUÍ
    
    inv_total = nw_data['assets']['investments']
    day_gain_usd = sum((s['market_value'] - (s['market_value'] / (1 + s['day_change_pct']/100))) for s in stocks if s.get('day_change_pct'))
    day_gain_pct = (day_gain_usd / (inv_total - day_gain_usd) * 100) if (inv_total - day_gain_usd) != 0 else 0
    inv_color = "text-success" if day_gain_usd >= 0 else "text-danger"
    inv_sign = "+" if day_gain_usd >= 0 else ""
    investments_display = dbc.Row([
        dbc.Col("Inversiones:", className="text-muted"),
        dbc.Col([html.Div(f"${inv_total:,.2f}", className="fw-bold text-info"), html.Small(f"{inv_sign}${abs(day_gain_usd):,.2f} ({inv_sign}{day_gain_pct:.2f}%) hoy", className=f"d-block small {inv_color} fw-bold")], className="text-end")
    ], className="mb-1 align-items-center")

    cred_data = dm.get_credit_summary_data()
    total_limit = cred_data['total_limit']
    total_debt = cred_data['total_debt']
    utilization = (total_debt / total_limit * 100) if total_limit > 0 else 0
    credit_display = html.Div([
        dbc.Row([dbc.Col("Límite Total TC:", className="text-muted"), dbc.Col(f"${total_limit:,.2f}", className="text-end fw-bold")], className="mb-1"),
        dbc.Progress([dbc.Progress(value=utilization, color="danger", bar=True), dbc.Progress(value=100-utilization, color="success" if total_debt > 0 else "secondary", bar=True)], style={"height": "10px", "backgroundColor": "#222"}, className="mb-1"),
        dbc.Row([dbc.Col(f"Deuda: ${total_debt:,.2f}", className="text-muted small"), dbc.Col(f"Uso: {utilization:.1f}%", className="text-end small fw-bold text-muted")])
    ])

    EXCLUDED_CATS = dm.get_excluded_categories_list()
    month_income, month_expense = 0.0, 0.0
    if not df_trans.empty:
        df_trans['date_dt'] = pd.to_datetime(df_trans['date'], format='mixed')
        today_d = date.today()
        df_curr = df_trans[(df_trans['date_dt'].dt.month == today_d.month) & (df_trans['date_dt'].dt.year == today_d.year)]
        month_income = df_curr[(df_curr['type'] == 'Income') & (~df_curr['category'].isin(EXCLUDED_CATS))]['amount'].sum()
        month_expense = df_curr[(df_curr['type'] == 'Expense') & (~df_curr['category'].isin(EXCLUDED_CATS))]['amount'].sum()

    savings = month_income - month_expense
    savings_rate = (savings / month_income * 100) if month_income > 0 else 0
    current_month_name = date.today().strftime("%B %Y").capitalize()
    label_month = f"Total en {current_month_name}"
    income_str = f"${month_income:,.2f}"
    expense_str = f"${month_expense:,.2f}"
    savings_str = f"{savings_rate:.1f}%"
    sav_color = "success" if savings_rate >= 20 else ("warning" if savings_rate > 0 else "danger")
    savings_bar = html.Div([
        dbc.Progress(value=max(0, savings_rate), color=sav_color, striped=True, className="mb-2", style={"height": "15px"}),
        html.Div([html.Small(f"Ahorro Neto: ${savings:,.2f}", className=f"text-{sav_color} fw-bold")], className="d-flex justify-content-between")
    ])

    # --- HELPERS GRÁFICOS ---
    def get_empty_fig(title):
        return go.Figure().update_layout(template="plotly_dark", plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", title={'text': title, 'x':0.5, 'xanchor':'center'}, xaxis={'visible': False}, yaxis={'visible': False})

    def make_pie(df_source, type_filter, group_col, color_seq, title_empty):
        if df_source.empty: return get_empty_fig(title_empty)
        df_f = df_source[(df_source['type'] == type_filter) & (~df_source['category'].isin(EXCLUDED_CATS)) & (df_source['amount'] > 0)]
        if df_f.empty: return get_empty_fig(title_empty)
        df_g = df_f.groupby(group_col)['amount'].sum().reset_index().sort_values(by='amount', ascending=False)
        
        fig = px.pie(df_g, names=group_col, values='amount', hole=0.5, color_discrete_sequence=color_seq)
        fig.update_layout(
            template="plotly_dark", 
            plot_bgcolor="rgba(0,0,0,0)", 
            paper_bgcolor="rgba(0,0,0,0)", 
            margin=dict(t=20, b=20, l=20, r=20), 
            legend=dict(orientation="h", y=-0.1, font=dict(color="white")), 
            font=dict(color="white"),
            hoverlabel=HOVER_STYLE 
        )
        fig.update_traces(textposition='inside', textinfo='percent+label', textfont_size=11)
        return fig

    fig_inc_cat = make_pie(df_trans, 'Income', 'category', px.colors.qualitative.Pastel, "Sin Ingresos")
    fig_inc_sub = make_pie(df_trans, 'Income', 'subcategory', px.colors.qualitative.Pastel, "Sin Subcategorías")
    fig_exp_cat = make_pie(df_trans, 'Expense', 'category', px.colors.qualitative.Set3, "Sin Gastos")
    fig_exp_sub = make_pie(df_trans, 'Expense', 'subcategory', px.colors.qualitative.Set3, "Sin Subcategorías")

    # 4. PASAR UID A MONTHLY SUMMARY
    df_summary = dm.get_monthly_summary(uid) # <--- AQUÍ
    
    if df_summary.empty: fig_cash = get_empty_fig("Sin datos")
    else:
        fig_cash = px.bar(df_summary, x="Month", y="amount", color="type", barmode="group", color_discrete_map={"Income": "#00C851", "Expense": "#ff4444"})
        fig_cash.update_layout(
            template="plotly_dark", 
            plot_bgcolor="rgba(0,0,0,0)", 
            paper_bgcolor="rgba(0,0,0,0)", 
            legend_orientation="h", legend_y=1.02, 
            font=dict(color="white"),
            hoverlabel=HOVER_STYLE
        )

    return (nw_str, nw_class, assets_str, liquid_str, investments_display, recv_str, 
            liab_str, credit_display, pay_str, 
            income_str, label_month, expense_str, label_month, 
            savings_str, savings_bar, 
            fig_cash,
            fig_inc_cat, fig_inc_sub, fig_exp_cat, fig_exp_sub,
            update_label)
# ------------------------------------------------------------------------------
# 5. CALLBACK DINÁMICO (SOLO PARA GRÁFICO HISTÓRICO)
# ------------------------------------------------------------------------------
# --- EN pages/dashboard.py ---

@callback(
    Output("graph-networth-history", "figure"),
    [Input("url", "pathname"),
     Input("dashboard-update-signal", "data"),
     Input("nw-date-picker", "start_date"), 
     Input("nw-date-picker", "end_date")]
)
def update_history_chart_only(pathname, signal, start_date, end_date):
    if pathname != "/": return no_update
    if not end_date: end_date = date.today()
    if not start_date: start_date = date(date.today().year, 1, 1)

    df_history = dm.get_historical_networth_trend(str(start_date), str(end_date))
    fig_nw = go.Figure()
    
    if df_history.empty:
        fig_nw.update_layout(title="Sin datos históricos", template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
    else:
        # --- SUAVIZADO VISUAL (Anti-Tetris) ---
        # Mantenemos solo los puntos donde hubo un cambio real de dinero,
        # más el primer y último punto para que la línea cubra todo el rango.
        # Esto restaura las líneas diagonales en lugar de escalones cuadrados.
        mask = (df_history['net_change'] != 0) | \
               (df_history.index == df_history.index[0]) | \
               (df_history.index == df_history.index[-1])
               
        df_graph = df_history[mask].copy()
        
        # Opcional: Si quieres líneas curvas en vez de rectas, cambia line_shape='spline'
        # Pero 'linear' es lo que tenías antes (diagonales rectas).
        
        # 1. Barras de variación (Usamos df_history completo para que se vean todos los días relevantes si quisieras, 
        # pero df_graph es más limpio)
        fig_nw.add_trace(go.Bar(
            x=df_graph['date'], 
            y=df_graph['net_change'].apply(lambda x: x if x >= 0 else None), 
            name='Var. Positiva', 
            marker=dict(color='#00C851'), 
            opacity=0.2, 
            yaxis='y2'
        ))
        fig_nw.add_trace(go.Bar(
            x=df_graph['date'], 
            y=df_graph['net_change'].apply(lambda x: abs(x) if x < 0 else None), 
            name='Var. Negativa', 
            marker=dict(color='#ff4444'), 
            opacity=0.5, 
            yaxis='y2'
        ))

        # 2. Línea de Patrimonio (Usamos df_graph limpio)
        fig_nw.add_trace(go.Scatter(
            x=df_graph['date'], 
            y=df_graph['net_worth'], 
            name='Patrimonio', 
            mode='lines', # +markers si quieres ver los puntos
            line=dict(
                color='#33b5e5', 
                width=3,
                shape='linear' # Cambia a 'spline' si quieres curvas suaves
            )
        ))
        
        fig_nw.update_layout(
            template="plotly_dark",
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            margin=dict(l=40, r=40, t=30, b=40),
            hovermode="x unified", 
            legend=dict(orientation="h", y=1.1, font=dict(color="white")),
            xaxis=dict(showgrid=False, gridcolor='rgba(255, 255, 255, 0.1)', range=[str(start_date), str(end_date)]),
            yaxis=dict(title="Patrimonio", showgrid=True, gridcolor='rgba(255, 255, 255, 0.1)', zeroline=False, side="left"),
            yaxis2=dict(title="Variación", overlaying="y", side="right", showgrid=False, zeroline=False, rangemode="tozero"),
            font=dict(family="sans-serif", size=12, color="#e0e0e0"),
            hoverlabel=HOVER_STYLE
        )
        
    return fig_nw