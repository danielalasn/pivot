# pages/investments/investments_sales_analysis.py

import dash
from dash import dcc, html, callback, Input, Output, State, no_update, ctx
import dash_bootstrap_components as dbc
import backend.data_manager as dm
from dash import dash_table
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import json 
from utils import ui_helpers 
from io import StringIO

# --- FUNCIONES AUXILIARES ---

def create_empty_bar(title, height=350):
    """Genera una figura vacía con un mensaje central."""
    fig = go.Figure().update_layout(template="plotly_dark")
    fig.update_layout(
        title=title, 
        plot_bgcolor="rgba(0,0,0,0)", 
        paper_bgcolor="rgba(0,0,0,0)", 
        font={"color": "gray"},
        xaxis={"visible": False}, 
        yaxis={"visible": False},
        annotations=[{
            'text': "Sin datos para mostrar",
            'xref': 'paper', 'yref': 'paper',
            'showarrow': False,
            'font': {'size': 16, 'color': 'gray'}
        }],
        height=height
    )
    return fig


# --- MODAL 1: AGREGAR AJUSTE DE P/L ---
realized_pl_modal = dbc.Modal([
    dbc.ModalHeader(dbc.ModalTitle("Añadir Ajuste P/L Histórico")),
    dbc.ModalBody([
        html.P("Introduce ganancias/pérdidas realizadas antes de usar Pivot.", className="text-muted small"),
        dbc.Label("Ticker Symbol"),
        dbc.Input(id="pl-adj-ticker", placeholder="Ej: AAPL", type="text", className="mb-3"),
        
        dbc.Label("Ganancia o Pérdida Realizada ($)"),
        html.Small("Usa signo negativo (-) para indicar pérdida.", className="text-warning d-block mb-2"),
        dbc.Input(id="pl-adj-amount", placeholder="0.00 (ej: -50.50 para pérdida)", type="number", className="mb-3"),
        
        html.Div(id="pl-adj-msg", className="mt-2 text-center")
    ]),
    dbc.ModalFooter([
        dbc.Button("Cancelar", id="btn-pl-adj-cancel", outline=True),
        dbc.Button("Guardar Ajuste", id="btn-pl-adj-save", color="success", className="ms-2"),
    ])
], id="realized-pl-modal", is_open=False, centered=True, size="sm")


# --- MODAL 2: EDICIÓN DE AJUSTE P/L ---
edit_adj_store = dcc.Store(id='edit-adj-id', data=None)

pl_adj_edit_modal = dbc.Modal([
    dbc.ModalHeader(dbc.ModalTitle(id="pl-adj-edit-title")),
    dbc.ModalBody([
        html.P("Corrige el valor de la ganancia/pérdida realizada históricamente.", className="text-muted small"),
        dbc.Label("Ticker Symbol"),
        dbc.Input(id="pl-adj-edit-ticker", type="text", disabled=True, className="mb-3"),
        
        dbc.Label("Ganancia o Pérdida Realizada ($)"),
        dbc.Input(id="pl-adj-edit-amount", type="number", className="mb-3"),
        
        html.Div(id="pl-adj-edit-msg", className="mt-2 text-center")
    ]),
    dbc.ModalFooter([
        dbc.Button("Cancelar", id="btn-pl-adj-edit-cancel", outline=True),
        dbc.Button("Guardar Corrección", id="btn-pl-adj-edit-save", color="info", className="ms-2"),
    ])
], id="pl-adj-edit-modal", is_open=False, centered=True, size="sm")


# --- LAYOUT PRINCIPAL (Contenido de la nueva pestaña de "Análisis P/L") ---

layout = dbc.Container([
    
    # Botón de Ajuste Histórico (Alineado a la derecha)
    dbc.Row(
        [
            dbc.Col(
                html.H4("Análisis P/L (Ventas)", className="text-info mb-3"), 
                width=True 
            ),
            
            dbc.Col(
                dbc.Button(
                    "Añadir Ajuste P/L Histórico", 
                    id="btn-open-pl-adj-modal", 
                    color="warning", 
                    outline=True, 
                    size="sm", 
                    className="mb-3"
                ),
                width="auto", 
                className="d-flex align-items-end" 
            ),
        ], 
        className="mb-3 g-0 align-items-end" 
    ),
    
    realized_pl_modal, 
    pl_adj_edit_modal,
    edit_adj_store,
    
    # 1. RESUMEN GLOBAL DE VENTAS REALIZADAS (KPI + GRÁFICO BARRA)
    html.H5("Rendimiento de Ventas Realizadas", className="text-info mb-3"),
    dbc.Row([
        
        # 1A. KPI: P/L Total Realizado
        dbc.Col(
            dbc.Card(
                dbc.CardBody([
                    html.H5("Ganancia Realizada Total", className="card-title text-info"),
                    html.H2(id="kpi-total-realized-pl", className="card-value fw-bold mb-2 text-white"),
                    # html.Small("P/L de todas las ventas cerradas.", className="text-muted small")
                ]),
                className="metric-card h-100 shadow-sm"
            ),
            lg=4, md=12, className="mb-4"
        ),

        # 1B. GRÁFICO: P/L por Ticker
        dbc.Col(
            dbc.Card(dbc.CardBody([
                html.H5("P/L Realizado por Ticker Vendido", className="card-title text-muted"),
                dcc.Graph(
                    id="realized-pl-bar-chart", 
                    config={'displayModeBar': False}, 
                    style={'height': '350px'},
                    figure=create_empty_bar("Cargando datos...") 
                )
            ]), className="data-card h-100"), 
            lg=8, md=12, className="mb-4"
        ),
        
    ], className="g-4"),
    
    # 2. PIVOT TABLE: P/L ACUMULADO (VIVOS + VENDIDOS)
    html.H4("Análisis Acumulado Ticker por Ticker", className="mb-3 mt-4 text-info"),
    html.P("Combina las ganancias realizadas (ventas + ajustes) con las ganancias abiertas (activos vivos).", className="text-muted"),
    dbc.Card(dbc.CardBody(id="pivot-pl-container", children=dbc.Spinner(size="lg", color="info", type="grow")), className="data-card mb-4"),
    
], fluid=True)


# ==============================================================================
# CALLBACKS DE CONTROL DEL MODAL DE AJUSTE
# ==============================================================================

# 0. Toggle Modal de Ajuste
@callback(
    Output("realized-pl-modal", "is_open"),
    [Input("btn-open-pl-adj-modal", "n_clicks"), 
     Input("btn-pl-adj-cancel", "n_clicks"),
     Input("btn-pl-adj-save", "n_clicks")],
    State("realized-pl-modal", "is_open"),
    prevent_initial_call=True
)
def toggle_pl_adj_modal(open_n, cancel_n, save_n, is_open):
    if ctx.triggered_id in ["btn-pl-adj-cancel", "btn-pl-adj-save"]:
        return False
    return not is_open

# 1. Guardar Ajuste
@callback(
    [Output("pl-adj-msg", "children"),
     Output("sales-history-cache", "data", allow_duplicate=True), 
     Output("pl-adj-ticker", "value"),          
     Output("pl-adj-amount", "value")],         
    Input("btn-pl-adj-save", "n_clicks"),
    [State("pl-adj-ticker", "value"),
     State("pl-adj-amount", "value")],
    prevent_initial_call=True
)
def save_pl_adjustment(n_clicks, ticker, amount):
    if not all([ticker, amount]):
        return html.Span("Faltan campos obligatorios.", className="text-danger"), no_update, no_update, no_update
        
    try:
        amount_f = float(amount)
    except ValueError:
        return html.Span("Monto de P/L inválido.", className="text-danger"), no_update, no_update, no_update

    # 1. Guardar en la base de datos
    success, msg = dm.add_realized_pl_adjustment(ticker, amount_f)
    
    if success:
        # 2. Forzamos la recarga del historial (Caché)
        df = dm.get_investment_transactions_df() 
        df['realized_pl'] = pd.to_numeric(df['realized_pl'], errors='coerce')
        new_cache = df.to_json(date_format='iso', orient='split')
        
        # 3. Retornamos éxito, el nuevo caché y LIMPIAMOS los campos de entrada
        return html.Span("Ajuste registrado con éxito. Recargando análisis.", className="text-success"), new_cache, None, None
    else:
        return html.Span(msg, className="text-danger"), no_update, no_update, no_update

# ==============================================================================
# CALLBACKS DE EDICIÓN DE AJUSTES MANUALES
# ==============================================================================

# 4. Abrir Modal de Edición al hacer click en la celda P/L Realizado
@callback(
    [Output("pl-adj-edit-modal", "is_open"),
     Output("pl-adj-edit-title", "children"),
     Output("pl-adj-edit-ticker", "value"),
     Output("pl-adj-edit-amount", "value"),
     Output("edit-adj-id", "data")],
    [Input("pl-pivot-table", "active_cell"),
     Input("btn-pl-adj-edit-cancel", "n_clicks"),
     Input("btn-pl-adj-edit-save", "n_clicks")],
    [State("pl-pivot-table", "data")],
    prevent_initial_call=True
)
def handle_adj_edit_modal(active_cell, cancel_n, save_n, table_data):
    trig = ctx.triggered_id
    
    if trig in ["btn-pl-adj-edit-cancel", "btn-pl-adj-edit-save"]:
        return False, no_update, no_update, no_update, None 
        
    if trig == "pl-pivot-table" and active_cell:
        col_id = active_cell['column_id']
        row_index = active_cell['row']
        
        # 🚨 CORRECCIÓN: El ID de la columna usada para merge es 'P/L Realizado'
        # La edición solo debe ocurrir si el clic es en esa columna
        if col_id == 'P/L Realizado': 
            ticker = table_data[row_index]['ticker']
            
            # Buscar el ID del ajuste manual en la DB (usando dm.get_adjustment_id_by_ticker)
            adjustment_id, realized_pl = dm.get_adjustment_id_by_ticker(ticker)
            
            if adjustment_id is not None:
                # Precargar los datos y abrir el modal
                return True, f"Editar Ajuste P/L para {ticker}", ticker, realized_pl, adjustment_id
            else:
                # Si es P/L Realizado por ventas del sistema, no permitimos editar aquí
                return no_update, no_update, no_update, no_update, None
    
    return no_update, no_update, no_update, no_update, no_update


# 5. Guardar Edición del Ajuste
@callback(
    [Output("pl-adj-edit-msg", "children"),
     Output("sales-history-cache", "data", allow_duplicate=True), 
     Output("pl-adj-edit-modal", "is_open", allow_duplicate=True)],
    Input("btn-pl-adj-edit-save", "n_clicks"),
    [State("pl-adj-edit-amount", "value"),
     State("edit-adj-id", "data")],
    prevent_initial_call=True
)
def save_edited_adjustment(n_clicks, new_amount, adjustment_id):
    if adjustment_id is None:
        return html.Span("Error: No se encontró el ID del ajuste.", className="text-danger"), no_update, no_update
        
    if new_amount is None:
        return html.Span("El monto no puede estar vacío.", className="text-danger"), no_update, no_update
        
    try:
        amount_f = float(new_amount)
    except ValueError:
        return html.Span("Monto de P/L inválido.", className="text-danger"), no_update, no_update

    # Guardar en la base de datos
    success, msg = dm.update_pl_adjustment(adjustment_id, amount_f)
    
    if success:
        # Forzar la recarga del caché de historial y cerrar el modal
        df = dm.get_investment_transactions_df() 
        df['realized_pl'] = pd.to_numeric(df['realized_pl'], errors='coerce')
        new_cache = df.to_json(date_format='iso', orient='split')
        
        return html.Span("Ajuste corregido con éxito. Recargando análisis.", className="text-success"), new_cache, False
    else:
        return html.Span(msg, className="text-danger"), no_update, no_update

# ==============================================================================
# CALLBACKS DE ANÁLISIS (Se mantienen igual)
# ==============================================================================

# 2. Generar KPI y Gráfico de Barras (SOLO VENTAS Y AJUSTES)
# pages/investments/investments_sales_analysis.py

from io import StringIO # Asegúrate de tener esto importado arriba

# pages/investments/investments_sales_analysis.py

# pages/investments/investments_sales_analysis.py

# pages/investments/investments_sales_analysis.py

@callback(
    [Output("kpi-total-realized-pl", "children"),
     Output("realized-pl-bar-chart", "figure")],
    Input("sales-history-cache", "data")
)
def render_realized_pl_summary(json_history):
    # --- 1. PREPARACIÓN DE DATOS (Igual que antes) ---
    df_sales = pd.DataFrame({'ticker': [], 'realized_pl': []})
    
    if json_history and json_history != '{}':
        df_all = pd.read_json(StringIO(json_history), orient='split')
        if not df_all.empty:
            df_sales = df_all[df_all['type'] == 'SELL'][['ticker', 'realized_pl']].copy()

    df_adjustments = dm.get_pl_adjustments_df()
    
    if not df_adjustments.empty:
        df_combined = pd.concat([df_sales, df_adjustments], ignore_index=True)
    else:
        df_combined = df_sales
    
    if df_combined.empty:
        empty_layout = html.Div([
            html.H2("$0.00", className="fw-bold mb-2 text-white"),
            html.Small("Sin operaciones cerradas aún.", className="text-muted")
        ])
        return empty_layout, create_empty_bar("Sin datos de ventas.")

    # --- 2. CÁLCULOS ---
    total_pl = df_combined['realized_pl'].sum()
    gross_gain = df_combined[df_combined['realized_pl'] > 0]['realized_pl'].sum()
    gross_loss = df_combined[df_combined['realized_pl'] < 0]['realized_pl'].sum()
    
    win_count = len(df_combined[df_combined['realized_pl'] > 0])
    loss_count = len(df_combined[df_combined['realized_pl'] <= 0])
    total_trades = win_count + loss_count
    
    win_rate = (win_count / total_trades * 100) if total_trades > 0 else 0
    loss_rate = 100 - win_rate

    # --- 3. LAYOUT FINAL (Diseño Solicitado) ---
    main_color = "text-success" if total_pl >= 0 else "text-danger"
    
    kpi_content = html.Div([
    # 1. TÍTULO Y MONTO TOTAL (El Héroe)
    html.H2(f"${total_pl:,.2f}", className=f"fw-bold mb-0 {main_color}"),
    html.P("P/L de todas las ventas cerradas.", className="text-muted", style={"fontSize": "11px", "marginTop": "2px"}),
    
    # Separador sutil
    html.Hr(className="my-2", style={"borderColor": "#e0e0e0", "opacity": "0.2"}),

    # 2. GANANCIA Y PÉRDIDA (Muy pequeño y explicativo)
    html.Div([
        # Fila Ganancia
        html.Div([
            html.Span("Ganancias brutas", className="text-muted"),
            html.Span(f"+${gross_gain:,.2f}", className="text-success fw-bold")
        ], className="d-flex justify-content-between mb-1"),
        
        # Fila Pérdida
        html.Div([
            html.Span("Pérdidas brutas", className="text-muted"),
            html.Span(f"${gross_loss:,.2f}", className="text-danger fw-bold")
        ], className="d-flex justify-content-between")
    ], className="mb-3", style={"fontSize": "0.8rem"}), # Tamaño muy reducido (letra chica)

    # 3. BARRA DE WIN RATE
    html.Div([
        # Título y Porcentaje
        html.Div([
            html.Span("Win Rate", className="text-white fw-bold", style={"fontSize": "0.85rem"}),
            html.Span(f"{win_rate:.1f}%", className=f"fw-bold {'text-success' if win_rate >= 50 else 'text-danger'}", style={"fontSize": "0.9rem"})
        ], className="d-flex justify-content-between mb-1"),

        # Barra
        dbc.Progress([
            dbc.Progress(value=win_rate, color="success", className="bg-success", bar=True),
            dbc.Progress(value=loss_rate, color="danger", className="bg-danger", bar=True),
        ], style={"height": "6px", "backgroundColor": "#2c2c2c"}, className="mb-1 rounded-pill overflow-hidden"),

        # 4. PIE DE BARRA (Wins Izquierda - Losses Derecha)
        html.Div([
            html.Span(f"{win_count} Wins", className="text-success fw-bold"),  # Pegado a la izquierda
            html.Span(f"{loss_count} Losses", className="text-danger fw-bold") # Pegado a la derecha
        ], className="d-flex justify-content-between", style={"fontSize": "10px"}) # Flexbox separa los extremos
    ])
])

    # --- 4. GRÁFICO (Sin cambios) ---
    df_combined['display_ticker'] = df_combined['ticker'].apply(dm.clean_ticker_display)
    df_pl_by_ticker = df_combined.groupby('display_ticker')['realized_pl'].sum().reset_index()
    
    if df_pl_by_ticker.empty:
        fig_bar = create_empty_bar("Sin P/L realizado.")
    else:
        df_pl_by_ticker['color'] = df_pl_by_ticker['realized_pl'].apply(lambda x: '#00C851' if x >= 0 else '#ff4444')
        df_pl_by_ticker = df_pl_by_ticker.sort_values(by='realized_pl', ascending=False)
        
        fig_bar = px.bar(
            df_pl_by_ticker, 
            x='display_ticker', 
            y='realized_pl', 
            title='P/L Realizado por Ticker (Ventas + Ajustes)',
            color='color', 
            color_discrete_map={'#00C851': '#00C851', '#ff4444': '#ff4444'},
            labels={'realized_pl': 'P/L ($)', 'display_ticker': 'Ticker'}
        )
        fig_bar.update_layout(
            template="plotly_dark", 
            plot_bgcolor="rgba(0,0,0,0)", 
            paper_bgcolor="rgba(0,0,0,0)",
            margin=dict(t=30, b=40, l=10, r=10),
            height=350,
            showlegend=False,
            xaxis=dict(showgrid=False, tickangle=-45),
            yaxis=dict(showgrid=True, gridcolor='#333')
        )
        fig_bar.update_traces(hovertemplate='<b>%{x}</b><br>$%{y:,.2f}<extra></extra>')

    return kpi_content, fig_bar
# 3. Generar Pivot Table (P/L Realizado + P/L Abierto + P/L Total)
# pages/investments/investments_sales_analysis.py

@callback(
    Output("pivot-pl-container", "children"),
    [Input("sales-history-cache", "data"), 
     Input("assets-data-cache", "data")] 
)
def render_pl_pivot_table(json_history, json_assets_cache):
    
    # --- 1. PROCESAR VENTAS (P/L REALIZADO) ---
    df_sales_combined = pd.DataFrame()
    
    # A. Cargar Historial
    if json_history and json_history != '{}':
        df_all = pd.read_json(StringIO(json_history), orient='split')
        if not df_all.empty:
            # Filtramos solo ventas
            df_sales_system = df_all[df_all['type'] == 'SELL'][['ticker', 'realized_pl']].copy()
            # Limpiamos el ticker (Ej: BINANCE:BTCUSDT -> BTC)
            df_sales_system['ticker_clean'] = df_sales_system['ticker'].apply(dm.clean_ticker_display)
            df_sales_combined = df_sales_system

    # B. Cargar Ajustes Manuales
    df_adjustments = dm.get_pl_adjustments_df() # Trae columns: ticker, realized_pl
    if not df_adjustments.empty:
        df_adjustments['ticker_clean'] = df_adjustments['ticker'].apply(dm.clean_ticker_display)
        df_sales_combined = pd.concat([df_sales_combined, df_adjustments], ignore_index=True)
        
    # C. Agrupar por Ticker LIMPIO
    if not df_sales_combined.empty:
        # Sumamos todo lo que se llame igual (ej: BTC + BINANCE:BTC)
        df_sales_grouped = df_sales_combined.groupby('ticker_clean')['realized_pl'].sum().reset_index()
        df_sales_grouped.rename(columns={'ticker_clean': 'ticker', 'realized_pl': 'P/L Realizado'}, inplace=True)
    else:
        df_sales_grouped = pd.DataFrame(columns=['ticker', 'P/L Realizado'])

    
    # --- 2. PROCESAR ACTIVOS VIVOS (P/L ABIERTO) ---
    df_assets_grouped = pd.DataFrame()
    
    if json_assets_cache and json_assets_cache != '{}' and json_assets_cache != '[]':
        assets = json.loads(json_assets_cache)
        df_assets = pd.DataFrame(assets)
        
        if not df_assets.empty:
            # Usamos 'display_ticker' que ya viene limpio del backend, o limpiamos 'ticker' si no existe
            if 'display_ticker' in df_assets.columns:
                df_assets['ticker_clean'] = df_assets['display_ticker']
            else:
                df_assets['ticker_clean'] = df_assets['ticker'].apply(dm.clean_ticker_display)
                
            # Agrupamos por si tienes el mismo activo en 2 exchanges distintos
            df_assets_grouped = df_assets.groupby('ticker_clean')['total_gain'].sum().reset_index()
            df_assets_grouped.rename(columns={'ticker_clean': 'ticker', 'total_gain': 'P/L Abierto'}, inplace=True)

    if df_assets_grouped.empty:
        df_assets_grouped = pd.DataFrame(columns=['ticker', 'P/L Abierto'])


    # --- 3. COMBINAR TODO (MERGE) ---
    if df_sales_grouped.empty and df_assets_grouped.empty:
        return html.Div("No hay datos para analizar.", className="text-muted text-center py-4")

    # Hacemos el merge usando la columna 'ticker' que ahora contiene NOMBRES LIMPIOS en ambos lados
    df_pivot = pd.merge(df_sales_grouped, df_assets_grouped, on='ticker', how='outer').fillna(0)
    
    # Calcular Total
    df_pivot['P/L Total'] = df_pivot['P/L Realizado'] + df_pivot['P/L Abierto']
    
    # Ordenar
    df_pivot = df_pivot.sort_values(by='P/L Total', ascending=False).reset_index(drop=True)
    
    # --- 4. GENERAR TABLA ---
    columns = [
        {"name": "Ticker", "id": "ticker"},
        {"name": "P/L Realizado (Vendido)", "id": "P/L Realizado", "type": "numeric", "format": {"specifier": "$,.2f"}},
        {"name": "P/L Abierto (Activo)", "id": "P/L Abierto", "type": "numeric", "format": {"specifier": "$,.2f"}},
        {"name": "P/L Acumulado", "id": "P/L Total", "type": "numeric", "format": {"specifier": "$,.2f"}},
    ]
    
    style_data_conditional = [
        {'if': {'column_id': 'P/L Realizado', 'filter_query': '{P/L Realizado} > 0'}, 'color': '#00C851', 'fontWeight': 'bold'},
        {'if': {'column_id': 'P/L Realizado', 'filter_query': '{P/L Realizado} < 0'}, 'color': '#ff4444', 'fontWeight': 'bold'},
        
        {'if': {'column_id': 'P/L Abierto', 'filter_query': '{P/L Abierto} > 0'}, 'color': '#00C851', 'fontWeight': 'bold'},
        {'if': {'column_id': 'P/L Abierto', 'filter_query': '{P/L Abierto} < 0'}, 'color': '#ff4444', 'fontWeight': 'bold'},
        
        {'if': {'column_id': 'P/L Total', 'filter_query': '{P/L Total} > 0'}, 'backgroundColor': 'rgba(0, 200, 81, 0.1)', 'color': '#00C851', 'fontWeight': 'bold'},
        {'if': {'column_id': 'P/L Total', 'filter_query': '{P/L Total} < 0'}, 'backgroundColor': 'rgba(255, 68, 68, 0.1)', 'color': '#ff4444', 'fontWeight': 'bold'},
    ]

    return dash_table.DataTable(
        id='pl-pivot-table',
        data=df_pivot.to_dict('records'),
        columns=columns,
        style_header={'backgroundColor': '#1a1a1a', 'color': 'white', 'fontWeight': 'bold', 'textAlign': 'center', 'border': '1px solid #333'},
        style_cell={'textAlign': 'center', 'border': '1px solid #333', 'padding': '12px', 'backgroundColor': '#1a1a1a', 'color': 'white'},
        page_action='native',
        page_size=10,
        style_data_conditional=style_data_conditional,
        sort_action="native",
        filter_action="native"
    )