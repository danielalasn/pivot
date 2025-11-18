import dash
from dash import dcc, html
import plotly.graph_objects as go
import dash_bootstrap_components as dbc

# ------------------------------------------------------------------------------
# Lógica y Datos (simulados por ahora)
# ------------------------------------------------------------------------------

# Crear figura placeholder para Income vs. Expenses
fig_income_expense = go.Figure(
    go.Bar(x=["Enero", "Febrero", "Marzo"], y=[2200, 2500, 2100], name="Ingresos", marker_color="#00A6FF"),
)
fig_income_expense.add_trace(
    go.Bar(x=["Enero", "Febrero", "Marzo"], y=[1800, 2000, 2050], name="Egresos", marker_color="#FF4B4B")
)
fig_income_expense.update_layout(
    template="plotly_dark",
    barmode='group',
    plot_bgcolor="rgba(0,0,0,0)",
    paper_bgcolor="rgba(0,0,0,0)",
    legend_orientation="h",
    legend_x=0.5,
    legend_xanchor="center",
    legend_y=-0.2
)

# Crear figura placeholder para Distribución de Gastos
fig_spending = go.Figure(
    go.Pie(
        labels=["Costos Fijos", "Guilt Free", "Investments", "Savings"],
        values=[45, 25, 15, 15],
        hole=.4,
        marker_colors=["#FF4B4B", "#FFAA00", "#00A6FF", "#28C76F"]
    )
)
fig_spending.update_layout(
    template="plotly_dark",
    plot_bgcolor="rgba(0,0,0,0)",
    paper_bgcolor="rgba(0,0,0,0)",
    legend_orientation="h",
    legend_x=0.5,
    legend_xanchor="center",
    legend_y=-0.2
)


# ------------------------------------------------------------------------------
# Componentes del Dashboard (Tarjetas de Métricas)
# ------------------------------------------------------------------------------

# Tarjeta de Net Worth
net_worth_card = dbc.Card(
    dbc.CardBody([
        html.H4("Patrimonio Neto", className="card-title"),
        html.H1("$120,450.78", className="card-value text-success"),
        html.P("vs. mes anterior +$1,200 (1.1%)", className="card-text-sm")
    ]),
    className="metric-card"
)

# Tarjeta de Rendimiento Hoy
invest_today_card = dbc.Card(
    dbc.CardBody([
        html.H4("Inversiones (Hoy)", className="card-title"),
        html.H1("+$250.10 (1.08%)", className="card-value text-success"),
        html.P("Última actualización: 16:00 ET", className="card-text-sm")
    ]),
    className="metric-card"
)

# Resumen de Metas
goals_summary = dbc.Card(
    dbc.CardBody([
        html.H4("Progreso de Metas", className="card-title mb-3"),
        
        # Meta 1
        html.Div([
            html.Div("Fondo de Emergencia", className="goal-label"),
            dbc.Progress(value=80, color="success", striped=True, className="goal-progress"),
        ], className="mb-2"),

        # Meta 2
        html.Div([
            html.Div("Viaje a Japón", className="goal-label"),
            dbc.Progress(value=45, color="warning", striped=True, className="goal-progress"),
        ]),

    ]),
    className="data-card"
)


# ------------------------------------------------------------------------------
# Layout de la Página del Dashboard
# ------------------------------------------------------------------------------
layout = dbc.Container(
    [
        # Fila de Título
        dbc.Row([
            dbc.Col(html.H1("Dashboard Principal"), width=12, className="mb-4")
        ]),

        # Fila de Métricas Clave (KPIs)
        dbc.Row([
            dbc.Col(net_worth_card, lg=4, md=6, sm=12, className="mb-4"),
            dbc.Col(invest_today_card, lg=4, md=6, sm=12, className="mb-4"),
            dbc.Col(goals_summary, lg=4, md=12, sm=12, className="mb-4"),
        ]),

        # Fila de Gráficos Principales
        dbc.Row([
            # Gráfico Income vs. Expenses
            dbc.Col(
                dbc.Card(
                    dbc.CardBody([
                        html.H4("Income vs. Expenses", className="card-title"),
                        dcc.Graph(figure=fig_income_expense, config={'displayModeBar': False})
                    ]),
                    className="data-card"
                ),
                lg=8, md=12, sm=12, className="mb-4"
            ),

            # Gráfico Distribución de Gastos
            dbc.Col(
                dbc.Card(
                    dbc.CardBody([
                        html.H4("Distribución de Gastos", className="card-title"),
                        dcc.Graph(figure=fig_spending, config={'displayModeBar': False})
                    ]),
                    className="data-card"
                ),
                lg=4, md=12, sm=12, className="mb-4"
            )
        ]),
        
        # Fila de Top Movers (Placeholder)
        dbc.Row([
            dbc.Col(
                dbc.Card(
                    dbc.CardBody([
                        html.H4("Top Movers (Inversiones)", className="card-title"),
                        # Aquí irían las dos columnas (Positivo/Negativo)
                        html.P("Contenido de Top Movers en construcción.")
                    ]),
                    className="data-card"
                ),
                width=12, className="mb-4"
            )
        ])
    ],
    fluid=True, # Hace que el contenedor ocupe todo el ancho
    className="page-container"
)