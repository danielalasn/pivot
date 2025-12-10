<<<<<<< HEAD
# pages/investments/investments_transactions.py
import dash
from dash import dcc, html, callback, Input, Output, State, no_update, ctx # 🚨 CORRECCIÓN: 'ctx' Importado
import dash_bootstrap_components as dbc
import backend.data_manager as dm
from utils import ui_helpers

# --- MODAL 1: REGISTRAR COMPRA (BUY) ---
# El Store ID 'trans-asset-ticker-store' está en investments_assets.py
def smart_format(val):
    if val is None or val == 0:
        return "0"
    
    try:
        val_f = float(val)
    except:
        return str(val)

    if val_f.is_integer():
        return f"{int(val_f):,}"
    
    val_abs = abs(val_f)
    if val_abs >= 0.01:
        return f"{val_f:,.2f}"
    else:
        # Redondeo a 5 decimales y limpieza
        return f"{val_f:.5f}".rstrip('0').rstrip('.')
    
buy_modal = dbc.Modal([
    dbc.ModalHeader(dbc.ModalTitle(id="buy-modal-title", children="Registrar Compra")),
    dbc.ModalBody([
        html.P(id="buy-modal-shares-info", className="text-muted small"),
        dbc.Label("Unidades a Comprar"),
        dbc.Input(id="buy-shares-amount", type="number", min=0, placeholder="0.0", className="mb-3"),
        
        dbc.Label("Costo por Unidad (Precio de Ejecución)"),
        dbc.Input(id="buy-price", type="number", placeholder="0.00", className="mb-3"),
        
        # Output para Costo Total Estimado
        html.Div(id="buy-total-cost-output", className="mb-2 fw-bold"), 
        
        # Output para Nuevo Costo Promedio
        html.Div(id="buy-new-avg-cost-output", className="mb-3 fw-bold"), 
        
        html.Div(id="buy-msg", className="mt-2 text-center")
    ]),
    dbc.ModalFooter([
        dbc.Button("Cancelar", id="btn-buy-cancel", outline=True),
        dbc.Button("Confirmar Compra", id="btn-buy-confirm", color="success", className="ms-2"),
    ])
], id="buy-modal", is_open=False, centered=True, size="md")


# --- MODAL 2: REGISTRAR VENTA (SELL) ---
sell_modal = dbc.Modal([
    dbc.ModalHeader(dbc.ModalTitle(id="sell-modal-title", children="Registrar Venta")),
    dbc.ModalBody([
        html.P(id="sell-modal-shares-info", className="text-muted small"),
        dbc.Label("Unidades a Vender"),
        dbc.Input(id="sell-shares-amount", type="number", min=0, placeholder="0.0", className="mb-3"),
        
        dbc.Label("Precio de Venta (Precio de Ejecución)"),
        dbc.Input(id="sell-price", type="number", placeholder="0.00", className="mb-3"),
        
        # Valor Total de la Transacción (Output)
        html.Div(id="sell-total-value-output", className="mb-2 fw-bold"),
        
        # P&L Realizado
        html.Div(id="sell-realized-pl-output", className="mb-3 fw-bold"),
        
        html.Div(id="sell-msg", className="mt-2 text-center")
    ]),
    dbc.ModalFooter([
        dbc.Button("Cancelar", id="btn-sell-cancel", outline=True),
        dbc.Button("Confirmar Venta", id="btn-sell-confirm", color="danger", className="ms-2"),
    ])
], id="sell-modal", is_open=False, centered=True, size="md")

# --- EXPORTAR LAYOUT DE MODALES ---
layout = html.Div([
    buy_modal, 
    sell_modal
])


# ==============================================================================
# CALLBACKS DE CONTROL DE MODALES Y LÓGICA DE TRANSACCIÓN
# ==============================================================================

# 1. Abrir Modal de Compra y poblar info (Incluye precarga de precio y limpieza de mensaje)
@callback(
    [Output("buy-modal", "is_open"),
     Output("buy-modal-title", "children"),
     Output("buy-modal-shares-info", "children"),
     Output("buy-msg", "children", allow_duplicate=True), 
     Output("buy-price", "value")], 
    Input("btn-open-buy-modal", "n_clicks"),
    Input("btn-buy-cancel", "n_clicks"),
    State("trans-asset-ticker-store", "data"), 
    prevent_initial_call=True
)
def toggle_buy_modal(open_n, cancel_n, ticker):
    if ctx.triggered_id == "btn-buy-cancel":
        return False, no_update, no_update, "", no_update
        
    if ticker and open_n:
        pos = dm.get_investment_by_ticker(ticker)
        data = dm.get_simulator_ticker_data(ticker)
        
        modal_title = f"Registrar Compra: {ticker}"
        
        # --- CAMBIO AQUÍ: Usamos smart_format ---
        cantidad = pos['shares'] if pos else 0
        shares_info = f"Activo: {ticker}. Unidades actuales: {smart_format(cantidad)}."
        
        current_price = data['current_price'] if data and data['current_price'] else 0
        
        return True, modal_title, shares_info, "", current_price
        
    return no_update, no_update, no_update, no_update, no_update

# 2. Abrir Modal de Venta y poblar info (Incluye precarga de precio y limpieza de mensaje)
@callback(
    [Output("sell-modal", "is_open"),
     Output("sell-modal-title", "children"),
     Output("sell-modal-shares-info", "children"),
     Output("sell-price", "value"),
     Output("sell-msg", "children", allow_duplicate=True)], 
    Input("btn-open-sell-modal", "n_clicks"),
    Input("btn-sell-cancel", "n_clicks"),
    State("trans-asset-ticker-store", "data"), 
    prevent_initial_call=True
)
def toggle_sell_modal(open_n, cancel_n, ticker):
    if ctx.triggered_id == "btn-sell-cancel":
        return False, no_update, no_update, no_update, ""
        
    if ticker and open_n:
        pos = dm.get_investment_by_ticker(ticker)
        data = dm.get_simulator_ticker_data(ticker)

        shares = pos['shares'] if pos else 0
        
        modal_title = f"Registrar Venta: {ticker}"
        
        # --- CAMBIO AQUÍ: Usamos smart_format ---
        shares_info = f"Activo: {ticker}. Unidades disponibles: {smart_format(shares)}."
        
        current_price = data['current_price'] if data and data['current_price'] else 0
        
        return True, modal_title, shares_info, current_price, ""
        
    return no_update, no_update, no_update, no_update, no_update
# 3. Registrar Compra (Actualiza DB y dispara Toast)
@callback(
    [Output("buy-msg", "children"),
     Output("buy-modal", "is_open", allow_duplicate=True),
     Output("asset-update-signal", "data", allow_duplicate=True),
     # OUTPUTS DE TOAST
     Output("asset-toast", "is_open", allow_duplicate=True),
     Output("asset-toast", "children", allow_duplicate=True),
     Output("asset-toast", "icon", allow_duplicate=True)],
    Input("btn-buy-confirm", "n_clicks"),
    [State("trans-asset-ticker-store", "data"),
     State("buy-shares-amount", "value"),
     State("buy-price", "value"),
     State("asset-update-signal", "data")],
    prevent_initial_call=True
)
def confirm_buy(n_clicks, ticker, shares, price, signal):
    if not n_clicks or not all([ticker, shares, price]):
        return no_update, no_update, no_update, no_update, no_update, no_update
        
    try:
        shares_f = float(shares)
        price_f = float(price)
        if shares_f <= 0 or price_f <= 0:
            raise ValueError()
    except ValueError:
        return html.Span("Error: Cantidad y precio deben ser positivos.", className="text-danger"), no_update, no_update, no_update, no_update, no_update

    # Llamada a la función de backend
    success, msg = dm.add_buy(ticker, shares_f, price_f) 
    
    if success:
        new_msg = f"Compra de {shares_f:,.2f} {ticker} registrada."

        # Retorna 3 valores del modal + 3 valores del helper = 6 valores
        return html.Span(new_msg, className="text-success"), False, (signal + 1), \
               *ui_helpers.mensaje_alerta_exito("success", new_msg)
    else:
        # Retorna 3 valores no_update + 3 valores de error para el Toast
        return html.Span(msg, className="text-danger"), no_update, no_update, \
               False, msg, "danger" # Dispara Toast de error

# 4. Registrar Venta (Actualiza DB y dispara Toast)
@callback(
    [Output("sell-msg", "children"),
     Output("sell-modal", "is_open", allow_duplicate=True),
     Output("asset-update-signal", "data", allow_duplicate=True), 
     Output("sales-update-signal", "data", allow_duplicate=True),
     # OUTPUTS DE TOAST
     Output("asset-toast", "is_open", allow_duplicate=True),
     Output("asset-toast", "children", allow_duplicate=True),
     Output("asset-toast", "icon", allow_duplicate=True)],
    Input("btn-sell-confirm", "n_clicks"),
    [State("trans-asset-ticker-store", "data"),
     State("sell-shares-amount", "value"),
     State("sell-price", "value"),
     State("asset-update-signal", "data"),
     State("sales-update-signal", "data")],
    prevent_initial_call=True
)
def confirm_sell(n_clicks, ticker, shares_sold, sale_price, asset_signal, sales_signal):
    if not n_clicks or not all([ticker, shares_sold, sale_price]):
        return no_update, no_update, no_update, no_update, no_update, no_update, no_update
        
    try:
        shares_f = float(shares_sold)
        price_f = float(sale_price)
        if shares_f <= 0 or price_f <= 0:
            raise ValueError()
    except ValueError:
        return html.Span("Error: Cantidad y precio deben ser positivos.", className="text-danger"), no_update, no_update, no_update, no_update, no_update, no_update

    # 1. Obtener unidades disponibles
    pos = dm.get_investment_by_ticker(ticker)
    if not pos or pos['shares'] < shares_f:
        return html.Span("Error: Unidades insuficientes para la venta.", className="text-danger"), no_update, no_update, no_update, no_update, no_update, no_update

    # 2. Llamada a la función de backend
    success, msg = dm.add_sale(ticker, shares_f, price_f) 
    
    if success:
        # Obtener el P&L realizado del mensaje de éxito (asumiendo que dm.add_sale lo devuelve en msg)
        import re
        realized_pl_match = re.search(r'\$[\d,.-]+', msg)
        realized_pl_str = realized_pl_match.group(0) if realized_pl_match else "$0.00"
        
        new_msg = f"Venta de {shares_f:,.2f} {ticker} registrada. P&L: {realized_pl_str}"
        
        # Retorna 4 valores de modal/señal + 3 valores del helper = 7 valores
        return html.Span(new_msg, className="text-success"), False, (asset_signal + 1), (sales_signal + 1), \
               *ui_helpers.mensaje_alerta_exito("success", new_msg)
    else:
        # Retorna 4 valores no_update + 3 valores de error para el Toast
        return html.Span(msg, className="text-danger"), no_update, no_update, no_update, \
               False, msg, "danger" # Dispara Toast de error


# 5. Callback para calcular Costo Total y Nuevo Costo Promedio (Compra - visual)
@callback(
    [Output("buy-total-cost-output", "children"),
     Output("buy-new-avg-cost-output", "children")],
    [Input("buy-shares-amount", "value"),
     Input("buy-price", "value")],
    State("trans-asset-ticker-store", "data"),
    prevent_initial_call=True
)
def calculate_buy_cost_display(shares_to_buy, buy_price, ticker):
    if not shares_to_buy or not buy_price or not ticker:
        return html.Span("Costo Total: $0.00"), html.Span("Nuevo Costo Promedio: $0.00")
    
    pos = dm.get_investment_by_ticker(ticker)

    try:
        shares_bought = float(shares_to_buy)
        price_bought = float(buy_price)
        cost_new_shares = shares_bought * price_bought

        if not pos:
            # Nueva Posición
            return html.Span(f"Costo Total: ${cost_new_shares:,.2f}", className="text-info"), \
                   html.Span(f"Nuevo Costo Promedio: ${price_bought:,.2f}", className="text-info")
            
        shares_current = pos['shares']
        avg_cost_current = pos['avg_price']
        
        current_total_cost = shares_current * avg_cost_current
        new_total_investment = current_total_cost + cost_new_shares
        new_shares_total = shares_current + shares_bought
        
        new_avg_price = new_total_investment / new_shares_total if new_shares_total > 0 else 0.0
        
        total_output = html.Span(f"Costo Total: ${cost_new_shares:,.2f}", className="text-info")
        avg_output = html.Span(f"Nuevo Costo Promedio: ${new_avg_price:,.2f}", className="text-info")
        
        return total_output, avg_output
        
    except:
        return html.Span("Costo Total: $ERROR", className="text-danger"), html.Span("Nuevo Costo Promedio: $ERROR", className="text-danger")


# 6. Callback para calcular P&L de la venta (visual)
@callback(
    [Output("sell-total-value-output", "children"),
     Output("sell-realized-pl-output", "children")],
    [Input("sell-shares-amount", "value"),
     Input("sell-price", "value")],
    State("trans-asset-ticker-store", "data"),
    prevent_initial_call=True
)
def calculate_sell_pl_display(shares_sold, sale_price, ticker):
    if not shares_sold or not sale_price or not ticker:
        return html.Span("Monto Total: $0.00"), html.Span("P/L: $0.00")

    pos = dm.get_investment_by_ticker(ticker)
    if not pos:
        return html.Span("Monto Total: $N/A", className="text-warning"), html.Span("P/L: $N/A", className="text-warning")

    try:
        shares = float(shares_sold)
        price = float(sale_price)
        avg_cost = pos['avg_price']
        
        total_sale_value = shares * price
        realized_pl = (price - avg_cost) * shares
        
        pl_color = "text-success" if realized_pl >= 0 else "text-danger"
        total_color = "text-info" 
        
        total_output = html.Span(f"Monto Total: ${total_sale_value:,.2f}", className=total_color)
        pl_output = html.Span(f"P/L: ${realized_pl:,.2f}", className=pl_color)

        return total_output, pl_output
        
    except:
=======
# pages/investments/investments_transactions.py
import dash
from dash import dcc, html, callback, Input, Output, State, no_update, ctx # 🚨 CORRECCIÓN: 'ctx' Importado
import dash_bootstrap_components as dbc
import backend.data_manager as dm
from utils import ui_helpers

# --- MODAL 1: REGISTRAR COMPRA (BUY) ---
# El Store ID 'trans-asset-ticker-store' está en investments_assets.py
def smart_format(val):
    if val is None or val == 0:
        return "0"
    
    try:
        val_f = float(val)
    except:
        return str(val)

    if val_f.is_integer():
        return f"{int(val_f):,}"
    
    val_abs = abs(val_f)
    if val_abs >= 0.01:
        return f"{val_f:,.2f}"
    else:
        # Redondeo a 5 decimales y limpieza
        return f"{val_f:.5f}".rstrip('0').rstrip('.')
    
buy_modal = dbc.Modal([
    dbc.ModalHeader(dbc.ModalTitle(id="buy-modal-title", children="Registrar Compra")),
    dbc.ModalBody([
        html.P(id="buy-modal-shares-info", className="text-muted small"),
        dbc.Label("Unidades a Comprar"),
        dbc.Input(id="buy-shares-amount", type="number", min=0, placeholder="0.0", className="mb-3"),
        
        dbc.Label("Costo por Unidad (Precio de Ejecución)"),
        dbc.Input(id="buy-price", type="number", placeholder="0.00", className="mb-3"),
        
        # Output para Costo Total Estimado
        html.Div(id="buy-total-cost-output", className="mb-2 fw-bold"), 
        
        # Output para Nuevo Costo Promedio
        html.Div(id="buy-new-avg-cost-output", className="mb-3 fw-bold"), 
        
        html.Div(id="buy-msg", className="mt-2 text-center")
    ]),
    dbc.ModalFooter([
        dbc.Button("Cancelar", id="btn-buy-cancel", outline=True),
        dbc.Button("Confirmar Compra", id="btn-buy-confirm", color="success", className="ms-2"),
    ])
], id="buy-modal", is_open=False, centered=True, size="md")


# --- MODAL 2: REGISTRAR VENTA (SELL) ---
sell_modal = dbc.Modal([
    dbc.ModalHeader(dbc.ModalTitle(id="sell-modal-title", children="Registrar Venta")),
    dbc.ModalBody([
        html.P(id="sell-modal-shares-info", className="text-muted small"),
        dbc.Label("Unidades a Vender"),
        dbc.Input(id="sell-shares-amount", type="number", min=0, placeholder="0.0", className="mb-3"),
        
        dbc.Label("Precio de Venta (Precio de Ejecución)"),
        dbc.Input(id="sell-price", type="number", placeholder="0.00", className="mb-3"),
        
        # Valor Total de la Transacción (Output)
        html.Div(id="sell-total-value-output", className="mb-2 fw-bold"),
        
        # P&L Realizado
        html.Div(id="sell-realized-pl-output", className="mb-3 fw-bold"),
        
        html.Div(id="sell-msg", className="mt-2 text-center")
    ]),
    dbc.ModalFooter([
        dbc.Button("Cancelar", id="btn-sell-cancel", outline=True),
        dbc.Button("Confirmar Venta", id="btn-sell-confirm", color="danger", className="ms-2"),
    ])
], id="sell-modal", is_open=False, centered=True, size="md")

# --- EXPORTAR LAYOUT DE MODALES ---
layout = html.Div([
    buy_modal, 
    sell_modal
])


# ==============================================================================
# CALLBACKS DE CONTROL DE MODALES Y LÓGICA DE TRANSACCIÓN
# ==============================================================================

# 1. Abrir Modal de Compra y poblar info (Incluye precarga de precio y limpieza de mensaje)
@callback(
    [Output("buy-modal", "is_open"),
     Output("buy-modal-title", "children"),
     Output("buy-modal-shares-info", "children"),
     Output("buy-msg", "children", allow_duplicate=True), 
     Output("buy-price", "value")], 
    Input("btn-open-buy-modal", "n_clicks"),
    Input("btn-buy-cancel", "n_clicks"),
    State("trans-asset-ticker-store", "data"), 
    prevent_initial_call=True
)
def toggle_buy_modal(open_n, cancel_n, ticker):
    if ctx.triggered_id == "btn-buy-cancel":
        return False, no_update, no_update, "", no_update
        
    if ticker and open_n:
        pos = dm.get_investment_by_ticker(ticker)
        data = dm.get_simulator_ticker_data(ticker)
        
        modal_title = f"Registrar Compra: {ticker}"
        
        # --- CAMBIO AQUÍ: Usamos smart_format ---
        cantidad = pos['shares'] if pos else 0
        shares_info = f"Activo: {ticker}. Unidades actuales: {smart_format(cantidad)}."
        
        current_price = data['current_price'] if data and data['current_price'] else 0
        
        return True, modal_title, shares_info, "", current_price
        
    return no_update, no_update, no_update, no_update, no_update

# 2. Abrir Modal de Venta y poblar info (Incluye precarga de precio y limpieza de mensaje)
@callback(
    [Output("sell-modal", "is_open"),
     Output("sell-modal-title", "children"),
     Output("sell-modal-shares-info", "children"),
     Output("sell-price", "value"),
     Output("sell-msg", "children", allow_duplicate=True)], 
    Input("btn-open-sell-modal", "n_clicks"),
    Input("btn-sell-cancel", "n_clicks"),
    State("trans-asset-ticker-store", "data"), 
    prevent_initial_call=True
)
def toggle_sell_modal(open_n, cancel_n, ticker):
    if ctx.triggered_id == "btn-sell-cancel":
        return False, no_update, no_update, no_update, ""
        
    if ticker and open_n:
        pos = dm.get_investment_by_ticker(ticker)
        data = dm.get_simulator_ticker_data(ticker)

        shares = pos['shares'] if pos else 0
        
        modal_title = f"Registrar Venta: {ticker}"
        
        # --- CAMBIO AQUÍ: Usamos smart_format ---
        shares_info = f"Activo: {ticker}. Unidades disponibles: {smart_format(shares)}."
        
        current_price = data['current_price'] if data and data['current_price'] else 0
        
        return True, modal_title, shares_info, current_price, ""
        
    return no_update, no_update, no_update, no_update, no_update
# 3. Registrar Compra (Actualiza DB y dispara Toast)
@callback(
    [Output("buy-msg", "children"),
     Output("buy-modal", "is_open", allow_duplicate=True),
     Output("asset-update-signal", "data", allow_duplicate=True),
     # OUTPUTS DE TOAST
     Output("asset-toast", "is_open", allow_duplicate=True),
     Output("asset-toast", "children", allow_duplicate=True),
     Output("asset-toast", "icon", allow_duplicate=True)],
    Input("btn-buy-confirm", "n_clicks"),
    [State("trans-asset-ticker-store", "data"),
     State("buy-shares-amount", "value"),
     State("buy-price", "value"),
     State("asset-update-signal", "data")],
    prevent_initial_call=True
)
def confirm_buy(n_clicks, ticker, shares, price, signal):
    if not n_clicks or not all([ticker, shares, price]):
        return no_update, no_update, no_update, no_update, no_update, no_update
        
    try:
        shares_f = float(shares)
        price_f = float(price)
        if shares_f <= 0 or price_f <= 0:
            raise ValueError()
    except ValueError:
        return html.Span("Error: Cantidad y precio deben ser positivos.", className="text-danger"), no_update, no_update, no_update, no_update, no_update

    # Llamada a la función de backend
    success, msg = dm.add_buy(ticker, shares_f, price_f) 
    
    if success:
        new_msg = f"Compra de {shares_f:,.2f} {ticker} registrada."

        # Retorna 3 valores del modal + 3 valores del helper = 6 valores
        return html.Span(new_msg, className="text-success"), False, (signal + 1), \
               *ui_helpers.mensaje_alerta_exito("success", new_msg)
    else:
        # Retorna 3 valores no_update + 3 valores de error para el Toast
        return html.Span(msg, className="text-danger"), no_update, no_update, \
               False, msg, "danger" # Dispara Toast de error

# 4. Registrar Venta (Actualiza DB y dispara Toast)
@callback(
    [Output("sell-msg", "children"),
     Output("sell-modal", "is_open", allow_duplicate=True),
     Output("asset-update-signal", "data", allow_duplicate=True), 
     Output("sales-update-signal", "data", allow_duplicate=True),
     # OUTPUTS DE TOAST
     Output("asset-toast", "is_open", allow_duplicate=True),
     Output("asset-toast", "children", allow_duplicate=True),
     Output("asset-toast", "icon", allow_duplicate=True)],
    Input("btn-sell-confirm", "n_clicks"),
    [State("trans-asset-ticker-store", "data"),
     State("sell-shares-amount", "value"),
     State("sell-price", "value"),
     State("asset-update-signal", "data"),
     State("sales-update-signal", "data")],
    prevent_initial_call=True
)
def confirm_sell(n_clicks, ticker, shares_sold, sale_price, asset_signal, sales_signal):
    if not n_clicks or not all([ticker, shares_sold, sale_price]):
        return no_update, no_update, no_update, no_update, no_update, no_update, no_update
        
    try:
        shares_f = float(shares_sold)
        price_f = float(sale_price)
        if shares_f <= 0 or price_f <= 0:
            raise ValueError()
    except ValueError:
        return html.Span("Error: Cantidad y precio deben ser positivos.", className="text-danger"), no_update, no_update, no_update, no_update, no_update, no_update

    # 1. Obtener unidades disponibles
    pos = dm.get_investment_by_ticker(ticker)
    if not pos or pos['shares'] < shares_f:
        return html.Span("Error: Unidades insuficientes para la venta.", className="text-danger"), no_update, no_update, no_update, no_update, no_update, no_update

    # 2. Llamada a la función de backend
    success, msg = dm.add_sale(ticker, shares_f, price_f) 
    
    if success:
        # Obtener el P&L realizado del mensaje de éxito (asumiendo que dm.add_sale lo devuelve en msg)
        import re
        realized_pl_match = re.search(r'\$[\d,.-]+', msg)
        realized_pl_str = realized_pl_match.group(0) if realized_pl_match else "$0.00"
        
        new_msg = f"Venta de {shares_f:,.2f} {ticker} registrada. P&L: {realized_pl_str}"
        
        # Retorna 4 valores de modal/señal + 3 valores del helper = 7 valores
        return html.Span(new_msg, className="text-success"), False, (asset_signal + 1), (sales_signal + 1), \
               *ui_helpers.mensaje_alerta_exito("success", new_msg)
    else:
        # Retorna 4 valores no_update + 3 valores de error para el Toast
        return html.Span(msg, className="text-danger"), no_update, no_update, no_update, \
               False, msg, "danger" # Dispara Toast de error


# 5. Callback para calcular Costo Total y Nuevo Costo Promedio (Compra - visual)
@callback(
    [Output("buy-total-cost-output", "children"),
     Output("buy-new-avg-cost-output", "children")],
    [Input("buy-shares-amount", "value"),
     Input("buy-price", "value")],
    State("trans-asset-ticker-store", "data"),
    prevent_initial_call=True
)
def calculate_buy_cost_display(shares_to_buy, buy_price, ticker):
    if not shares_to_buy or not buy_price or not ticker:
        return html.Span("Costo Total: $0.00"), html.Span("Nuevo Costo Promedio: $0.00")
    
    pos = dm.get_investment_by_ticker(ticker)

    try:
        shares_bought = float(shares_to_buy)
        price_bought = float(buy_price)
        cost_new_shares = shares_bought * price_bought

        if not pos:
            # Nueva Posición
            return html.Span(f"Costo Total: ${cost_new_shares:,.2f}", className="text-info"), \
                   html.Span(f"Nuevo Costo Promedio: ${price_bought:,.2f}", className="text-info")
            
        shares_current = pos['shares']
        avg_cost_current = pos['avg_price']
        
        current_total_cost = shares_current * avg_cost_current
        new_total_investment = current_total_cost + cost_new_shares
        new_shares_total = shares_current + shares_bought
        
        new_avg_price = new_total_investment / new_shares_total if new_shares_total > 0 else 0.0
        
        total_output = html.Span(f"Costo Total: ${cost_new_shares:,.2f}", className="text-info")
        avg_output = html.Span(f"Nuevo Costo Promedio: ${new_avg_price:,.2f}", className="text-info")
        
        return total_output, avg_output
        
    except:
        return html.Span("Costo Total: $ERROR", className="text-danger"), html.Span("Nuevo Costo Promedio: $ERROR", className="text-danger")


# 6. Callback para calcular P&L de la venta (visual)
@callback(
    [Output("sell-total-value-output", "children"),
     Output("sell-realized-pl-output", "children")],
    [Input("sell-shares-amount", "value"),
     Input("sell-price", "value")],
    State("trans-asset-ticker-store", "data"),
    prevent_initial_call=True
)
def calculate_sell_pl_display(shares_sold, sale_price, ticker):
    if not shares_sold or not sale_price or not ticker:
        return html.Span("Monto Total: $0.00"), html.Span("P/L: $0.00")

    pos = dm.get_investment_by_ticker(ticker)
    if not pos:
        return html.Span("Monto Total: $N/A", className="text-warning"), html.Span("P/L: $N/A", className="text-warning")

    try:
        shares = float(shares_sold)
        price = float(sale_price)
        avg_cost = pos['avg_price']
        
        total_sale_value = shares * price
        realized_pl = (price - avg_cost) * shares
        
        pl_color = "text-success" if realized_pl >= 0 else "text-danger"
        total_color = "text-info" 
        
        total_output = html.Span(f"Monto Total: ${total_sale_value:,.2f}", className=total_color)
        pl_output = html.Span(f"P/L: ${realized_pl:,.2f}", className=pl_color)

        return total_output, pl_output
        
    except:
>>>>>>> b74f1b0a886c27181c8264a954a4baf9f2b71029
        return html.Span("Monto Total: $ERROR", className="text-danger"), html.Span("P/L: $ERROR", className="text-danger")