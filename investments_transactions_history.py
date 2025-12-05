# pages/investments/investments_transactions_history.py

import dash
from dash import dcc, html, callback, Input, Output, State, no_update, ctx
import dash_bootstrap_components as dbc
import backend.data_manager as dm
from dash import dash_table
import pandas as pd
import json 
from utils import ui_helpers 
import plotly.graph_objects as go # Necesario para create_empty_bar

# --- FUNCIONES AUXILIARES ---

def create_empty_bar(title, height=350):
    """Genera una figura vacía con un mensaje central (Reimplementado localmente por seguridad)."""
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


# --- STORE Y MODAL: ANULACIÓN DE TRANSACCIÓN ---

# Se necesita un store para el ID de la transacción seleccionada
trade_deleting_store = dcc.Store(id='trade-deleting-id', data=None)

# MODAL: CONFIRMACIÓN DE ANULACIÓN
trade_delete_confirm_modal = dbc.Modal([
    dbc.ModalHeader(dbc.ModalTitle("Confirmar Anulación de Transacción")),
    dbc.ModalBody(html.Div([
        html.P("¿Estás seguro de anular esta transacción?"),
        html.P("Esto revertirá el movimiento (suma/resta de unidades y corrección de costos) en tu portafolio.", className="text-warning")
    ])),
    dbc.ModalFooter([
        dbc.Button("Cancelar", id="btn-trade-del-cancel", className="ms-auto", outline=True),
        dbc.Button("Sí, Anular", id="btn-trade-del-confirm", color="danger"),
    ])
], id="trade-delete-confirm-modal", is_open=False, centered=True, size="sm")


# --- LAYOUT PRINCIPAL (Contenido de la pestaña "Historial Detallado") ---

layout = dbc.Container([
    
    trade_deleting_store, 
    trade_delete_confirm_modal,
    
    html.H4("Historial Detallado de Transacciones de Inversión", className="mb-3 mt-4 text-info"),
    html.P("Registro cronológico de todas las compras y ventas realizadas.", className="text-muted"),
    dbc.Card(
        dbc.CardBody(id="transaction-history-table-container", children=dbc.Spinner(size="lg", color="info", type="grow")), 
        className="data-card mb-4"
    ),
    
], fluid=True)


# ==============================================================================
# CALLBACKS DE LÓGICA Y DATOS
# ==============================================================================

# 0. Fetch y Caché de Transacciones (Alimenta ambas pestañas de análisis/historial)
# Nota: La señal 'sales-update-signal' se define en investments_assets.py
@callback(
    Output('sales-history-cache', 'data'),
    Input('url', 'pathname'),
    Input('sales-update-signal', 'data'), 
    Input('asset-update-signal', 'data'),
    prevent_initial_call=False
)
def fetch_and_cache_transactions(pathname, signal_sales, signal_assets):
    if pathname == "/inversiones":
        # Llama a la función consolidada
        df = dm.get_investment_transactions_df() 
        df['realized_pl'] = pd.to_numeric(df['realized_pl'], errors='coerce')
        return df.to_json(date_format='iso', orient='split')
    return '{}'


# 1. Renderizar Historial Detallado de Transacciones (COMPRAS y VENTAS)
@callback(
    Output("transaction-history-table-container", "children"),
    Input("sales-history-cache", "data") # Contiene todo el historial de trades
)
def render_transaction_history_table(json_history):
    
    if not json_history or json_history == '{}':
        return html.Div("No hay transacciones de inversión registradas.", className="text-muted fst-italic text-center py-4")

    df_history = pd.read_json(json_history, orient='split')
    
    # Renombrar y seleccionar columnas para la visualización
    df_history = df_history.rename(columns={
        'date': 'Fecha', 
        'ticker': 'Ticker', 
        'type': 'Tipo', 
        'shares': 'Cant. Unidades', 
        'price': 'Precio Ejecución', 
        'total_transaction': 'Total Transacción',
        'realized_pl': 'P/L',
        'avg_cost_at_trade': 'Costo Promedio'
    })
    
    df_history['Tipo'] = df_history['Tipo'].apply(lambda x: 'Venta' if x == 'SELL' else 'Compra')
    
    # Añadir columna de acción (botón de eliminar)
    df_history['Acción'] = "✖" 

    # --- GENERAR DASH TABLE ---
    columns = [
        {"name": "Fecha", "id": "Fecha"},
        {"name": "Tipo", "id": "Tipo"},
        {"name": "Ticker", "id": "Ticker"},
        {"name": "Precio Ejecución", "id": "Precio Ejecución", "type": "numeric", "format": {"specifier": "$,.2f"}},
        {"name": "Cant. Unidades", "id": "Cant. Unidades", "type": "numeric", "format": {"specifier": ",.2f"}},
        {"name": "Total Transacción", "id": "Total Transacción", "type": "numeric", "format": {"specifier": "$,.2f"}},
        {"name": "P/L", "id": "P/L", "type": "numeric", "format": {"specifier": "$,.2f"}},
        {"name": "Costo Promedio", "id": "Costo Promedio", "type": "numeric", "format": {"specifier": "$,.2f"}},
        {"name": "Anular", "id": "Acción", "deletable": False, "selectable": False} 
    ]
    
    # Estilos de color condicional
    style_data_conditional = [
        {'if': {'column_id': 'P/L', 'filter_query': '{P/L} > 0'}, 'color': '#00C851', 'fontWeight': 'bold'},
        {'if': {'column_id': 'P/L', 'filter_query': '{P/L} < 0'}, 'color': '#ff4444', 'fontWeight': 'bold'},
        {'if': {'filter_query': '{Tipo} = "Venta"'}, 'backgroundColor': 'rgba(255, 68, 68, 0.1)', 'color': 'white'},
        {'if': {'filter_query': '{Tipo} = "Compra"'}, 'backgroundColor': 'rgba(0, 200, 81, 0.1)', 'color': 'white'},
        {'if': {'column_id': 'Acción'}, 'textAlign': 'center', 'cursor': 'pointer', 'fontWeight': 'bold', 'color': '#f44336'},
    ]

    return dash_table.DataTable(
        id='detailed-history-table',
        data=df_history.to_dict('records'),
        columns=columns,
        style_header={'backgroundColor': '#333', 'color': 'white', 'fontWeight': 'bold', 'textAlign': 'center'},
        style_cell={'textAlign': 'center', 'border': '1px solid #444', 'padding': '10px'},
        page_action='native',
        page_size=10,
        style_data_conditional=style_data_conditional,
        sort_action="native",
        filter_action="native"
    )


# 2. Toggle Modal de Confirmación para Anulación
@callback(
    [Output("trade-delete-confirm-modal", "is_open"),
     Output("trade-deleting-id", "data")],
    [Input("detailed-history-table", "active_cell"),
     Input("btn-trade-del-cancel", "n_clicks"),
     Input("btn-trade-del-confirm", "n_clicks")],
    [State("detailed-history-table", "data")],
    prevent_initial_call=True
)
def handle_trade_delete_modal(active_cell, cancel_n, confirm_n, table_data):
    trig = ctx.triggered_id
    
    if trig == "btn-trade-del-cancel" or trig == "btn-trade-del-confirm":
        return False, no_update
        
    # Verificar si se hizo clic en la columna 'Acción'
    if trig == "detailed-history-table" and active_cell:
        if active_cell['column_id'] == 'Acción':
            # El ID es el 'id' de la transacción
            trade_id = table_data[active_cell['row']]['id'] 
            return True, trade_id
    
    return no_update, no_update


# 3. Finalizar Anulación y Trigger Refresh
@callback(
    [Output("sales-history-cache", "data", allow_duplicate=True), 
     Output("trade-delete-confirm-modal", "is_open", allow_duplicate=True),
     Output("asset-update-signal", "data", allow_duplicate=True)], 
    Input("btn-trade-del-confirm", "n_clicks"),
    [State("trade-deleting-id", "data"),
     State("asset-update-signal", "data")],
    prevent_initial_call=True
)
def finalize_trade_annulation(n_clicks, trade_id, asset_signal):
    if n_clicks and trade_id is not None:
        success, msg = dm.undo_investment_transaction(trade_id) 
        
        if success:
            # 1. Recargar el historial (no_update funciona si el fetcher usa la señal)
            # 2. Cerrar modal (False)
            # 3. Aumentar la señal de activos para actualizar la tabla de posiciones
            return no_update, False, (asset_signal + 1) 
        else:
            # En caso de error, solo prevenimos el cierre del modal temporalmente
            print(f"Error al anular transacción {trade_id}: {msg}")
            return no_update, no_update, no_update
            
    return no_update, no_update, no_update