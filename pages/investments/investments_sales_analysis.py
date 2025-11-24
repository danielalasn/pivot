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
                    html.Small("P/L de todas las ventas cerradas.", className="text-muted small")
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
@callback(
    [Output("kpi-total-realized-pl", "children"),
     Output("realized-pl-bar-chart", "figure")],
    Input("sales-history-cache", "data")
)
def render_realized_pl_summary(json_history):
    # --- 1. PREPARACIÓN DE DATOS ---
    df_sales = pd.DataFrame({'ticker': [], 'realized_pl': []})
    
    if json_history and json_history != '{}':
        # 🚨 CORRECCIÓN LÍNEA 300 🚨
        df_all = pd.read_json(StringIO(json_history), orient='split')
        df_sales = df_all[df_all['type'] == 'SELL'][['ticker', 'realized_pl']].copy()

    df_adjustments = dm.get_pl_adjustments_df()
    
    if not df_adjustments.empty:
        df_combined = pd.concat([df_sales, df_adjustments], ignore_index=True)
    else:
        df_combined = df_sales
    
    if df_combined.empty:
        return "$0.00", create_empty_bar("Sin datos de ventas.")

    df_pl_by_ticker = df_combined.groupby('ticker')['realized_pl'].sum().reset_index()
    total_pl = df_pl_by_ticker['realized_pl'].sum()
    
    # --- 1A. KPI ---
    pl_color_cls = "text-success" if total_pl >= 0 else "text-danger"
    kpi_output = html.Span(f"${total_pl:,.2f}", className=pl_color_cls)
    
    # --- 1B. GRÁFICO DE BARRAS ---
    if df_pl_by_ticker.empty or total_pl == 0:
        fig_bar = create_empty_bar("Sin P/L realizado.")
    else:
        df_pl_by_ticker['color'] = df_pl_by_ticker['realized_pl'].apply(lambda x: '#00C851' if x >= 0 else '#ff4444')
        
        fig_bar = px.bar(
            df_pl_by_ticker, 
            x='ticker', 
            y='realized_pl', 
            title='P/L Realizado por Ticker (Ventas + Ajustes)',
            color='color', 
            color_discrete_map={'#00C851': '#00C851', '#ff4444': '#ff4444'},
            labels={'realized_pl': 'P/L Realizado ($)', 'ticker': 'Ticker'}
        )
        fig_bar.update_layout(
            template="plotly_dark", 
            plot_bgcolor="rgba(0,0,0,0)", 
            paper_bgcolor="rgba(0,0,0,0)",
            margin=dict(t=30, b=0, l=10, r=10),
            height=350,
            xaxis={'categoryorder': 'total descending', 'showgrid': False},
            yaxis={'showgrid': False, 'zeroline': True, 'zerolinewidth': 2, 'zerolinecolor': 'gray'},
            showlegend=False
        )
        fig_bar.update_traces(hovertemplate='<b>%{x}</b><br>P/L: $%{y:,.2f}<extra></extra>')

    return kpi_output, fig_bar


# 3. Generar Pivot Table (P/L Realizado + P/L Abierto + P/L Total)
@callback(
    Output("pivot-pl-container", "children"),
    [Input("sales-history-cache", "data"), 
     Input("assets-data-cache", "data")] 
)
def render_pl_pivot_table(json_history, json_assets_cache):
    
    # 1A. Ventas Realizadas (P/L Cerrado + Ajustes)
    df_sales_combined = pd.DataFrame()
    if json_history and json_history != '{}':
        # 🚨 CORRECCIÓN LÍNEA 361 🚨
        df_all = pd.read_json(StringIO(json_history), orient='split')
        df_sales_system = df_all[df_all['type'] == 'SELL'][['ticker', 'realized_pl']].copy()
        
        df_adjustments = dm.get_pl_adjustments_df()
        df_sales_combined = pd.concat([df_sales_system, df_adjustments], ignore_index=True)
        
        if not df_sales_combined.empty:
            df_sales_combined = df_sales_combined.groupby('ticker')['realized_pl'].sum().reset_index().rename(columns={'realized_pl': 'P/L Realizado'})
        
    if df_sales_combined.empty:
        df_sales_combined = pd.DataFrame(columns=['ticker', 'P/L Realizado'])

    
    # 1B. Posiciones Vivas (P/L Abierto)
    df_assets = pd.DataFrame()
    if json_assets_cache and json_assets_cache != '{}' and json_assets_cache != '[]':
        assets = json.loads(json_assets_cache)
        df_assets = pd.DataFrame(assets)
        
        if not df_assets.empty:
            df_assets = df_assets.groupby('ticker')['total_gain'].sum().reset_index().rename(columns={'total_gain': 'P/L Abierto'})

    if df_assets.empty:
        df_assets = pd.DataFrame(columns=['ticker', 'P/L Abierto'])


    # --- 2. COMBINAR DATOS ---
    if df_sales_combined.empty and df_assets.empty:
        return html.Div("No hay datos de ventas ni activos vivos para analizar.", className="text-muted fst-italic text-center py-4")

    df_pivot = pd.merge(df_sales_combined, df_assets, on='ticker', how='outer').fillna(0)
    
    df_pivot['P/L Total'] = df_pivot['P/L Realizado'] + df_pivot['P/L Abierto']
    
    df_pivot = df_pivot[['ticker', 'P/L Realizado', 'P/L Abierto', 'P/L Total']]
    df_pivot = df_pivot.sort_values(by='P/L Total', ascending=False).reset_index(drop=True)
    
    # --- 3. GENERAR DASH TABLE ---
    
    # Definición de columnas de la tabla (usando el ID 'P/L Realizado' que coincide con el DF)
    columns = [
        {"name": "Ticker", "id": "ticker"},
        {"name": "P/L Realizado (Vendido)", "id": "P/L Realizado", "type": "numeric", "format": {"specifier": "$,.2f"}},
        {"name": "P/L Abierto (Activo)", "id": "P/L Abierto", "type": "numeric", "format": {"specifier": "$,.2f"}},
        {"name": "P/L Acumulado", "id": "P/L Total", "type": "numeric", "format": {"specifier": "$,.2f"}},
    ]
    
    style_data_conditional = [
        # Las condiciones usan el ID original del DataFrame: 'P/L Realizado'
        {'if': {'column_id': 'P/L Realizado', 'filter_query': '{P/L Realizado} > 0'}, 'color': '#00C851', 'fontWeight': 'bold'},
        {'if': {'column_id': 'P/L Realizado', 'filter_query': '{P/L Realizado} < 0'}, 'color': '#ff4444', 'fontWeight': 'bold'},
        
        {'if': {'column_id': 'P/L Abierto', 'filter_query': '{P/L Abierto} > 0'}, 'color': '#00C851', 'fontWeight': 'bold'},
        {'if': {'column_id': 'P/L Abierto', 'filter_query': '{P/L Abierto} < 0'}, 'color': '#ff4444', 'fontWeight': 'bold'},
        
        {'if': {'column_id': 'P/L Total', 'filter_query': '{P/L Total} > 0'}, 'backgroundColor': '#1E3C2B', 'color': '#00C851', 'fontWeight': 'bolder'},
        {'if': {'column_id': 'P/L Total', 'filter_query': '{P/L Total} < 0'}, 'backgroundColor': '#3C1E1E', 'color': '#ff4444', 'fontWeight': 'bolder'},
        {'if': {'column_id': 'P/L Total', 'filter_query': '{P/L Total} = 0'}, 'backgroundColor': '#333', 'color': '#fff', 'fontWeight': 'bolder'},
    ]

    return dash_table.DataTable(
        id='pl-pivot-table',
        data=df_pivot.to_dict('records'),
        columns=columns,
        style_header={'backgroundColor': '#333', 'color': 'white', 'fontWeight': 'bold', 'textAlign': 'center'},
        style_cell={'textAlign': 'center', 'border': '1px solid #444', 'padding': '10px'},
        page_action='native',
        page_size=10,
        style_data_conditional=style_data_conditional,
        sort_action="native",
        filter_action="native"
    )