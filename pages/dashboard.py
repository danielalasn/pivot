# pages/dashboard.py
import dash
from dash import dcc, html, callback, Input, Output, ctx
import plotly.graph_objects as go
import plotly.express as px
import dash_bootstrap_components as dbc
import backend.data_manager as dm
import pandas as pd
from datetime import date

# ------------------------------------------------------------------------------
# LAYOUT DEL DASHBOARD
# ------------------------------------------------------------------------------
layout = dbc.Container(
    [
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
                        html.Small(id="last-updated-dash-label", className="text-muted ms-2 small fst-italic")
                    ], className="d-flex align-items-center")
                ]
            )
        ], width="auto", className="d-flex align-items-center ms-auto"),
    ], className="mb-4 align-items-center"),

        # --- FILA 1: KPIs PRINCIPALES (Patrimonio, Activos, Pasivos) ---
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
            
            # 2. ACTIVOS (CON FLASH DE INVERSIONES)
            dbc.Col(
                dbc.Card(
                    dbc.CardBody([
                        html.H5("🟢 Lo que tienes (Activos)", className="card-title text-success"),
                        html.H3(id="nw-assets-total", className="card-value text-success mb-3"),
                        
                        dbc.Row([
                            dbc.Col("Bancos/Efectivo:", className="text-muted"),
                            dbc.Col(id="nw-assets-liquid", className="text-end fw-bold")
                        ], className="mb-1"),
                        
                        # Inversiones con Flash Diario
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
            
            # 3. PASIVOS (CON SALUD DE CRÉDITO)
            dbc.Col(
                dbc.Card(
                    dbc.CardBody([
                        html.H5("🔴 Lo que debes (Pasivos)", className="card-title text-danger"),
                        html.H3(id="nw-liabilities-total", className="card-value text-danger mb-3"),
                        
                        # Sección Tarjetas con Barra de Uso
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

        # --- FILA 2: GRÁFICO DE EVOLUCIÓN ---
        dbc.Row([
            dbc.Col(
                dbc.Card(
                    dbc.CardBody([
                        dbc.Row([
                            dbc.Col(html.H5("Evolución Histórica del Patrimonio", className="card-title"), width=7),
                            dbc.Col(
                                dcc.DatePickerRange(
                                    id='nw-date-picker',
                                    display_format='DD/MM/YYYY', 
                                    start_date=None,
                                    end_date=date.today(),
                                    className="float-end",
                                    style={'transform': 'scale(0.85)', 'transformOrigin': 'top right', 'zIndex': 100}
                                ), width=5
                            )
                        ], className="align-items-center mb-3"),
                        
                        dcc.Graph(id="graph-networth-history", config={'displayModeBar': False}, style={'height': '350px'})
                    ]),
                    className="data-card shadow-sm mb-5"
                ),
                width=12
            )
        ]),

        # --- FILA 3: MONITOR DEL MES (KPIs + TASA DE AHORRO) ---
        html.H5("Monitor del Mes Actual", className="text-info mb-3"),
        dbc.Row([
            # Ingresos
            dbc.Col(
                dbc.Card(
                    dbc.CardBody([
                        html.H6("Ingresos Reales", className="card-title text-success"),
                        html.H2(id="kpi-month-income", className="card-value text-success"),
                        html.Small(id="kpi-month-label-inc", className="text-muted")
                    ]),
                    className="metric-card h-100 shadow-sm"
                ),
                lg=4, md=6, sm=12, className="mb-4"
            ),
            # Gastos
            dbc.Col(
                dbc.Card(
                    dbc.CardBody([
                        html.H6("Gastos Reales", className="card-title text-danger"),
                        html.H2(id="kpi-month-expense", className="card-value text-danger"),
                        html.Small(id="kpi-month-label-exp", className="text-muted")
                    ]),
                    className="metric-card h-100 shadow-sm"
                ),
                lg=4, md=6, sm=12, className="mb-4"
            ),
            # TASA DE AHORRO (NUEVO)
            dbc.Col(
                dbc.Card(
                    dbc.CardBody([
                        html.H6("Tasa de Ahorro", className="card-title text-info"),
                        html.H2(id="kpi-savings-rate", className="card-value text-info"),
                        html.Div(id="kpi-savings-bar-container", className="mt-2")
                    ]),
                    className="metric-card h-100 shadow-sm"
                ),
                lg=4, md=12, sm=12, className="mb-4"
            ),
        ]),

        # --- FILA 4: GRÁFICOS INFERIORES ---
        dbc.Row([
            dbc.Col(
                dbc.Card(
                    dbc.CardBody([
                        html.H5("Histórico de Flujo de Caja", className="card-title"),
                        dcc.Graph(id="graph-cashflow", config={'displayModeBar': False}, style={'height': '350px'})
                    ]),
                    className="data-card shadow-sm"
                ),
                lg=8, md=12, sm=12, className="mb-4"
            ),

            dbc.Col(
                dbc.Card(
                    dbc.CardBody([
                        html.H5("Gastos por Categoría", className="card-title"),
                        dcc.Graph(id="graph-categories", config={'displayModeBar': False}, style={'height': '350px'})
                    ]),
                    className="data-card shadow-sm"
                ),
                lg=4, md=12, sm=12, className="mb-4"
            )
        ]),
    ],
    fluid=True,
    className="page-container"
)

# ------------------------------------------------------------------------------
# CALLBACKS
# ------------------------------------------------------------------------------

@callback(
    [Output("nw-total", "children"),
     Output("nw-total", "className"),
     Output("nw-assets-total", "children"),
     Output("nw-assets-liquid", "children"),
     Output("nw-assets-investments-container", "children"), # Contenedor Inversiones
     Output("nw-assets-receivable", "children"),
     Output("nw-liabilities-total", "children"),
     Output("nw-liabilities-credit-container", "children"), # Contenedor Crédito
     Output("nw-liabilities-payable", "children"),
     Output("kpi-month-income", "children"),
     Output("kpi-month-label-inc", "children"),
     Output("kpi-month-expense", "children"),
     Output("kpi-month-label-exp", "children"),
     Output("kpi-savings-rate", "children"),       # Output Tasa Ahorro Texto
     Output("kpi-savings-bar-container", "children"), # Output Barra Ahorro
     Output("graph-cashflow", "figure"),
     Output("graph-categories", "figure"),
     Output("graph-networth-history", "figure"),
     Output("last-updated-dash-label", "children")],
    [Input("url", "pathname"),
     Input("nw-date-picker", "start_date"), 
     Input("nw-date-picker", "end_date"),
     Input("btn-refresh-dashboard", "n_clicks")] 
)
def update_dashboard(pathname, start_date, end_date, n_refresh):
    if pathname != "/":
        return [dash.no_update] * 19

    # --- LÓGICA DE REFRESCO ---
    ctx_id = ctx.triggered_id
    force_refresh = (ctx_id == "btn-refresh-dashboard")

    # --- FECHAS INICIALES ---
    df_trans = dm.get_transactions_df()
    if not end_date: end_date = date.today()
    if not start_date:
        today = date.today()
        jan_first = date(today.year, 1, 1)
        calc_start = jan_first
        if not df_trans.empty:
            first_data_date = pd.to_datetime(df_trans['date']).dt.date.min()
            if first_data_date > jan_first:
                calc_start = first_data_date
        start_date = calc_start

    # ==============================================================================
    # 1. DATOS DE PATRIMONIO Y MEJORAS DE VISUALIZACIÓN
    # ==============================================================================
    nw_data = dm.get_net_worth_breakdown(force_refresh=force_refresh)
    last_ts = dm.get_data_timestamp()
    update_label = f"Precios: {last_ts}"

    # A) Patrimonio Neto
    net_worth = nw_data['net_worth']
    nw_str = f"${net_worth:,.2f}"
    nw_class = "card-value display-4 fw-bold text-success" if net_worth >= 0 else "card-value display-4 fw-bold text-danger"
    
    # B) Activos Simples
    assets_str = f"${nw_data['assets']['total']:,.2f}"
    liquid_str = f"${nw_data['assets']['liquid']:,.2f}"
    recv_str = f"${nw_data['assets']['receivables']:,.2f}"
    
    # C) MEJORA 1: FLASH DE INVERSIONES (Cálculo Diario)
    # Obtenemos los stocks (usando caché para ser rápido) para calcular cambio diario
    stocks = dm.get_stocks_data(force_refresh=False)
    inv_total = nw_data['assets']['investments']
    
    day_gain_usd = 0.0
    for s in stocks:
        # Calcular ganancia diaria en USD aproximada: ValorHoy - (ValorHoy / (1 + Pct/100))
        if s.get('day_change_pct'):
            val = s['market_value']
            pct = s['day_change_pct']
            if val and pct:
                prev_val = val / (1 + pct/100)
                day_gain_usd += (val - prev_val)

    day_gain_pct = (day_gain_usd / (inv_total - day_gain_usd) * 100) if (inv_total - day_gain_usd) != 0 else 0
    
    # Renderizado Flash Inversiones
    inv_color = "text-success" if day_gain_usd >= 0 else "text-danger"
    inv_sign = "+" if day_gain_usd >= 0 else ""
    
    investments_display = dbc.Row([
        dbc.Col("Inversiones:", className="text-muted"),
        dbc.Col([
            html.Div(f"${inv_total:,.2f}", className="fw-bold text-info"),
            html.Small(f"{inv_sign}${day_gain_usd:,.2f} ({inv_sign}{day_gain_pct:.2f}%) hoy", className=f"d-block small {inv_color} fw-bold")
        ], className="text-end")
    ], className="mb-1 align-items-center")


    # D) Pasivos Simples
    liab_str = f"${nw_data['liabilities']['total']:,.2f}"
    pay_str = f"${nw_data['liabilities']['payables']:,.2f}"

    # E) MEJORA 2: SALUD DE CRÉDITO (Utilización)
    # Obtenemos datos detallados de crédito
    cred_data = dm.get_credit_summary_data()
    total_limit = cred_data['total_limit']
    total_debt = cred_data['total_debt']
    
    # Cálculo de porcentaje usado
    utilization = (total_debt / total_limit * 100) if total_limit > 0 else 0
    available_pct = 100 - utilization
    
    # Color del TEXTO de abajo (para mantener la alerta semántica)
    text_color_class = "success" if utilization < 30 else ("warning" if utilization < 50 else "danger")
    
    credit_display = html.Div([
        dbc.Row([
            dbc.Col("Tarjetas Crédito:", className="text-muted"),
            dbc.Col(f"${total_debt:,.2f}", className="text-end fw-bold")
        ], className="mb-1"),
        
        # --- BARRA APILADA (STACKED PROGRESS BAR) ---
        # Rojo (Izquierda): Lo que ya gastaste
        # Verde (Derecha): Lo que te queda disponible
        dbc.Progress([
            dbc.Progress(value=utilization, color="danger", bar=True),
            dbc.Progress(value=available_pct, color="success", bar=True),
        ], style={"height": "10px", "backgroundColor": "#222"}, className="mb-1"),
        # --------------------------------------------
        
        dbc.Row([
            dbc.Col(f"Límite: ${total_limit:,.0f}", className="text-muted small", style={"fontSize": "0.7rem"}),
            dbc.Col(f"Uso: {utilization:.1f}%", className=f"text-end small fw-bold text-{text_color_class}", style={"fontSize": "0.7rem"})
        ])
    ])


    # ==============================================================================
    # 2. GRÁFICO HISTÓRICO PATRIMONIO
    # ==============================================================================
    if not start_date: start_date = date(date.today().year, 1, 1)
    if not end_date: end_date = date.today()

    df_history = dm.get_historical_networth_trend(str(start_date), str(end_date))
    fig_nw = go.Figure()
    
    if df_history.empty:
        fig_nw.update_layout(title="Sin datos históricos", template="plotly_dark")
    else:
        fig_nw.add_trace(go.Bar(
            x=df_history['date'], y=df_history['net_change'], name='Var. Diaria',
            marker_color=df_history['net_change'].apply(lambda x: '#00C851' if x >= 0 else '#ff4444'), opacity=0.4
        ))
        fig_nw.add_trace(go.Scatter(
            x=df_history['date'], y=df_history['net_worth'], name='Patrimonio',
            mode='lines+markers', line=dict(color='#33b5e5', width=3), marker=dict(size=5)
        ))
        fig_nw.update_layout(
            template="plotly_dark", plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            xaxis=dict(showgrid=False), yaxis=dict(showgrid=True, gridcolor="#333"),
            legend=dict(orientation="h", y=1.1), margin=dict(l=40, r=20, t=40, b=40),
            hovermode="x unified"
        )


    # ==============================================================================
    # 3. CÁLCULOS DEL MES Y TASA DE AHORRO
    # ==============================================================================
    today = date.today()
    current_month_name = today.strftime("%B %Y").capitalize()
    
    # Categorías internas a excluir
    EXCLUDED_CATS = ['Transferencia', 'Transferencia/Pago', 'Deudas/Cobros']
    
    month_income = 0.0
    month_expense = 0.0

    if not df_trans.empty:
        df_trans['date_dt'] = pd.to_datetime(df_trans['date'])
        df_curr = df_trans[(df_trans['date_dt'].dt.month == today.month) & (df_trans['date_dt'].dt.year == today.year)]
        
        # Filtro de ingresos reales
        df_inc = df_curr[(df_curr['type'] == 'Income') & (~df_curr['category'].isin(EXCLUDED_CATS))]
        month_income = df_inc['amount'].sum()
        
        # Filtro de gastos reales
        df_exp = df_curr[(df_curr['type'] == 'Expense') & (~df_curr['category'].isin(EXCLUDED_CATS))]
        month_expense = df_exp['amount'].sum()

    income_str = f"${month_income:,.2f}"
    expense_str = f"${month_expense:,.2f}"
    label_month = f"Total en {current_month_name}"

    # F) MEJORA 3: TASA DE AHORRO (Cálculo y Visualización)
    savings = month_income - month_expense
    savings_rate = (savings / month_income * 100) if month_income > 0 else 0
    
    savings_str = f"{savings_rate:.1f}%"
    
    # Color y mensaje según la tasa
    if savings_rate <= 0:
        sav_color = "danger"
        sav_msg = "Gastas más de lo que ingresas"
    elif savings_rate < 10:
        sav_color = "warning"
        sav_msg = "Margen ajustado"
    elif savings_rate < 30:
        sav_color = "info"
        sav_msg = "Buen ritmo"
    else:
        sav_color = "success"
        sav_msg = "¡Excelente ahorro!"

    # Componente visual (Barra con labels)
    savings_bar = html.Div([
        dbc.Progress(value=max(0, savings_rate), color=sav_color, striped=True, animated=True, className="mb-2", style={"height": "15px"}),
        html.Div([
            html.Small(f"Ahorro Neto: ${savings:,.2f}", className=f"text-{sav_color} fw-bold"),
            html.Small(sav_msg, className="text-muted fst-italic")
        ], className="d-flex justify-content-between")
    ])


    # ==============================================================================
    # 4. GRÁFICOS INFERIORES
    # ==============================================================================
    df_summary = dm.get_monthly_summary()
    if df_summary.empty:
        fig_cash = go.Figure().update_layout(template="plotly_dark", title="Sin datos")
    else:
        fig_cash = px.bar(df_summary, x="Month", y="amount", color="type", barmode="group",
                          color_discrete_map={"Income": "#00C851", "Expense": "#ff4444"})
        fig_cash.update_layout(template="plotly_dark", plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", legend_orientation="h", legend_y=1.02)

    df_cats = dm.get_category_summary()
    if not df_cats.empty:
        # Filtro extra para el gráfico
        df_cats = df_cats[~df_cats['category'].isin(EXCLUDED_CATS)]
        
    if df_cats.empty:
        fig_pie = go.Figure().update_layout(template="plotly_dark", title="Sin gastos")
    else:
        fig_pie = px.pie(df_cats, names="category", values="amount", hole=0.5, color_discrete_sequence=px.colors.qualitative.Pastel)
        fig_pie.update_layout(template="plotly_dark", plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", legend_orientation="h", legend_y=-0.1)

    return (nw_str, nw_class, assets_str, liquid_str, investments_display, recv_str, 
            liab_str, credit_display, pay_str, 
            income_str, label_month, expense_str, label_month, 
            savings_str, savings_bar, 
            fig_cash, fig_pie, fig_nw, update_label)