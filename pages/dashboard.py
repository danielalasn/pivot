# pages/dashboard.py
import dash
from dash import dcc, html, callback, Input, Output
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
        # Título
        dbc.Row([
            dbc.Col(html.H2("Resumen Financiero Global", className="mb-4"), width=12)
        ]),

        # --- FILA 1: PATRIMONIO (KPIs) ---
        html.H5("Mi Patrimonio", className="text-primary mb-3"),
        dbc.Row([
            # 1. PATRIMONIO NETO (Total)
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
                        dbc.Row([
                            dbc.Col("Tarjetas Crédito:", className="text-muted"),
                            dbc.Col(id="nw-liabilities-credit", className="text-end fw-bold")
                        ], className="mb-1"),
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

        # --- FILA 1.5: GRÁFICO DE EVOLUCIÓN DE PATRIMONIO CON FILTRO ---
        dbc.Row([
            dbc.Col(
                dbc.Card(
                    dbc.CardBody([
                        # CABECERA: Título y Selector de Fechas
                        dbc.Row([
                            dbc.Col(html.H5("Evolución Histórica del Patrimonio", className="card-title"), width=7),
                            dbc.Col(
                                dcc.DatePickerRange(
                                    id='nw-date-picker',
                                    display_format='DD/MM/YYYY', # Formato más compacto
                                    # FECHAS POR DEFECTO: Inicio de Año -> Hoy
                                    start_date=None,
                                    end_date=date.today(),
                                    className="float-end",
                                    # ESTILO PARA HACERLO MÁS PEQUEÑO
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

        # --- FILA 2: MONITOR MENSUAL (KPIs) ---
        html.H5("Monitor del Mes Actual", className="text-info mb-3"),
        dbc.Row([
            # Ingresos Mes
            dbc.Col(
                dbc.Card(
                    dbc.CardBody([
                        html.H6("Ingresos", className="card-title text-success"),
                        html.H2(id="kpi-month-income", className="card-value text-success"),
                        html.Small(id="kpi-month-label-inc", className="text-muted")
                    ]),
                    className="metric-card h-100 shadow-sm"
                ),
                lg=6, md=6, sm=12, className="mb-4"
            ),
            # Gastos Mes
            dbc.Col(
                dbc.Card(
                    dbc.CardBody([
                        html.H6("Gastos", className="card-title text-danger"),
                        html.H2(id="kpi-month-expense", className="card-value text-danger"),
                        html.Small(id="kpi-month-label-exp", className="text-muted")
                    ]),
                    className="metric-card h-100 shadow-sm"
                ),
                lg=6, md=6, sm=12, className="mb-4"
            ),
        ]),

        # --- FILA 3: GRÁFICOS INFERIORES ---
        dbc.Row([
            # Gráfico Histórico
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

            # Gráfico Categorías
            dbc.Col(
                dbc.Card(
                    dbc.CardBody([
                        html.H5("Gastos por Categoría (Histórico)", className="card-title"),
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
     Output("nw-assets-receivable", "children"),
     Output("nw-liabilities-total", "children"),
     Output("nw-liabilities-credit", "children"),
     Output("nw-liabilities-payable", "children"),
     Output("kpi-month-income", "children"),
     Output("kpi-month-label-inc", "children"),
     Output("kpi-month-expense", "children"),
     Output("kpi-month-label-exp", "children"),
     Output("graph-cashflow", "figure"),
     Output("graph-categories", "figure"),
     Output("graph-networth-history", "figure")],
    [Input("url", "pathname"),
     Input("nw-date-picker", "start_date"), 
     Input("nw-date-picker", "end_date")]   
)
def update_dashboard(pathname, start_date, end_date):
    if pathname != "/":
        return [dash.no_update] * 15

    # --- LÓGICA DE FECHAS DINÁMICA ---
    # Cargamos transacciones aquí porque las necesitamos para validar la fecha
    df_trans = dm.get_transactions_df()
    
    if not end_date: 
        end_date = date.today()

    if not start_date:
        today = date.today()
        jan_first = date(today.year, 1, 1)
        
        # Por defecto asumimos el 1 de Enero
        calc_start = jan_first
        
        if not df_trans.empty:
            # Obtenemos la fecha de la primera transacción registrada
            first_data_date = pd.to_datetime(df_trans['date']).dt.date.min()
            
            # TU CONDICIÓN:
            # "Si el primer dato es despues del primer dia del año, el start date sera la primera fecha"
            if first_data_date > jan_first:
                calc_start = first_data_date
            # "Si no (es antes o igual), pues el primer dia del año" (se mantiene jan_first)
            
        start_date = calc_start


    # 1. DATOS DE PATRIMONIO
    nw_data = dm.get_net_worth_breakdown()

    # 1. DATOS DE PATRIMONIO
    nw_data = dm.get_net_worth_breakdown()
    net_worth = nw_data['net_worth']
    
    # Formateo Strings
    nw_str = f"${net_worth:,.2f}"
    nw_class = "card-value display-4 fw-bold text-success" if net_worth >= 0 else "card-value display-4 fw-bold text-danger"
    
    assets_str = f"${nw_data['assets']['total']:,.2f}"
    liquid_str = f"${nw_data['assets']['liquid']:,.2f}"
    recv_str = f"${nw_data['assets']['receivables']:,.2f}"
    
    liab_str = f"${nw_data['liabilities']['total']:,.2f}"
    credit_str = f"${nw_data['liabilities']['credit_cards']:,.2f}"
    pay_str = f"${nw_data['liabilities']['payables']:,.2f}"


    # 2. GRÁFICO COMBO: EVOLUCIÓN DIARIA (CON FILTRO)
    # Si no hay fechas seleccionadas (al inicio antes de cargar), poner defaults
    if not start_date: start_date = date(date.today().year, 1, 1)
    if not end_date: end_date = date.today()

    df_history = dm.get_historical_networth_trend(str(start_date), str(end_date))
    
    fig_nw = go.Figure()
    
    if df_history.empty:
        fig_nw.update_layout(title="Sin datos históricos suficientes", template="plotly_dark")
    else:
        # Barra: Cambio Diario
        fig_nw.add_trace(go.Bar(
            x=df_history['date'], 
            y=df_history['net_change'],
            name='Variación Diaria',
            marker_color=df_history['net_change'].apply(lambda x: '#00C851' if x >= 0 else '#ff4444'),
            opacity=0.4
        ))

        # Línea: Patrimonio Total
        fig_nw.add_trace(go.Scatter(
            x=df_history['date'], 
            y=df_history['net_worth'],
            name='Patrimonio Neto',
            mode='lines+markers', 
            line=dict(color='#33b5e5', width=3),
            marker=dict(size=5)
        ))
        
        fig_nw.update_layout(
            template="plotly_dark",
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            xaxis=dict(showgrid=False, title=None),
            yaxis=dict(showgrid=True, gridcolor="#333"),
            legend=dict(orientation="h", y=1.1),
            margin=dict(l=40, r=20, t=40, b=40),
            hovermode="x unified",
            hoverlabel=dict(bgcolor="#333333", font_size=13, font_color="white")
        )


    # 3. CÁLCULOS DEL MES ACTUAL
    df_trans = dm.get_transactions_df()
    today = date.today()
    current_month_name = today.strftime("%B %Y").capitalize()
    month_income = 0.0
    month_expense = 0.0

    if not df_trans.empty:
        df_trans['date_dt'] = pd.to_datetime(df_trans['date'])
        df_current = df_trans[(df_trans['date_dt'].dt.month == today.month) & (df_trans['date_dt'].dt.year == today.year)]
        month_income = df_current[df_current['type'] == 'Income']['amount'].sum()
        month_expense = df_current[df_current['type'] == 'Expense']['amount'].sum()

    income_str = f"${month_income:,.2f}"
    expense_str = f"${month_expense:,.2f}"
    label_month = f"Total en {current_month_name}"


    # 4. GRÁFICOS INFERIORES
    df_summary = dm.get_monthly_summary()
    if df_summary.empty:
        fig_cashflow = go.Figure().update_layout(template="plotly_dark", title="Sin datos", xaxis={"visible": False}, yaxis={"visible": False})
    else:
        fig_cashflow = px.bar(
            df_summary, x="Month", y="amount", color="type", barmode="group",
            color_discrete_map={"Income": "#00C851", "Expense": "#ff4444"},
            labels={"amount": "Monto", "Month": "Mes", "type": "Tipo"}
        )
        fig_cashflow.update_layout(template="plotly_dark", plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", legend_orientation="h", legend_y=1.02)

    df_cats = dm.get_category_summary()
    if df_cats.empty:
        fig_pie = go.Figure().update_layout(template="plotly_dark", title="Sin gastos", xaxis={"visible": False}, yaxis={"visible": False})
    else:
        fig_pie = px.pie(df_cats, names="category", values="amount", hole=0.5, color_discrete_sequence=px.colors.qualitative.Pastel)
        fig_pie.update_layout(template="plotly_dark", plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", legend_orientation="h", legend_y=-0.1)

    return (nw_str, nw_class, assets_str, liquid_str, recv_str, 
            liab_str, credit_str, pay_str, 
            income_str, label_month, expense_str, label_month, 
            fig_cashflow, fig_pie, fig_nw)