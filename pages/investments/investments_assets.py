# pages/investments/investments_assets.py
import dash
from dash import dcc, html, callback, Input, Output, State, no_update, ctx, ALL 
import dash_bootstrap_components as dbc
import backend.data_manager as dm
from utils import ui_helpers
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import time 
import json 


from . import investments_transactions 


# ------------------------------------------------------------------------------
# 1. FUNCIONES AUXILIARES (Definidas antes del Layout)
# ------------------------------------------------------------------------------
def smart_format(val):
    if pd.isna(val) or val == 0:
        return "0"
    if float(val).is_integer():
        return f"{int(val):,}"
    
    val_abs = abs(val)
    if val_abs >= 0.01:
        return f"{val:,.2f}"
    else:
        # Redondeo a 5 decimales y limpieza de ceros
        return f"{val:.5f}".rstrip('0').rstrip('.')
# --- FUNCIÓN AUXILIAR 1: FIGURA INICIAL ---
def get_initial_empty_fig():
    """Genera una figura transparente y vacía para evitar el flash blanco al cargar."""
    fig = go.Figure()
    fig.update_layout(
        template="plotly_dark",
        plot_bgcolor="rgba(0,0,0,0)", 
        paper_bgcolor="rgba(0,0,0,0)", 
        xaxis={"visible": False}, 
        yaxis={"visible": False},
        font={"color": "#444"},
        margin=dict(t=0, b=0, l=0, r=0)
    )
    return fig

# --- FUNCIÓN AUXILIAR 2: FIGURA VACÍA CON MENSAJE ---
def create_empty_pie(title):
    """Genera una figura con un mensaje central para cuando no hay datos."""
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
        }]
    )
    return fig

# --- FUNCIÓN AUXILIAR 3: BARRA DE RANGO VISUAL ---
def create_range_bar(min_val, max_val, current_price, label):
    """
    Genera una barra visual donde el nivel de llenado representa la posición del precio 
    actual dentro del rango histórico Mín/Máx.
    """
    
    if max_val <= min_val or max_val == 0:
        return html.Div(f"{label}: Sin datos de rango.", className="text-muted small")

    price_range = max_val - min_val
    price_position = current_price - min_val
    
    bar_value_pct = (price_position / price_range) * 100
    bar_value_pct = max(0, min(100, bar_value_pct))

    return html.Div([
        html.Small(f"{label}: ", className="text-muted d-block fw-bold mb-1"),
        
        dbc.Progress(
            value=bar_value_pct,
            color="#33b5e5", 
            className="mb-1",
            style={
                "height": "12px", 
                "backgroundColor": "var(--input-bg)", 
                "borderRadius": "5px"
            },
        ),
        
        dbc.Row([
            dbc.Col(f"${min_val:,.2f}", width="auto", className="small text-muted me-auto"),
            dbc.Col(f"${max_val:,.2f}", width="auto", className="small text-muted text-end"),
        ], className="g-0 justify-content-between", style={'marginTop': '5px'})
        
    ], className="mb-4")


# ------------------------------------------------------------------------------
# 2. MODALES Y LAYOUT PRINCIPAL
# ------------------------------------------------------------------------------

# --- MODAL: DETALLE POSICIÓN ---
detail_asset_modal = dbc.Modal([
    dbc.ModalHeader(dbc.ModalTitle(id="detail-asset-title")),
    dbc.ModalBody(id="detail-asset-body"),
    dbc.ModalFooter([
        # Botón de Edición
        dbc.Button("Editar", id="btn-open-edit-modal", color="info", outline=True, className="me-auto"),
        
        # Botón de gestión (Eliminar)
        dbc.Button("Eliminar Posición", id="btn-asset-delete", color="secondary", outline=True, className="ms-2"),
    ])
], id="detail-asset-modal", is_open=False, centered=True, size="md")


# --- MODAL: AÑADIR POSICIÓN ---
add_asset_modal = dbc.Modal([
    dbc.ModalHeader("Agregar Nueva Posición"),
    dbc.ModalBody([
        html.Div([
            html.Small("Para criptomonedas, usa el formato: BINANCE:BTCUSDT", className="text-warning fw-bold"),
        ], className="mb-3 p-2 border border-warning rounded"),

        dbc.Label("Ticker Symbol"),
        dbc.Input(id="new-asset-ticker", placeholder="Ej: AAPL, SPY, BTCUSD", type="text", className="mb-3"),
        
        dbc.Label("Cantidad de Unidades"),
        dbc.Input(id="new-asset-shares", placeholder="0.0", type="number", className="mb-3"),
        
        dbc.Label("Inversión Total ($)"), 
        dbc.Input(id="new-asset-total-investment", placeholder="0.00", type="number", className="mb-3"), 
        
        html.Div(id="asset-modal-msg", className="text-center")
    ]),
    dbc.ModalFooter([
        dbc.Button("Cancelar", id="btn-asset-cancel", outline=True),
        dbc.Button("Guardar", id="btn-asset-save", color="success", className="ms-2"),
    ])
], id="add-asset-modal", is_open=False, centered=True, size="sm")


# --- MODAL: EDITAR POSICIÓN ---
edit_asset_modal = dbc.Modal([
    dbc.ModalHeader("Editar Posición Existente"),
    dbc.ModalBody([
        html.P("Solo se permite editar las unidades y la inversión total, lo cual recalculará el costo promedio.", className="text-warning small"),
        
        dbc.Label("Ticker Symbol"),
        dbc.Input(id="edit-asset-ticker", type="text", disabled=True, className="mb-3"),
        
        dbc.Label("Cantidad de Unidades"),
        dbc.Input(id="edit-asset-shares", placeholder="0.0", type="number", className="mb-3"),
        
        dbc.Label("Inversión Total ($)"), 
        dbc.Input(id="edit-asset-total-investment", placeholder="0.00", type="number", className="mb-3"), 
        
        html.Div(id="edit-asset-modal-msg", className="text-center")
    ]),
    dbc.ModalFooter([
        dbc.Button("Cancelar", id="btn-edit-cancel", outline=True),
        dbc.Button("Guardar Cambios", id="btn-edit-save", color="info", className="ms-2"),
    ])
], id="edit-asset-modal", is_open=False, centered=True, size="sm")


# --- MODAL 3: CONFIRMACIÓN DE ELIMINACIÓN ---
delete_confirm_modal = dbc.Modal([
    dbc.ModalHeader(dbc.ModalTitle("Confirmar Eliminación")),
    dbc.ModalBody("¿Estás seguro de eliminar esta posición? Esta acción no se puede deshacer y el balance será corregido."),
    dbc.ModalFooter([
        dbc.Button("Cancelar", id="btn-del-cancel", className="ms-auto", outline=True),
        dbc.Button("Sí, Eliminar", id="btn-del-confirm", color="danger"),
    ])
], id="asset-delete-confirm-modal", is_open=False, centered=True, size="sm")


# --- LAYOUT PRINCIPAL ---
layout = dbc.Container([
    # STORES COMPARTIDOS (Visibles globalmente)
    dcc.Store(id="asset-update-signal", data=0),
    dcc.Store(id="asset-viewing-id", data=None),
    dcc.Store(id="assets-data-cache", data='{}'),
    dcc.Store(id="trans-asset-ticker-store", data=None),
    dcc.Store(id="data-ready-flag", data=False), 
    dcc.Store(id='sales-update-signal', data=0), 
    dcc.Store(id='sales-history-cache', data='{}'), 

    # Botones ocultos para evitar error 'nonexistent object'
    html.Button(id="btn-open-sell-modal", style={'display': 'none'}),
    html.Button(id="btn-open-buy-modal", style={'display': 'none'}),
    
    ui_helpers.get_feedback_toast("asset-toast"),

    add_asset_modal,
    detail_asset_modal,
    edit_asset_modal, 
    delete_confirm_modal,
    investments_transactions.layout,

    # 1. EL LOADER (VISIBLE POR DEFECTO)
    html.Div(id="initial-loader", children=[
        dbc.Spinner(color="info", type="grow", size="lg"),
        html.H4("Cargando Portafolio...", className="mt-3 text-info fw-bold"),
        html.Small("Obteniendo últimos precios de mercado...", className="text-muted")
    ], style={
        "height": "60vh", 
        "display": "flex", 
        "flexDirection": "column", 
        "justifyContent": "center", 
        "alignItems": "center"
    }),

    html.Div(id="main-dashboard-view", style={"display": "none"}, children=[
        
        dbc.Row([
            dbc.Col(
                html.H4("Resumen del Portafolio", className="text-info mb-0"), 
                width="auto", 
                className="d-flex align-items-center"
            ),
            
            dbc.Col([
                # COMPONENTE DE CARGA (Loading)
                dcc.Loading(
                    id="loading-refresh-inv",
                    type="circle",
                    color="#2A9FD6",
                    children=[
                        html.Div([
                            dbc.Button(
                                html.I(className="bi bi-arrow-clockwise"), 
                                id="btn-refresh-investments", 
                                color="link", 
                                size="sm", 
                                className="p-0 ms-2 text-decoration-none text-muted fs-5",
                                title="Actualizar precios ahora"
                            ),
                            # ETIQUETA DE FECHA (Se actualiza con la DB)
                            html.Small(id="last-updated-inv-label", className="text-muted ms-2 small fst-italic"),
                            
                            # 🚨 NUEVO: Div invisible para forzar el spinner
                            html.Div(id="dummy-spinner-target", style={"display": "none"})
                            
                        ], className="d-flex align-items-center")
                    ]
                )
            ], width="auto", className="d-flex align-items-center ms-auto"),
        ], className="mb-3 align-items-center"),
        
        # 🚨 AQUÍ ESTABA EL ERROR: FALTABA ESTA FILA 🚨
        # Esta es la fila donde el callback inyecta los cuadros de KPIs (Valor Total, P/L, etc.)
        dbc.Row(id="assets-summary-row", className="g-4 mb-4"), 
        
        # 2. GRÁFICOS PIE
        dbc.Row([
            dbc.Col(dbc.Card(dbc.CardBody([
                html.H5("Valor por Activo", className="card-title text-muted"),
                dcc.Graph(id="assets-pie-stock", config={'displayModeBar': False}, style={'height': '300px'}, figure=get_initial_empty_fig())
            ]), className="data-card"), lg=4, md=12, className="mb-4"),
            
            dbc.Col(dbc.Card(dbc.CardBody([
                html.H5("Distribución por Industria", className="card-title text-muted"),
                dcc.Graph(id="assets-pie-industry", config={'displayModeBar': False}, style={'height': '300px'}, figure=get_initial_empty_fig())
            ]), className="data-card"), lg=4, md=12, className="mb-4"),

            dbc.Col(dbc.Card(dbc.CardBody([
                html.H5("Distribución por Tipo", className="card-title text-muted"), 
                dcc.Graph(id="assets-pie-type", config={'displayModeBar': False}, style={'height': '300px'}, figure=get_initial_empty_fig())
            ]), className="data-card"), lg=4, md=12, className="mb-4"),
        ], className="g-4"),
        
        # 3. POSICIONES INDIVIDUALES 
        html.H4("Posiciones por Tipo", className="mb-3 mt-4 text-info"), 

        # --- DROP DOWN DE ORDENACIÓN ---
        dbc.Row([
            dbc.Col(
                dbc.Label("Ordenar por:", className="me-2 text-muted"),
                width="auto",
                className="d-flex align-items-center"
            ),
            dbc.Col(
                dcc.Dropdown(
                    id='assets-sort-dropdown',
                    options=[
                        {'label': 'Nombre (A-Z)', 'value': 'ticker_asc'},
                        {'label': 'Nombre (Z-A)', 'value': 'ticker_desc'},
                        {'label': 'Valor (Alto-Bajo)', 'value': 'market_value_desc'},
                        {'label': 'Valor (Menor a Mayor)', 'value': 'market_value_asc'}, 
                        {'label': '% Cambio Hoy (Ganadores)', 'value': 'day_change_pct_desc'},
                        {'label': '% Cambio Hoy (Perdedores)', 'value': 'day_change_pct_asc'},
                        {'label': '% Ganancia Total (Mayor)', 'value': 'total_gain_pct_desc'},
                        {'label': '% Ganancia Total (Menor)', 'value': 'total_gain_pct_asc'},
                    ],
                    value='market_value_desc',
                    clearable=False,
                    searchable=False
                ),
                lg=3, md=5
            ),
            dbc.Col(
                dbc.Button("+ Agregar Posición", id="btn-open-asset-modal", color="primary", className="mb-4"),
                width="auto"
            )
        ], className="mb-4"),
        
        # --- TABS DE FILTRADO ---
        dbc.Tabs(id="assets-display-tabs", active_tab="tab-all", children=[
            dbc.Tab(label="Todos los Activos", tab_id="tab-all"),
            dbc.Tab(label="Acciones (Stocks)", tab_id="tab-stocks"),
            dbc.Tab(label="Fondos (ETFs)", tab_id="tab-etfs"),
            dbc.Tab(label="Cripto/Forex", tab_id="tab-crypto"),
            dbc.Tab(label="Otros", tab_id="tab-other"),
        ], className="mb-3"), 

        dbc.Row(id="assets-grid", className="g-4", style={"minHeight": "200px"}) 
    ])
], fluid=True, className="py-3")


# ------------------------------------------------------------------------------
# 3. CALLBACKS
# ------------------------------------------------------------------------------

# 0. Callback Inicial/Actualización: Llama a la API y guarda el DF en el Store.
# 0. Callback Inicial/Actualización: Llama a la API y guarda el DF en el Store.
# 0. Callback Inicial/Actualización: Llama a la API y guarda el DF en el Store.
# 0. Callback Inicial/Actualización: Llama a la API y guarda el DF en el Store.
# 0. Callback Inicial/Actualización: Solo carga datos (Lectura)
@callback(
    [Output('assets-data-cache', 'data'),
     Output('last-updated-inv-label', 'children')], 
    [Input('url', 'pathname'),
     Input('asset-update-signal', 'data')], # <--- YA NO ESTÁ EL BOTÓN AQUÍ
    prevent_initial_call=False
)
def fetch_and_cache_assets(pathname, signal):
    uid = dm.get_uid() # Obtener ID
    if not uid: return no_update, no_update
    
    if pathname == "/inversiones":
        # Traemos los datos (Sin forzar refresh aquí, solo lectura de DB)
        stocks_list = dm.get_stocks_data(uid, force_refresh=False)
        timestamp = dm.get_data_timestamp()
        label_text = f"Actualizado: {timestamp}"
        return json.dumps(stocks_list), label_text
        
    return no_update, no_update

# 0-B. Callback Nuevo: Acción Manual de Refrescar (Escritura + Notificación)
# 0-B. Callback Nuevo: Acción Manual de Refrescar
@callback(
    [Output("asset-update-signal", "data", allow_duplicate=True),
     Output("asset-toast", "is_open", allow_duplicate=True),
     Output("asset-toast", "children", allow_duplicate=True),
     Output("asset-toast", "icon", allow_duplicate=True),
     # 🚨 NUEVO OUTPUT: Apuntamos al div invisible dentro del spinner
     Output("dummy-spinner-target", "children")], 
    Input("btn-refresh-investments", "n_clicks"),
    State("asset-update-signal", "data"),
    prevent_initial_call=True
)
def manual_refresh_handler(n_clicks, signal):
    # Ajustamos el retorno de no_update para que coincida con la cantidad de outputs (5)
    if not n_clicks: return no_update, no_update, no_update, no_update, no_update
    
    # 1. Llamar a la función robusta del backend (Aquí es donde tarda y gira la rueda)
    success, msg = dm.manual_price_refresh()
    
    # 2. Incrementar señal
    new_signal = (signal or 0) + 1
    
    # 🚨 NOTA: Agregamos "" al final de los return para llenar el dummy-spinner-target
    if success:
        return new_signal, *ui_helpers.mensaje_alerta_exito("success", msg), ""
    else:
        return new_signal, *ui_helpers.mensaje_alerta_exito("danger", msg), ""
# 1. Abrir/Cerrar Modal Agregar

@callback(
    [Output("add-asset-modal", "is_open"),
     Output("asset-modal-msg", "children", allow_duplicate=True)],
    [Input("btn-open-asset-modal", "n_clicks"), 
     Input("btn-asset-cancel", "n_clicks"), 
     Input("asset-update-signal", "data")],
    State("add-asset-modal", "is_open"),
    prevent_initial_call=True
)
def toggle_add_modal(open_n, cancel_n, signal, is_open):
    if ctx.triggered_id == "asset-update-signal" or ctx.triggered_id == "btn-asset-cancel": 
        return False, "" 
    return not is_open, "" 

# 2. Guardar Posición (CON VALIDACIÓN DE TICKER y TOTAL INVESTMENT)
# 2. Guardar Posición (CON VALIDACIÓN Y TOAST)
@callback(
    [Output("asset-update-signal", "data", allow_duplicate=True),
     Output("add-asset-modal", "is_open", allow_duplicate=True),  # 1. Controlar Modal
     Output("asset-toast", "is_open", allow_duplicate=True),      # 2. Controlar Toast
     Output("asset-toast", "children", allow_duplicate=True),     # 3. Mensaje Toast
     Output("asset-toast", "icon", allow_duplicate=True),         # 4. Icono Toast
     Output("asset-modal-msg", "children", allow_duplicate=True)], # 5. Mensaje interno (limpieza)
    Input("btn-asset-save", "n_clicks"),
    [State("new-asset-ticker", "value"),
     State("new-asset-shares", "value"),
     State("new-asset-total-investment", "value"),
     State("asset-update-signal", "data")],
    prevent_initial_call=True
)
def save_asset(n_clicks, ticker, shares, total_investment, signal):
    if not n_clicks: 
        return no_update, no_update, no_update, no_update, no_update, no_update

    # --- VALIDACIONES BÁSICAS ---
    if not all([ticker, shares, total_investment]):
        # Error de validación: Mantenemos modal abierto y mostramos error interno
        return no_update, True, False, "", "", html.Span("Faltan datos obligatorios.", className="text-danger")
    
    es_valido = dm.is_ticker_valid(ticker)
    if not es_valido:
        return no_update, True, False, "", "", html.Span("Error: El Ticker no existe o no es soportado.", className="text-danger")

    try:
        shares_f = float(shares)
        total_investment_f = float(total_investment)
        if shares_f <= 0 or total_investment_f <= 0:
            return no_update, True, False, "", "", html.Span("Valores deben ser positivos.", className="text-danger")
    except ValueError:
        return no_update, True, False, "", "", html.Span("Datos numéricos inválidos.", className="text-danger")

    # --- GUARDADO EN DB ---
    success, msg = dm.add_stock(ticker, shares_f, total_investment_f)

    if success:
        # ✅ ÉXITO: 
        # 1. Signal +1 (Recarga tabla)
        # 2. Modal False (Cierra modal)
        # 3. Toast True (Muestra éxito)
        # 4. Mensaje interno limpio
        return (signal or 0) + 1, False, *ui_helpers.mensaje_alerta_exito("success", msg), ""
    else:
        # ❌ ERROR DB:
        # Mantenemos modal abierto y mostramos error en Toast
        return no_update, True, *ui_helpers.mensaje_alerta_exito("danger", f"Error: {msg}"), ""

# 3A. Generar Resumen y Gráficos de Pastel (Usa el CACHÉ) - Lógica de renderizado
# pages/investments/investments_assets.py (Callback 3A - MODIFICADO)

# 3A. Generar Resumen y Gráficos de Pastel (Usa el CACHÉ) - Lógica de renderizado
@callback(
    [Output("assets-summary-row", "children"),
     Output("assets-pie-stock", "figure"),
     Output("assets-pie-industry", "figure"),
     Output("assets-pie-type", "figure")],
    [Input("assets-data-cache", "data")] 
)
def render_portfolio_summary(json_assets):
    
    if not json_assets or json_assets == '{}' or json_assets == '[]':
        assets = []
        summary = {
            'market_value': 0.0, 'day_gain_usd': 0.0, 'day_pct': 0.0,
            'total_gain_usd': 0.0, 'total_pct': 0.0 
        }
        df_stock = pd.DataFrame({'name': [], 'value': []})
        df_industry = pd.DataFrame({'name': [], 'value': []})
        df_asset_type = pd.DataFrame({'name': [], 'value': []})
        
    else:
        assets = json.loads(json_assets)
        summary = dm.get_portfolio_summary_data(assets)
        df_stock, df_industry = dm.get_portfolio_breakdown(assets)
        df_asset_type = dm.get_asset_type_breakdown(assets)

    # --- CÁLCULOS DE VALORES FINALES ---
    open_gain = summary['total_gain_usd']
    realized_pl_total = dm.get_total_realized_pl() 
    
    # 🚨 LÓGICA ANTERIOR (ERRÓNEA PARA TU OBJETIVO)
    # total_investment_base = dm.get_total_historical_investment_cost() # <-- Esto sumaba lo vendido
    
    # ✅ CORRECCIÓN: Calcular costo base SOLO de activos vivos
    # Iteramos sobre la lista 'assets' que ya cargaste del JSON
    current_assets_cost = sum(a['shares'] * a['avg_price'] for a in assets)
    
    total_historical_profit = open_gain + realized_pl_total
    
    # Cálculo de la Base Neta de Capital (Tu lógica exacta)
    # (Costo de lo que tengo hoy) - (Ganancias que ya cobré)
    net_investment_base = current_assets_cost - realized_pl_total
    
    # Cálculo del Porcentaje 
    total_pct = 0.0
    
    # Ajustamos la lógica del porcentaje para que sea consistente
    if net_investment_base > 0:
        total_pct = (total_historical_profit / net_investment_base) * 100
    elif total_historical_profit > 0 and summary['market_value'] > 0:
        # Fallback si la base es negativa (ej: ya sacaste más ganancia que el capital puesto)
        total_pct = (total_historical_profit / summary['market_value']) * 100

    total_gain = total_historical_profit
    
    # --- ASIGNACIÓN DE VARIABLES Y ESTILOS ---
    market_value = summary['market_value']
    day_gain = summary['day_gain_usd']
    day_pct = summary['day_pct']
    
    day_text = "Ganancia del Día" if day_gain >= 0 else "Pérdida del Día"
    total_text = "Ganancia Total" if total_gain >= 0 else "Pérdida Total"
    
    day_cls = "text-success" if day_gain >= 0 else "text-danger"
    day_icon = "bi-arrow-up-right-circle-fill" if day_gain >= 0 else "bi-arrow-down-right-circle-fill"
    total_cls = "text-success" if total_gain >= 0 else "text-danger"
    total_icon = "bi-graph-up-arrow" if total_gain >= 0 else "bi-graph-down-arrow"

    
    # --- FUNCIÓN LOCAL PARA GENERAR TARJETA ---
    def create_kpi_card(title, value, value_class, icon, detail_text, detail_value=None, detail_class=None):
        value_str = f"${value:,.2f}"
        
        detail_content = html.Small([
            html.I(className=f"bi {icon} me-1"),
            detail_text, 
            html.Span(f" ({detail_value:+.2f}%)" if detail_value is not None else "", className=f"{detail_class} fw-bold")
        ], className=f"d-block text-muted small")
        
        return dbc.Col(
            dbc.Card(
                dbc.CardBody([
                    html.H5(title, className="card-title text-info"),
                    html.H2(value_str, className=f"card-value {value_class} fw-bold mb-2"),
                    detail_content
                ]),
                # Usamos h-100 para asegurar que ambas filas tengan la misma altura si es necesario
                className="metric-card h-100 shadow-sm" 
            ),
            # Ocupa la mitad del espacio en la fila
            lg=6, md=6, sm=12 
        )

    # 🚨 REORDENAMIENTO EN DOS FILAS 🚨
    
    # ROW 1: Principal (Valor Total y Capital Neto)
    row_1_cards = [
        # 1. Valor Total Portafolio
        create_kpi_card("Valor Total Portafolio", market_value, "text-white", "bi-wallet", "Valor de Mercado Actual", detail_value=None, detail_class="text-white"),
        
        # 2. Capital Neto Introducido
        create_kpi_card(
            "Capital Neto Introducido", 
            net_investment_base, 
            "text-white", 
            "bi-cash-coin", 
            "Costo Adquisición - P/L Realizado"
        )
    ]
    
    # ROW 2: Rendimiento (Histórico y Diario)
    row_2_cards = [
        # 3. Rendimiento Histórico
        create_kpi_card("Rendimiento Histórico", total_gain, total_cls, total_icon, total_text, detail_value=total_pct, detail_class=total_cls),
        
        # 4. Cambio del Día
        create_kpi_card("Cambio del Día", day_gain, day_cls, day_icon, day_text, detail_value=day_pct, detail_class=day_cls)
    ]
    
    # --- RESULTADO FINAL DEL LAYOUT ---
    final_layout = html.Div([
        # Fila 1
        dbc.Row(row_1_cards, className="g-4 mb-4"),
        # Fila 2
        dbc.Row(row_2_cards, className="g-4 mb-4"),
    ])


    # --- FUNCIÓN LOCAL PARA GENERAR GRÁFICOS (CORREGIDA: LEYENDA HORIZONTAL) ---
    def get_figure_data(df, title, colors): 
        if df.empty: return create_empty_pie(title)
        
        fig = go.Figure(data=[go.Pie(
            labels=df['name'], 
            values=df['value'], 
            hole=0.5, # Agujero un poco más grande para elegancia
            marker=dict(colors=colors, line=dict(color='#1e1e1e', width=2)),
            textinfo='percent',
            textposition='inside',
            insidetextorientation='horizontal',
            hovertemplate='<b>%{label}</b><br>Valor: $%{value:,.2f}<br>Participación: %{percent}<extra></extra>'
        )])

        fig.update_layout(
            template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)", 
            plot_bgcolor="rgba(0,0,0,0)",
            
            # --- CONFIGURACIÓN DE LEYENDA HORIZONTAL ---
            showlegend=True,
            legend=dict(
                orientation="h",      # Horizontal obligatoria
                yanchor="top",        # Anclar la parte superior de la leyenda...
                y=-0.15,              # ...un poco más abajo del gráfico (negativo)
                xanchor="center",     # Centrar horizontalmente
                x=0.5,                # En la mitad del componente
                bgcolor="rgba(0,0,0,0)", 
                font=dict(size=11, color="#ccc"),
                # NOTA: Eliminamos 'itemwidth' para que fluya natural, no en columnas
            ),
            
            # --- MÁRGENES ---
            # Aumentamos 'b' (bottom) a 80 o 100 para dar espacio a las 
            # líneas de texto de la leyenda sin que se corten.
            margin=dict(t=20, b=80, l=10, r=10), 
            
            font=dict(family="sans-serif", color="white")
        )
        return fig
    # Lógica de creación de gráficos (usando las variables calculadas en el else)
    # Las definiciones completas de estas funciones deben estar en tu archivo.
    fig_stock = get_figure_data(df_stock, "Valor por Activo", px.colors.qualitative.Pastel)
    fig_industry = get_figure_data(df_industry, "Distribución por Industria", px.colors.qualitative.Vivid)
    fig_type = get_figure_data(df_asset_type, "Distribución por Tipo", px.colors.qualitative.Bold)
    
    return final_layout, fig_stock, fig_industry, fig_type

# 3. Generar Cards (Renderiza la cuadrícula de stocks con Heatmap y ordenación)
# pages/investments/investments_assets.py

# 3. Generar Cards (Renderiza la cuadrícula de stocks con Heatmap y ordenación)
# 3. Generar Cards (Renderiza la cuadrícula de stocks con Heatmap y ordenación)
@callback(
    Output("assets-grid", "children"),
    [Input("assets-data-cache", "data"),
     Input("assets-sort-dropdown", "value"),
     Input("assets-display-tabs", "active_tab")] 
)
def render_asset_cards(json_assets, sort_value, active_tab):
  
    # 1. Validar si el JSON es válido
    if not json_assets or json_assets == '{}':
        return html.Div("Cargando datos...", className="text-muted text-center")

    stocks = json.loads(json_assets)
    
    if not stocks:
        return html.Div([
            html.I(className="bi bi-inbox fs-1 d-block mb-3"),
            "No tienes posiciones de inversión registradas.",
            html.Br(),
            html.Small("Usa el botón '+ Agregar Posición' para comenzar.", className="text-info")
        ], className="text-muted text-center p-5")

    # 3. Crear DataFrame
    df_stocks = pd.DataFrame(stocks)
    
    if 'asset_type' not in df_stocks.columns:
        return html.Div("Error estructural: Falta asset_type", className="text-danger")
        

    # 4. Mapeo de Tipos de Activos
    # ATENCIÓN: He añadido .strip() y .upper() para hacer el filtro más robusto
    df_stocks['Display_Type'] = df_stocks['asset_type'].apply(lambda x: 
        'ETF' if str(x).upper().strip() == 'ETF' else (
        'CRYPTO_FOREX' if str(x).upper().strip() in ['CRYPTO', 'CRYPTO_FOREX', 'FOREX'] else (
        'STOCK' if str(x).upper().strip() == 'STOCK' else 'OTHER'))
    )

    # 5. Filtrado por Pestaña
    rows_before = len(df_stocks)
    if active_tab == 'tab-stocks':
        df_stocks = df_stocks[df_stocks['Display_Type'] == 'STOCK']
    elif active_tab == 'tab-etfs':
        df_stocks = df_stocks[df_stocks['Display_Type'] == 'ETF']
    elif active_tab == 'tab-crypto':
        df_stocks = df_stocks[df_stocks['Display_Type'] == 'CRYPTO_FOREX']
    elif active_tab == 'tab-other':
        df_stocks = df_stocks[df_stocks['Display_Type'] == 'OTHER']
    
    if df_stocks.empty:
        return html.Div(f"No hay activos en la categoría {active_tab}.", className="text-muted text-center p-4")

    # 6. Ordenación
    if sort_value == 'ticker_asc': df_stocks = df_stocks.sort_values(by='ticker', ascending=True)
    elif sort_value == 'ticker_desc': df_stocks = df_stocks.sort_values(by='ticker', ascending=False)
    elif sort_value == 'market_value_desc': df_stocks = df_stocks.sort_values(by='market_value', ascending=False)
    elif sort_value == 'market_value_asc': df_stocks = df_stocks.sort_values(by='market_value', ascending=True)
    elif sort_value == 'day_change_pct_desc': df_stocks = df_stocks.sort_values(by='day_change_pct', ascending=False)
    elif sort_value == 'day_change_pct_asc': df_stocks = df_stocks.sort_values(by='day_change_pct', ascending=True)
    elif sort_value == 'total_gain_pct_desc': df_stocks = df_stocks.sort_values(by='total_gain_pct', ascending=False)
    elif sort_value == 'total_gain_pct_asc': df_stocks = df_stocks.sort_values(by='total_gain_pct', ascending=True)
        
    # 7. Generar las tarjetas
    cards = []
    for index, s in df_stocks.iterrows(): 
        total_color = "text-success" if s['total_gain'] >= 0 else "text-danger"
        total_sign = "+" if s['total_gain'] >= 0 else ""
        day_color = "text-success" if s['day_change_pct'] >= 0 else "text-danger"
        day_sign = "+" if s['day_change_pct'] >= 0 else ""
        
        # Corrección de división por cero
        if (1 + s['day_change_pct']/100) != 0:
            prev_val = s['market_value'] / (1 + s['day_change_pct']/100)
            day_gain_usd = s['market_value'] - prev_val
        else: day_gain_usd = 0.0

        display_ticker = s.get('display_ticker', s['ticker']) 
        display_name = s.get('name', display_ticker)
        card_bg_class = 'bg-heatmap-positive' if s['day_change_pct'] >= 0 else 'bg-heatmap-negative'

        card = dbc.Col(
            dbc.Card([
                dbc.CardBody([
                    html.Div([
                        html.H3(display_ticker, className="fw-bold mb-0 text-white"),
                        html.Small(display_name, className="text-muted text-uppercase fw-bold", style={"fontSize": "0.75rem"}),
                        
                        dbc.Row([
                            dbc.Col(html.P(f"Unidades: {smart_format(s['shares'])}", className="text-white fw-bold mt-1 mb-0", style={"fontSize": "0.75rem"}), width="auto"),
                            dbc.Col(html.P(f"@{s['avg_price']:,.2f}", className="text-muted fw-bold mt-1 mb-0", style={"fontSize": "0.75rem"}), width="auto", className="ms-auto")
                        ], className="g-0 justify-content-between mb-2")
                    ], className="mb-3"), 

                    html.Div([
                        html.H4(f"${s['market_value']:,.2f}", className="fw-bold mb-0 text-white"),
                        html.Small(f"${s['current_price']:,.2f}", className="text-muted") 
                    ], className="mb-3 text-center"), 

                    html.Hr(className="border-secondary my-2"),
                    html.Small("Rendimiento:", className="text-muted fw-bold mb-2 d-block"),

                    dbc.Row([
                        # Cambiado width=4 a width=3 para dar más espacio a los números
                        dbc.Col("Hoy:", width=3, className="text-muted small"),
                        dbc.Col([
                            html.Span(f"{day_sign}${day_gain_usd:,.2f}", className=f"fw-bold {day_color} me-2"),
                            # Eliminado el '+' del formato f-string porque day_sign ya lo trae
                            html.Small(f"({day_sign}{s['day_change_pct']:.2f}%)", className=f"{day_color}")
                        ], width=9, className="text-end") # Cambiado width=8 a width=9
                    ], className="mb-1 g-0"),

                    dbc.Row([
                        # Cambiado width=4 a width=3
                        dbc.Col("Total:", width=3, className="text-muted small"),
                        dbc.Col([
                            html.Span(f"{total_sign}${s['total_gain']:,.2f}", className=f"fw-bold {total_color} me-2"),
                            # Eliminado el '+' del formato f-string porque total_sign ya lo trae
                            html.Small(f"({total_sign}{s['total_gain_pct']:.2f}%)", className=f"{total_color}")
                        ], width=9, className="text-end") # Cambiado width=8 a width=9
                    ], className="g-0"),
                ]),
                html.Div(id={'type': 'stock-card', 'index': s['id']}, className="stretched-link") 
            ], className=f"data-card h-100 zoom-on-hover shadow-sm {card_bg_class}", style={"cursor": "pointer"}),
            lg=3, md=4, sm=6 
        )
        cards.append(card)
        
    return cards


# 4. Abrir Detalle (Click en Card) - MODIFICADO
@callback(
    [Output("detail-asset-modal", "is_open"),
     Output("detail-asset-title", "children"),
     Output("detail-asset-body", "children"),
     Output("asset-viewing-id", "data"),
     Output("trans-asset-ticker-store", "data")], 
     
    [Input({'type': 'stock-card', 'index': ALL}, 'n_clicks'),
     Input("btn-asset-delete", "n_clicks"),
     Input("btn-open-sell-modal", "n_clicks"), 
     Input("btn-open-buy-modal", "n_clicks"),
     Input("btn-open-edit-modal", "n_clicks")], 
     
    [State("asset-viewing-id", "data")],
    prevent_initial_call=True
)
def handle_card_click(n_clicks, delete, open_sell, open_buy, open_edit, viewing_id):
    trig = ctx.triggered_id
    
    # --- LÓGICA DE CIERRE ---
    # Si presionamos Editar, Eliminar, Vender o Comprar, cerramos este modal
    # PERO usamos 'no_update' en los Stores para NO PERDER el ID seleccionado.
    if trig in ["btn-asset-delete", "btn-open-sell-modal", "btn-open-buy-modal", "btn-open-edit-modal"]:
        return False, no_update, no_update, no_update, no_update
    
    # --- LÓGICA DE APERTURA ---
    if isinstance(trig, dict) and trig['type'] == 'stock-card':
        if not ctx.triggered[0]['value']: return no_update, no_update, no_update, no_update, no_update

        asset_id = trig['index']
        data = dm.get_investment_detail(asset_id) 

        if not data:
            return True, "Error", html.P("No se pudo cargar la información."), asset_id, None

        # Variables de estilo para el P&L
        gain_color = "text-success" if data['total_gain'] >= 0 else "text-danger"
        day_color = "text-success" if data['day_change'] >= 0 else "text-danger"
        day_sign = "+" if data['day_change'] >= 0 else ""

        # --- CONSTRUCCIÓN DEL CUERPO DEL MODAL (Body) ---
        modal_content = html.Div([
            
            # 1. PRECIO ACTUAL Y CAMBIO DEL DÍA
            dbc.Row([
                dbc.Col([
                    html.H1(f"${data['current_price']:,.2f}", className="display-4 fw-bold mb-0"),
                    html.H5(f"{day_sign}{data['day_change']:,.2f} ({day_sign}{data['day_change_pct']:.2f}%)", className=f"mb-0 {day_color}")
                ], width=12, className="text-center mb-4")
            ]),
            
            # BOTONES DE ACCIÓN (VENDER / COMPRAR)
            dbc.Row([
                dbc.Col(
                    dbc.Button("Vender", id="btn-open-sell-modal", color="danger", outline=True, className="w-100"), 
                    width=6
                ),
                dbc.Col(
                    dbc.Button("Comprar", id="btn-open-buy-modal", color="success", outline=True, className="w-100"), 
                    width=6
                ),
            ], className="g-2 mb-4"),
            
            # 2. CARD: MI POSICIÓN
            dbc.Card([
                dbc.CardHeader("Mi Posición", className="fw-bold small text-uppercase"),
                dbc.CardBody([
                    dbc.Row([
                        dbc.Col([html.Small("Tipo:", className="text-muted d-block"),html.H6(data.get('asset_type', 'N/A'), className="fw-bold text-info mb-3")], width=6),
                        dbc.Col([html.Small("Sector:", className="text-muted d-block"),html.H6(data.get('sector', 'N/A'), className="fw-bold text-info mb-3")], width=6)
                    ]),
                    
                    dbc.Row([
                        dbc.Col([html.Small("Valor Mercado", className="text-muted d-block"),html.H4(f"${data['market_value']:,.2f}", className="fw-bold")], width=6),
                        dbc.Col([html.Small("Ganancia Total", className="text-muted d-block"),html.H4([f"${data['total_gain']:,.2f} ",html.Small(f"({data['total_gain_pct']:+.2f}%)", className="fs-6 fw-normal", style={'color': gain_color})])], width=6)
                    ], className="mb-2"),
                    html.Hr(className="my-2"),
                    dbc.Row([
                        dbc.Col([html.B("Unidades:"), f" {smart_format(data['shares'])}"], width=6, className="small"),
                        dbc.Col([html.B("Costo Prom:"), f" ${data['avg_price']:,.2f}"], width=6, className="small text-end"),
                    ])
                ])
            ], className="mb-4 shadow-sm border-light"),


            # 3. ESTADÍSTICAS CLAVE
            html.H6("Estadísticas Clave", className="mb-3 border-bottom pb-2 text-info"),
            create_range_bar(
                min_val=data['day_low'], max_val=data['day_high'], current_price=data['current_price'], label="Rango Día"
            ),
            create_range_bar(
                min_val=data['fiftyTwo_low'], max_val=data['fiftyTwo_high'], current_price=data['current_price'], label="Rango 52 Semanas"
            ),
            # 3. ESTADÍSTICAS CLAVE
            # Fila 1: Market Cap y P/E Ratio
            dbc.Row([
                # COLUMNA IZQUIERDA (Con línea divisoria 'border-end')
                dbc.Col([
                    # 1. Market Cap
                    html.Div([
                        html.Small("Market Cap", className="text-muted d-block"),
                        html.Span(f"${data.get('market_cap'):,.0f}M" if data.get('market_cap') else "-", className="fw-bold")
                    ], className="mb-3"),
                    
                    # 2. Div Yield
                    html.Div([
                        html.Small("Div Yield", className="text-muted d-block"),
                        html.Span(f"{data['dividend_yield']:.2f}%" if data['dividend_yield'] else "-", className="fw-bold")
                    ]),
                ], width=6, className="border-end border-secondary"), # <--- AQUÍ ESTÁ LA LÍNEA
                
                # COLUMNA DERECHA (Con padding 'ps-3' para separarse de la línea)
                dbc.Col([
                    # 3. P/E Ratio
                    html.Div([
                        html.Small("P/E Ratio", className="text-muted d-block"),
                        html.Span(f"{data['pe_ratio']:.2f}" if data['pe_ratio'] else "-", className="fw-bold")
                    ], className="mb-3 ps-3"), # ps-3 = padding-start: 3 (espacio a la izquierda)
                    
                    # 4. Beta
                    html.Div([
                        html.Small("Beta (Volatilidad)", className="text-muted d-block"),
                        html.Span(f"{data['beta']:.2f}" if data['beta'] else "-", className="fw-bold")
                    ], className="ps-3"),
                ], width=6),
            ]),
            # 4. INFORMACIÓN DE ORIGEN
            html.H6("Información de Origen", className="mb-3 mt-3 border-bottom pb-2 text-info"),
            dbc.Row([
                dbc.Col([html.Small("País de Origen:", className="text-muted d-block"),html.Span(data['country'], className="fw-bold")], width=6, className="mb-3"),
            ]),
            html.P(data['summary'], className="small text-muted fst-italic"),

            # 5. NOTICIAS RECIENTES
            html.H6("Noticias Recientes (7 Días)", className="mb-2 mt-3 border-bottom pb-2 text-info"),
            dbc.ListGroup([
                dbc.ListGroupItem([
                    html.A(n['headline'], href=n['url'], target="_blank", className="text-white text-decoration-none fw-bold"),
                    html.Small(f" - Fuente: {n['source']}", className="text-muted d-block")
                ], className="list-group-item-action bg-transparent border-secondary py-2") 
                for n in data['news']
            ]) if data['news'] else html.P("No hay noticias recientes (últimos 7 días).", className="small text-muted"),


        ], id="stock-modal-content-scroll", 
        style={"maxHeight": "65vh", "overflowY": "auto", "overflowX": "hidden", "paddingRight": "10px"})
        
        display_ticker = data.get('display_ticker', data['ticker'])
        
        real_name = data.get('real_name', display_ticker) 

        title = html.Div([
            # 1. Display Ticker (Grande, Negrita, Blanco)
            html.H2(display_ticker, className="mb-0 fw-bold d-inline-block me-2 text-white"),
            
            # 2. Real Name (Pequeño, Gris)
            html.Small(real_name, className="text-muted", style={"fontSize": "1rem", "fontWeight": "normal"})
        ], className="d-flex align-items-baseline") # Alineados a la base
        
        # El ticker técnico para operaciones sigue siendo el raw
        ticker_real = data['ticker'] 
        
        return True, title, modal_content, asset_id, ticker_real

    return no_update, no_update, no_update, no_update, no_update

# 5. Ejecutar Eliminación y Trigger Refresh
@callback(
    [Output("asset-update-signal", "data", allow_duplicate=True),
     Output("asset-viewing-id", "data", allow_duplicate=True),
     Output("asset-delete-confirm-modal", "is_open", allow_duplicate=True),
     Output("asset-toast", "is_open", allow_duplicate=True),
     Output("asset-toast", "children", allow_duplicate=True),
     Output("asset-toast", "icon", allow_duplicate=True)],
    Input("btn-del-confirm", "n_clicks"),
    [State("asset-update-signal", "data"),
     State("asset-viewing-id", "data")], 
    prevent_initial_call=True
)
def execute_delete_and_refresh(n_clicks, signal, asset_id):
    if n_clicks and asset_id is not None:
        success, msg = dm.delete_investment(asset_id)
        
        if success:
            return ((signal or 0) + 1), None, False, *ui_helpers.mensaje_alerta_exito("success", msg)
        else:
            return no_update, no_update, False, *ui_helpers.mensaje_alerta_exito("danger", msg)

    return no_update, no_update, no_update, no_update, no_update, no_update


# 6. Toggle Modal de Confirmación
@callback(
    Output("asset-delete-confirm-modal", "is_open"),
    [Input("btn-asset-delete", "n_clicks"),
     Input("btn-del-cancel", "n_clicks"),
     Input("btn-del-confirm", "n_clicks")], 
    State("asset-delete-confirm-modal", "is_open"),
    prevent_initial_call=True
)
def toggle_delete_confirm_modal(trigger_del, cancel_del, confirm_del, is_open):
    trig_id = ctx.triggered_id
    
    if trig_id == "btn-asset-delete":
        return True
    
    if trig_id in ["btn-del-cancel", "btn-del-confirm"]:
        return False
        
    return is_open

# 7. Abrir y Precargar Modal de Edición
@callback(
    [Output("edit-asset-modal", "is_open"),
     Output("edit-asset-ticker", "value"),
     Output("edit-asset-shares", "value"),
     Output("edit-asset-total-investment", "value"),
     Output("edit-asset-modal-msg", "children")], 
    [Input("btn-open-edit-modal", "n_clicks"), 
     Input("btn-edit-cancel", "n_clicks"),
     Input("btn-edit-save", "n_clicks")],
    State("asset-viewing-id", "data"),
    prevent_initial_call=True
)
def toggle_edit_modal(open_n, cancel_n, save_n, asset_id):
    trig_id = ctx.triggered_id
    
    if trig_id in ["btn-edit-cancel", "btn-edit-save"]:
        return False, no_update, no_update, no_update, ""
        
    if trig_id == "btn-open-edit-modal" and asset_id is not None:
        data = dm.get_investment_by_id(asset_id)
        
        if data:
            return True, data['ticker'], data['shares'], data['total_investment'], ""
            
    return no_update, no_update, no_update, no_update, no_update


# 8. Guardar Cambios de Edición
# 8. Guardar Cambios de Edición (CON TOAST)
@callback(
    [Output("asset-update-signal", "data", allow_duplicate=True),
     Output("edit-asset-modal", "is_open", allow_duplicate=True), # 1. Controlar Modal
     Output("asset-toast", "is_open", allow_duplicate=True),      # 2. Controlar Toast
     Output("asset-toast", "children", allow_duplicate=True),     # 3. Mensaje Toast
     Output("asset-toast", "icon", allow_duplicate=True),         # 4. Icono Toast
     Output("edit-asset-modal-msg", "children", allow_duplicate=True)], # 5. Mensaje interno
    Input("btn-edit-save", "n_clicks"),
    [State("edit-asset-shares", "value"),
     State("edit-asset-total-investment", "value"),
     State("asset-viewing-id", "data"), 
     State("asset-update-signal", "data")],
    prevent_initial_call=True
)
def save_edited_asset(n_clicks, shares, total_investment, asset_id, signal):
    if not n_clicks: 
        return no_update, no_update, no_update, no_update, no_update, no_update

    if asset_id is None:
        return no_update, True, False, "", "", html.Span("Error ID.", className="text-danger")

    if not all([shares, total_investment]):
        return no_update, True, False, "", "", html.Span("Faltan datos.", className="text-danger")
    
    try:
        shares_f = float(shares)
        total_investment_f = float(total_investment)
        if shares_f <= 0 or total_investment_f <= 0:
             return no_update, True, False, "", "", html.Span("Valores positivos requeridos.", className="text-danger")
    except ValueError:
         return no_update, True, False, "", "", html.Span("Números inválidos.", className="text-danger")

    # --- ACTUALIZAR DB ---
    success, msg = dm.update_investment(asset_id, shares_f, total_investment_f)
    
    if success:
        # ✅ ÉXITO
        return (signal or 0) + 1, False, *ui_helpers.mensaje_alerta_exito("success", "Posición actualizada."), ""
    else:
        # ❌ ERROR
        return no_update, True, *ui_helpers.mensaje_alerta_exito("danger", f"Error: {msg}"), ""

# X. Callback de Visibilidad: Oculta el Loader y Muestra el Dashboard cuando hay datos
# X. Callback de Visibilidad: Oculta el Loader y Muestra el Dashboard cuando hay datos
@callback(
    [Output("initial-loader", "style"),
     Output("main-dashboard-view", "style")],
    Input("assets-data-cache", "data")
)
def toggle_dashboard_visibility(json_assets):
    loader_style = {
        "height": "60vh", "display": "flex", 
        "flexDirection": "column", "justifyContent": "center", "alignItems": "center"
    }
    
    # CORRECCIÓN:
    # Solo mostramos el loader si es None o '{}' (estado inicial por defecto).
    # Si json_assets es '[]', significa que la DB respondió "0 activos", 
    # por lo tanto DEBEMOS ocultar el loader y mostrar el dashboard.
    
    if json_assets is None or json_assets == '{}':
        return loader_style, {'display': 'none'}
    
    # Si llega aquí, es porque hay datos o es una lista vacía '[]' (usuario nuevo).
    # En ambos casos, queremos ver el dashboard.
    return {'display': 'none'}, {'display': 'block', 'animation': 'fadein 1s'}