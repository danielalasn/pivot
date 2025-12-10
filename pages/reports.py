# pages/reports.py
import dash
from dash import dcc, html, callback, Input, Output, State, no_update, ctx
import dash_bootstrap_components as dbc
import backend.data_manager as dm
from datetime import date
import pandas as pd
import io
import time 

# --- LISTA MAESTRA DE REPORTES ---
REPORT_OPTIONS = [
    ("transactions", "Transacciones (Ingresos/Gastos)"),
    ("net_worth", "Patrimonio Neto"),
    ("investments_current", "Portafolio Actual"),
    ("investments_history", "Historial de Trading"),
    ("accounts", "Cuentas y Deudas"),
    ("fixed_costs", "Costos Fijos"),
    ("savings", "Metas de Ahorro"),
]

# 🚨 AJUSTE CLAVE: Usamos 'style' para darle una altura que se ajuste mejor al contenido vertical
layout = dbc.Container([
    html.H2("Centro de Reportes", className="mb-3 text-primary"),
    dbc.Card([
        dbc.CardHeader([
            html.I(className="bi bi-file-earmark-spreadsheet me-2"),
            "Configuración de Reporte Excel"
        ], className="fw-bold py-2"), # Reducir padding vertical del Header
        
        # 🚨 Contenedor principal con margen reducido (py-3 en lugar de py-4/5)
        dbc.CardBody(className="py-3", children=[ 
            
            # 1. RANGO DE FECHAS (Fila 1)
            dbc.Row([
                # Columna de Título (más pequeña)
                dbc.Col(html.H6("1. Rango de Fechas", className="text-info mb-0"), lg=3, md=12),
                
                # Selector de Fechas
                dbc.Col([
                    dcc.DatePickerRange(
                        id='report-date-picker',
                        display_format='DD/MM/YYYY',
                        start_date=date(date.today().year, 1, 1),
                        end_date=date.today(),
                        style={'zIndex': 100, 'width': '100%'}
                    )
                ], lg=5, md=8, xs=12, className="mb-2 mb-lg-0"),
                
                # Botón Toda la Historia
                dbc.Col([
                    dbc.Button("Toda la Historia", id="btn-report-all-time", color="secondary", outline=True, size="sm", className="w-100"), 
                ], lg=4, md=4, xs=12),

            ], className="mb-3 align-items-center g-2"), # Reducir margen inferior y gap
            
            html.Hr(className="my-3"),

            # 2. SELECCIÓN DE DATOS (Fila 2 - Switches)
            dbc.Row([
                # Columna de Título (más pequeña)
                dbc.Col(html.H6("2. Datos a Incluir (Pestañas en Excel)", className="text-info mb-2"), lg=3, md=12),

                # Botones de control masivo (Justificación a la derecha)
                dbc.Col([
                    dbc.Row([
                        dbc.Col(
                            dbc.Button("Seleccionar Todo", id="btn-select-all-reports", color="link", size="sm", className="p-0 text-success"), 
                            width="auto"
                        ),
                        dbc.Col(
                            dbc.Button("Ninguno", id="btn-deselect-all-reports", color="link", size="sm", className="p-0 text-muted"),
                            width="auto"
                        )
                    ], className="g-2 justify-content-end")
                ], lg=9, md=12, className="d-flex align-items-center"),

            ], className="align-items-center"),


            # Lista de switches (Horizontal y Expandida)
            dbc.Row([
                 dbc.Col(
                     dbc.Checklist(
                        id="report-selection-list",
                        options=[{"label": label, "value": val} for val, label in REPORT_OPTIONS],
                        value=["transactions"],
                        switch=True,
                        inputClassName="me-2",
                        className="d-flex flex-wrap gap-3 mb-4 p-3 rounded bg-transparent" 
                    ),
                    width=12
                 )
            ], className="mb-2"), # Margen inferior reducido


            html.Hr(className="my-3"),

            # 3. BOTÓN DE DESCARGA (Fila 3)
            dbc.Row([
                # Mensaje de Estado
                dbc.Col(html.Div(id="report-status-msg", className="text-center text-danger small pt-2"), lg=6, md=12),
                
                # Botón de Descarga
                dbc.Col(
                    dbc.Button([html.I(className="bi bi-download me-2"), "Generar Reporte Excel"], 
                               id="btn-download-report", color="success", size="lg", className="w-100 fw-bold"),
                    lg=6, md=12
                ),
            ], className="g-3 align-items-center")
            
        ])
    ], className="shadow-lg border-light mb-0"),
    
    # Componente invisible que maneja la descarga
    dcc.Download(id="download-dataframe-xlsx"),

], fluid=True, className="p-0 m-0 page-container")


# ==============================================================================
# CALLBACKS (Mantienen la misma lógica, solo la vista cambia)
# ==============================================================================
# 1. CONTROL DE FECHAS (BOTÓN "TODA LA HISTORIA")
@callback(
    [Output('report-date-picker', 'start_date', allow_duplicate=True),
     Output('report-date-picker', 'end_date', allow_duplicate=True)],
    Input('btn-report-all-time', 'n_clicks'),
    prevent_initial_call=True
)
def set_all_time(n):
    return "2020-01-01", date.today()

# 2. CONTROL DE SELECCIÓN (TODOS / NINGUNO)
@callback(
    Output('report-selection-list', 'value'),
    [Input('btn-select-all-reports', 'n_clicks'),
     Input('btn-deselect-all-reports', 'n_clicks')],
    prevent_initial_call=True
)
def toggle_selection(n_all, n_none):
    ctx_id = ctx.triggered_id
    if ctx_id == 'btn-select-all-reports':
        return [x[0] for x in REPORT_OPTIONS]
    elif ctx_id == 'btn-deselect-all-reports':
        return []
    return no_update


# 3. GENERAR Y DESCARGAR EXCEL (Lógica Principal)
@callback(
    [Output("download-dataframe-xlsx", "data"),
     Output("report-status-msg", "children")],
    Input("btn-download-report", "n_clicks"),
    [State("report-selection-list", "value"),
     State("report-date-picker", "start_date"),
     State("report-date-picker", "end_date")],
    prevent_initial_call=True
)
def generate_excel_report(n, selected_reports, start_date, end_date):
    if not n: return no_update, ""
    if not selected_reports:
        return no_update, "⚠️ Selecciona al menos un tipo de reporte para descargar."

    output = io.BytesIO()
    
    try:
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            has_data = False

            def filter_df_by_date(df, start_date, end_date):
                if df.empty: return df
                df['date_dt'] = pd.to_datetime(df['date'], format='mixed', errors='coerce')
                mask = (df['date_dt'] >= pd.to_datetime(start_date)) & (df['date_dt'] <= pd.to_datetime(end_date))
                return df.loc[mask].drop(columns=['date_dt'], errors='ignore')

            # 1. TRANSACCIONES
            if "transactions" in selected_reports:
                df = dm.get_transactions_df()
                df_final = filter_df_by_date(df, start_date, end_date).drop(columns=['user_id', 'account_id'], errors='ignore')
                if not df_final.empty:
                    df_final.to_excel(writer, sheet_name='Transacciones', index=False)
                    has_data = True

            # 2. PATRIMONIO NETO
            if "net_worth" in selected_reports:
                df = dm.get_historical_networth_trend(start_date, end_date)
                if not df.empty:
                    df.to_excel(writer, sheet_name='Historial Patrimonio', index=False)
                    has_data = True

            # 3. PORTAFOLIO ACTUAL (Ignora Fechas)
            if "investments_current" in selected_reports:
                data = dm.get_stocks_data(force_refresh=False)
                if data:
                    df = pd.DataFrame(data)
                    cols = ['ticker', 'name', 'shares', 'avg_price', 'current_price', 'market_value', 'total_gain', 'asset_type', 'sector']
                    cols = [c for c in cols if c in df.columns]
                    df[cols].to_excel(writer, sheet_name='Portafolio Actual', index=False)
                    has_data = True

            # 4. HISTORIAL TRADING
            if "investments_history" in selected_reports:
                df = dm.get_investment_transactions_df()
                df_final = filter_df_by_date(df, start_date, end_date).drop(columns=['user_id'], errors='ignore')
                if not df_final.empty:
                    df_final.to_excel(writer, sheet_name='Historial Trading', index=False)
                    has_data = True

            # 5. CUENTAS (Ignora Fechas)
            if "accounts" in selected_reports:
                df_acc = dm.get_accounts_by_category("Debit")
                df_cred = dm.get_accounts_by_category("Credit")
                df = pd.concat([df_acc, df_cred], ignore_index=True)
                if not df.empty:
                    df.drop(columns=['user_id'], errors='ignore').to_excel(writer, sheet_name='Estado Cuentas', index=False)
                    has_data = True

            # 6. COSTOS FIJOS (Ignora Fechas)
            if "fixed_costs" in selected_reports:
                df = dm.get_fixed_costs_df()
                if not df.empty:
                    df.drop(columns=['user_id'], errors='ignore').to_excel(writer, sheet_name='Costos Fijos', index=False)
                    has_data = True

            # 7. AHORROS (Ignora Fechas)
            if "savings" in selected_reports:
                df = dm.get_savings_goals_df()
                if not df.empty:
                    df.drop(columns=['user_id'], errors='ignore').to_excel(writer, sheet_name='Metas Ahorro', index=False)
                    has_data = True

            if not has_data:
                return no_update, "⚠️ No se encontraron datos en los filtros aplicados. Intenta con un rango más amplio."

    except Exception as e:
        return no_update, f"Error generando Excel: {str(e)}"

    # Preparar descarga
    data = output.getvalue()
    filename = f"Reporte_Pivot_{date.today().strftime('%Y-%m-%d')}.xlsx"
    return dcc.send_bytes(data, filename), ""