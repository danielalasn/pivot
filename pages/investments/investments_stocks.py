# pages/investments_stocks.py
import dash
from dash import dcc, html, callback, Input, Output, State, no_update, ctx, ALL
import dash_bootstrap_components as dbc
import backend.data_manager as dm
from utils import ui_helpers

# --- MODAL: AÑADIR STOCK ---
add_stock_modal = dbc.Modal([
    dbc.ModalHeader("Agregar Acción al Portafolio"),
    dbc.ModalBody([
        dbc.Label("Ticker Symbol (Ej: AAPL, TSLA, VO)"),
        dbc.Input(id="new-stock-ticker", placeholder="SYMBOL", type="text", className="mb-3"),
        
        dbc.Label("Cantidad de Acciones"),
        dbc.Input(id="new-stock-shares", placeholder="0.0", type="number", className="mb-3"),
        
        dbc.Label("Precio Promedio de Compra (Avg Price)"),
        dbc.Input(id="new-stock-price", placeholder="0.00", type="number", className="mb-3"),
        
        html.Div(id="stock-modal-msg", className="text-center")
    ]),
    dbc.ModalFooter([
        dbc.Button("Cancelar", id="btn-stock-cancel", outline=True),
        dbc.Button("Guardar", id="btn-stock-save", color="success", className="ms-2"),
    ])
], id="add-stock-modal", is_open=False, centered=True, size="sm")

# --- MODAL: DETALLE STOCK (Al hacer clic en la card) ---
detail_stock_modal = dbc.Modal([
    dbc.ModalHeader(dbc.ModalTitle(id="detail-stock-title")),
    dbc.ModalBody(id="detail-stock-body"),
    dbc.ModalFooter([
        dbc.Button("Eliminar del Portafolio", id="btn-stock-delete", color="danger", outline=True),
        dbc.Button("Cerrar", id="btn-stock-close-detail", color="secondary", className="ms-auto"),
    ])
], id="detail-stock-modal", is_open=False, centered=True, size="md")


# --- LAYOUT ---
layout = dbc.Container([
    dcc.Store(id="stock-update-signal", data=0),
    dcc.Store(id="stock-viewing-id", data=None),
    ui_helpers.get_feedback_toast("stock-toast"),

    add_stock_modal,
    detail_stock_modal,

    dbc.Row([
        dbc.Col(
            dbc.Button("+ Agregar Posición", id="btn-open-stock-modal", color="primary", className="mb-4"),
            width=12
        )
    ]),

    dcc.Loading(
        id="loading-stocks",
        type="circle",    # Opciones: 'graph', 'cube', 'circle', 'dot', 'default'
        color="#2A9FD6",  # Color azul del tema Cyborg
        children=[
            # Este es tu contenedor original
            dbc.Row(id="stocks-grid", className="g-4", style={"minHeight": "200px"}) 
        ]
    )

], fluid=True, className="py-3")


# --- CALLBACKS ---

# 1. Abrir/Cerrar Modal Agregar
@callback(
    Output("add-stock-modal", "is_open"),
    [Input("btn-open-stock-modal", "n_clicks"), Input("btn-stock-cancel", "n_clicks"), Input("stock-update-signal", "data")],
    State("add-stock-modal", "is_open"),
    prevent_initial_call=True
)
def toggle_add_modal(open_n, cancel_n, signal, is_open):
    if ctx.triggered_id == "stock-update-signal": return False
    if ctx.triggered_id == "btn-stock-cancel": return False
    return not is_open

# 2. Guardar Stock
@callback(
    Output("stock-update-signal", "data"),
    Output("stock-modal-msg", "children"),
    Input("btn-stock-save", "n_clicks"),
    State("new-stock-ticker", "value"),
    State("new-stock-shares", "value"),
    State("new-stock-price", "value"),
    State("stock-update-signal", "data"),
    prevent_initial_call=True
)
def save_stock(n_clicks, ticker, shares, price, signal):
    if not all([ticker, shares, price]):
        return no_update, html.Span("Faltan datos", className="text-danger")
    
    success, msg = dm.add_stock(ticker, float(shares), float(price))
    if success:
        return (signal + 1), html.Span(msg, className="text-success")
    else:
        return no_update, html.Span(msg, className="text-danger")

# 3. Generar Cards (CON DATOS EN VIVO)
# pages/investments/investments_stocks.py - Reemplazar Callback 3

# pages/investments/investments_stocks.py

# 3. Generar Cards (DISEÑO VERTICAL CORREGIDO)
@callback(
    Output("stocks-grid", "children"),
    Input("url", "pathname"),
    Input("stock-update-signal", "data")
)
def render_stock_cards(pathname, signal):
    stocks = dm.get_stocks_data() 
    
    if not stocks:
        return html.Div("No tienes acciones registradas.", className="text-muted text-center")

    cards = []
    for s in stocks:
        # --- CÁLCULOS DE VISUALIZACIÓN ---
        total_color = "text-success" if s['total_gain'] >= 0 else "text-danger"
        total_sign = "+" if s['total_gain'] >= 0 else ""
        
        day_pct = s['day_change_pct']
        day_color = "text-success" if day_pct >= 0 else "text-danger"
        day_sign = "+" if day_pct >= 0 else ""
        
        # Cálculo de ganancia diaria en $
        if (1 + day_pct/100) != 0:
            prev_val = s['market_value'] / (1 + day_pct/100)
            day_gain_usd = s['market_value'] - prev_val
        else:
            day_gain_usd = 0.0

        # Evitar duplicar nombre si es igual al ticker (limpieza visual)
        display_name = s['name'] if s['name'] != s['ticker'] else ""

        # --- ESTRUCTURA DE LA CARD (VERTICAL) ---
        card = dbc.Col(
            dbc.Card([
                dbc.CardBody([
                    # 1. ENCABEZADO: Ticker y Nombre (Arriba a la izquierda)
                    html.Div([
                        html.H2(s['ticker'], className="fw-bold mb-0 text-white"),
                        html.Small(display_name, className="text-muted text-uppercase fw-bold", style={"fontSize": "0.75rem"})
                    ], className="mb-4"), # Margen inferior para separar del monto

                    # 2. VALOR TOTAL (Grande y Centrado o Izquierda, con ancho completo)
                    html.Div([
                        html.H1(f"${s['market_value']:,.2f}", className="display-6 fw-bold mb-0 text-white"),
                        html.Small(f"${s['current_price']:,.2f} / acción", className="text-muted")
                    ], className="mb-4 text-center"), # Centrado para destacar el valor

                    html.Hr(className="border-secondary my-2"),
                    
                    # 3. SECCIÓN DE RESULTADOS (Compacta)
                    html.Small("Rendimiento:", className="text-muted fw-bold mb-2 d-block"),

                    # Fila: Hoy
                    dbc.Row([
                        dbc.Col("Hoy:", width=4, className="text-muted small"),
                        dbc.Col([
                            html.Span(f"{day_sign}${day_gain_usd:,.2f}", className=f"fw-bold {day_color} me-2"),
                            html.Small(f"({day_sign}{day_pct:.2f}%)", className=f"{day_color}")
                        ], width=8, className="text-end")
                    ], className="mb-1"),

                    # Fila: Total Histórico
                    dbc.Row([
                        dbc.Col("Total:", width=4, className="text-muted small"),
                        dbc.Col([
                            html.Span(f"{total_sign}${s['total_gain']:,.2f}", className=f"fw-bold {total_color} me-2"),
                            html.Small(f"({total_sign}{s['total_gain_pct']:+.2f}%)", className=f"{total_color}")
                        ], width=8, className="text-end")
                    ]),
                    
                ]),
                # Link invisible para hacer click en toda la tarjeta
                html.Div(id={'type': 'stock-card', 'index': s['id']}, className="stretched-link") 
            ], className="data-card h-100 zoom-on-hover shadow-sm", style={"cursor": "pointer"}),
            lg=4, md=6, sm=12
        )
        cards.append(card)
        
    return cards
# 4. Abrir Detalle (Click en Card)
# pages/investments/investments_stocks.py

# 4. Abrir Detalle (Click en Card) - VERSIÓN MEJORADA
# pages/investments/investments_stocks.py

# 4. Abrir Detalle (Click en Card)
# pages/investments/investments_stocks.py

# 4. Abrir Detalle (Click en Card)
@callback(
    Output("detail-stock-modal", "is_open"),
    Output("detail-stock-title", "children"),
    Output("detail-stock-body", "children"),
    Output("stock-viewing-id", "data"),
    Input({'type': 'stock-card', 'index': ALL}, 'n_clicks'),
    Input("btn-stock-close-detail", "n_clicks"),
    Input("btn-stock-delete", "n_clicks"),
    State("stock-viewing-id", "data"),
    prevent_initial_call=True
)
def handle_card_click(n_clicks, close, delete, viewing_id):
    trig = ctx.triggered_id
    
    # CERRAR
    if trig == "btn-stock-close-detail":
        return False, no_update, no_update, None
    
    # BORRAR
    if trig == "btn-stock-delete" and viewing_id:
        dm.delete_investment(viewing_id)
        return False, no_update, no_update, None 

    # ABRIR
    if isinstance(trig, dict) and trig['type'] == 'stock-card':
        if not ctx.triggered[0]['value']: return no_update, no_update, no_update, no_update

        stock_id = trig['index']
        data = dm.get_investment_detail(stock_id)

        if not data:
            return True, "Error", html.P("No se pudo cargar la información."), stock_id

        # Colores
        gain_color = "text-success" if data['total_gain'] >= 0 else "text-danger"
        day_color = "text-success" if data['day_change'] >= 0 else "text-danger"
        day_sign = "+" if data['day_change'] >= 0 else ""

        # --- LAYOUT DEL CONTENIDO DEL MODAL ---
        # pages/investments/investments_stocks.py - Dentro de Callback 4

# ... (El código anterior se mantiene hasta aquí) ...

        # --- LAYOUT DEL CONTENIDO DEL MODAL ---
        modal_content = html.Div([
            # 1. PRECIO GRANDE
            dbc.Row([
                dbc.Col([
                    html.H1(f"${data['current_price']:,.2f}", className="display-4 fw-bold mb-0"),
                    html.H5(f"{day_sign}{data['day_change']:,.2f} ({day_sign}{data['day_change_pct']:.2f}%)", className=f"mb-0 {day_color}")
                ], width=12, className="text-center mb-4")
            ]),

            # 2. MI POSICIÓN (Compacta)
            dbc.Card([
                dbc.CardHeader("Mi Posición", className="fw-bold small text-uppercase"),
                dbc.CardBody([
                    dbc.Row([
                        dbc.Col([
                            html.Small("Valor Mercado", className="text-muted d-block"),
                            html.H4(f"${data['market_value']:,.2f}", className="fw-bold")
                        ], width=6),
                        dbc.Col([
                            html.Small("Ganancia Total", className="text-muted d-block"),
                            html.H4([
                                f"${data['total_gain']:,.2f} ",
                                html.Small(f"({data['total_gain_pct']:+.2f}%)", className="fs-6 fw-normal")
                            ], className=f"fw-bold {gain_color}")
                        ], width=6)
                    ], className="mb-2"),
                    html.Hr(className="my-2"),
                    dbc.Row([
                        dbc.Col([html.B("Acciones:"), f" {data['shares']}"], width=6, className="small"),
                        dbc.Col([html.B("Costo Prom:"), f" ${data['avg_price']:,.2f}"], width=6, className="small text-end"),
                    ])
                ])
            ], className="mb-4 shadow-sm border-light"),

            # 3. DATOS DE MERCADO (GRID)
            html.H6("Estadísticas Clave", className="mb-3 border-bottom pb-2 text-info"),
            dbc.Row([
                dbc.Col([
                    html.Small("Rango Día", className="text-muted d-block"),
                    html.Span(f"${data['day_low']:,.2f} - ${data['day_high']:,.2f}")
                ], width=6, className="mb-3"),
                dbc.Col([
                    html.Small("Rango 52 Sem", className="text-muted d-block"),
                    html.Span(f"${data['fiftyTwo_low']:,.2f} - ${data['fiftyTwo_high']:,.2f}")
                ], width=6, className="mb-3"),
                dbc.Col([
                    html.Small("Market Cap", className="text-muted d-block"),
                    html.Span(f"${data['market_cap']:,.0f}M") if data['market_cap'] else "-"
                ], width=4, className="mb-3"),
                dbc.Col([
                    html.Small("P/E Ratio", className="text-muted d-block"),
                    html.Span(f"{data['pe_ratio']:.2f}") if data['pe_ratio'] else "-"
                ], width=4),
                dbc.Col([
                    html.Small("Div Yield", className="text-muted d-block"),
                    html.Span(f"{data['dividend_yield']:.2f}%") if data['dividend_yield'] else "-"
                ], width=4),
                 dbc.Col([
                    html.Small("Beta (Volatilidad)", className="text-muted d-block"),
                    html.Span(f"{data['beta']:.2f}") if data['beta'] else "-"
                ], width=4),
            ]),

            # 4. INFO EXTRA Y SECTOR
            html.H6("Industria y Perfil", className="mb-3 mt-3 border-bottom pb-2 text-info"),
            dbc.Row([
                dbc.Col([
                    html.Small("Sector:", className="text-muted d-block"),
                    html.Span(data['sector'], className="fw-bold")
                ], width=6, className="mb-3"),
                dbc.Col([
                    html.Small("País de Origen:", className="text-muted d-block"),
                    html.Span(data['country'], className="fw-bold")
                ], width=6, className="mb-3"),
            ]),
            html.P(data['summary'], className="small text-muted fst-italic"),

            # 5. SENTIMIENTO INSIDER (NUEVO)
            html.H6("Sentimiento Insider (7 Días)", className="mb-2 mt-3 border-bottom pb-2 text-info"),
            
            dbc.Row(className="mb-3", children=[
                dbc.Col([
                    html.Small("Transacciones:", className="text-muted d-block"),
                    html.Span(data['sentiment'].get('month_data_count', 0), className="fw-bold")
                ], width=4),
                dbc.Col([
                    html.Small("Ratio Neto C/V:", className="text-muted d-block"),
                    html.Span(f"{data['sentiment'].get('avg_net_buy_sell_ratio', 0):.2f}", 
                              className="fw-bold text-warning")
                ], width=4),
                dbc.Col([
                    html.Small("Ratio Compras:", className="text-muted d-block"),
                    html.Span(f"{data['sentiment'].get('avg_buy_ratio', 0) * 100:.1f}%", 
                              className="fw-bold text-warning")
                ], width=4),
                
            ]) if data['sentiment'].get('month_data_count') else html.P("Datos de sentimiento no disponibles (últimos 7 días).", className="small text-muted"),


            # 6. NOTICIAS RECIENTES (NUEVO)
            html.H6("Noticias Recientes (7 Días)", className="mb-2 mt-3 border-bottom pb-2 text-info"),
            
            dbc.ListGroup([
                dbc.ListGroupItem(
                    [
                        html.A(
                            n['headline'],
                            href=n['url'],
                            target="_blank",
                            className="text-white text-decoration-none fw-bold"
                        ),
                        html.Small(f" - Fuente: {n['source']}", className="text-muted d-block")
                    ],
                    className="list-group-item-action bg-transparent border-secondary py-2"
                ) for n in data['news']
            ]) if data['news'] else html.P("No hay noticias recientes (últimos 7 días).", className="small text-muted"),


        # --- ESTILO DEL SCROLLBAR (Max Height) ---
        ], id="stock-modal-body", style={
            "maxHeight": "50vh", 
            "overflowY": "auto", 
            "overflowX": "hidden",
            "paddingRight": "10px"
        })
        # ... (El resto del callback se mantiene) ...
        # Header del Modal
        title = html.Div([
            html.Span(data['name'], className="me-2 h5"),
            dbc.Badge(data['ticker'], color="light", className="text-dark align-top")
        ])
        
        return True, title, modal_content, stock_id

    return no_update, no_update, no_update, no_update

# 5. Trigger refresh al borrar (Helper simple)
@callback(
    Output("stock-update-signal", "data", allow_duplicate=True),
    Input("btn-stock-delete", "n_clicks"),
    State("stock-update-signal", "data"),
    prevent_initial_call=True
)
def trigger_update_on_delete(n, signal):
    return (signal or 0) + 1