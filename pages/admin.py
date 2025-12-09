# pages/admin.py
import dash
from dash import dcc, html, callback, Input, Output, State, no_update, ctx, dash_table
import dash_bootstrap_components as dbc
import backend.data_manager as dm
from flask_login import current_user
import time

# ==============================================================================
# 0. COMPONENTES GLOBALES (TOAST DE NOTIFICACIÓN)
# ==============================================================================
success_toast = dbc.Toast(
    "Acción realizada correctamente.",
    id="admin-success-toast",
    header="Éxito",
    is_open=False,
    dismissable=True,
    icon="success",
    duration=4000, # Dura 4 segundos
    style={"position": "fixed", "top": 80, "right": 10, "width": 350, "zIndex": 9999},
)

# ==============================================================================
# 1. MODAL: DETALLES Y EDICIÓN DE USUARIO
# ==============================================================================
user_detail_modal = dbc.Modal([
    dbc.ModalHeader(dbc.ModalTitle("Detalles de Usuario")),
    dbc.ModalBody([
        dcc.Store(id="admin-selected-user-id"), 
        dcc.Store(id="admin-selected-username"), # Guardamos el username para la validación de borrado
        
        # A. TARJETA DE RESUMEN
        dbc.Card([
            dbc.CardBody([
                dbc.Row([
                    dbc.Col([
                        html.H4(id="detail-display-name", className="fw-bold mb-0 text-primary"),
                        html.Small(id="detail-username", className="text-muted")
                    ], width=8),
                    dbc.Col([
                        dbc.Badge(id="detail-id-badge", color="dark", className="float-end")
                    ], width=4)
                ], className="mb-3"),
                
                dbc.Row([
                    dbc.Col([
                        html.Small("📅 Creado el:", className="text-muted d-block"),
                        html.Span(id="detail-created", className="fw-bold")
                    ], width=6),
                    dbc.Col([
                        html.Small("🕒 Último Login:", className="text-muted d-block"),
                        html.Span(id="detail-last-login", className="fw-bold text-info")
                    ], width=6),
                ])
            ])
        ], className="mb-4 shadow-sm border-0 bg-light"),

        # B. SECCIONES DE GESTIÓN (Acordeón)
        dbc.Accordion([
            # --- EDITAR DATOS ---
            dbc.AccordionItem([
                dbc.Label("Nombre Visible (Display Name)"),
                dbc.Input(id="edit-display-name", type="text", className="mb-2"),
                
                dbc.Label("Correo Electrónico"),
                dbc.Input(id="edit-email", type="email", className="mb-3"),
                
                dbc.Button("Guardar Cambios", id="btn-save-details", color="success", size="sm", className="w-100"),
                html.Div(id="detail-save-msg", className="mt-2 text-center small")
            ], title="✏️ Editar Datos Personales"),

            # --- RESTABLECER CONTRASEÑA ---
            dbc.AccordionItem([
                html.P("Si el usuario olvidó su contraseña, asigna una nueva aquí.", className="text-muted small"),
                dbc.Input(id="reset-password-input", placeholder="Nueva contraseña...", type="text", className="mb-2"),
                dbc.Button("Restablecer Contraseña", id="btn-reset-pass", color="warning", size="sm", className="w-100 text-dark fw-bold"),
                html.Div(id="reset-pass-msg", className="mt-2 text-center small")
            ], title="🔒 Restablecer Contraseña"),

            # --- ZONA DE PELIGRO (BORRAR) ---
            dbc.AccordionItem([
                html.P("⚠️ CUIDADO: Esta acción es irreversible. Se borrarán todas las cuentas, transacciones e inversiones de este usuario.", className="text-danger small"),
                # Este botón ahora abre el modal de confirmación de seguridad
                dbc.Button("🗑️ Eliminar Usuario Definitivamente", id="btn-pre-delete-user", color="danger", outline=True, size="sm", className="w-100"),
            ], title="💀 Zona de Peligro"),
        ], flush=True, start_collapsed=True)
    ]),
    dbc.ModalFooter(
        dbc.Button("Cerrar", id="btn-close-detail", className="ms-auto", outline=True)
    )
], id="user-detail-modal", is_open=False, centered=True)


# ==============================================================================
# 2. MODAL: CONFIRMACIÓN DE SEGURIDAD (BORRADO)
# ==============================================================================
delete_confirm_modal = dbc.Modal([
    dbc.ModalHeader("Confirmar Eliminación Irreversible", className="bg-danger text-white"),
    dbc.ModalBody([
        html.P("Para confirmar, por favor escribe la siguiente frase exactamente:", className="mb-2"),
        
        # Texto objetivo dinámico
        html.Div(id="delete-target-text", className="alert alert-secondary text-center fw-bold user-select-all mb-3"),
        
        dbc.Input(id="delete-confirm-input", placeholder="Escribe aquí...", type="text", className="mb-2"),
        html.Div(id="delete-validation-msg", className="small text-danger", style={"minHeight": "20px"})
    ]),
    dbc.ModalFooter([
        dbc.Button("Cancelar", id="btn-cancel-delete", outline=True, className="me-2"),
        # Botón deshabilitado por defecto hasta que coincida el texto
        dbc.Button("Confirmar Borrado", id="btn-final-delete-confirm", color="danger", disabled=True)
    ])
], id="delete-confirm-modal", is_open=False, centered=True, backdrop="static")


# ==============================================================================
# 3. MODAL: CREAR NUEVO USUARIO
# ==============================================================================
add_user_modal = dbc.Modal([
    dbc.ModalHeader("Registrar Nuevo Usuario"),
    dbc.ModalBody([
        dbc.Label("Username (Login) *"),
        dbc.Input(id="new-user-name", placeholder="Ej: admin", className="mb-2"),
        
        dbc.Label("Contraseña *"),
        dbc.Input(id="new-user-pass", placeholder="••••••", type="password", className="mb-2"),
        
        dbc.Label("Nombre Visible (Opcional)"),
        dbc.Input(id="new-display-name", placeholder="Ej: Daniel Alas", className="mb-2"),
        
        dbc.Label("Email (Opcional)"),
        dbc.Input(id="new-user-email", placeholder="correo@ejemplo.com", type="email", className="mb-2"),
        
        html.Div(id="add-user-msg", className="text-center mt-3 fw-bold small")
    ]),
    dbc.ModalFooter([
        dbc.Button("Cancelar", id="btn-cancel-add", outline=True, className="me-2"),
        dbc.Button("Crear Usuario", id="btn-create-user", color="primary")
    ])
], id="add-user-modal", is_open=False, centered=True)


# ==============================================================================
# 4. LAYOUT PRINCIPAL
# ==============================================================================
layout = html.Div([
    dcc.Store(id="admin-refresh-signal", data=0),
    success_toast, # Toast invisible hasta que se active
    
    dbc.Container([
        html.H2("Panel de Administración", className="mb-4 text-warning"),
        html.Div(id="admin-content-protector", style={"height": "100%"})
    ], 
    fluid=True, 
    style={
        "height": "calc(100vh - 140px)", 
        "overflow": "hidden", 
        "display": "flex", 
        "flexDirection": "column"
    }) 
])


# ==============================================================================
# 5. CALLBACKS
# ==============================================================================

# --- RENDERIZAR TABLA ---
@callback(
    Output("admin-content-protector", "children"),
    [Input("url", "pathname"), Input("admin-refresh-signal", "data")]
)
def render_admin_panel(pathname, signal):
    if not current_user.is_authenticated or current_user.username != 'admin':
        return dbc.Alert("Acceso Denegado: Se requieren privilegios de administrador.", color="danger", className="mt-4")

    users = dm.get_all_users_detailed()
    
    data = []
    for u in users:
        row = u.copy()
        row['info_btn'] = "ℹ️ Gestionar" 
        data.append(row)

    columns = [
        {"name": "ID", "id": "id"},
        {"name": "Usuario", "id": "username"},
        {"name": "Display Name", "id": "display_name"},
        {"name": "Email", "id": "email"},
        {"name": "Último Login", "id": "last_login"},
        {"name": "Acción", "id": "info_btn", "presentation": "markdown"} 
    ]

    table = dash_table.DataTable(
        id='users-table',
        columns=columns,
        data=data,
        style_header={'backgroundColor': '#222', 'color': 'white', 'fontWeight': 'bold'},
        style_cell={'textAlign': 'center', 'padding': '12px', 'backgroundColor': '#1a1a1a', 'color': '#eee', 'border': '1px solid #333'},
        style_data_conditional=[
            {'if': {'column_id': 'info_btn'}, 'cursor': 'pointer', 'color': '#2A9FD6', 'fontWeight': 'bold', 'fontSize': '1.1em'}
        ],
        page_action='none', 
        fixed_rows={'headers': True}, 
        style_table={'height': '60vh', 'overflowY': 'auto'}, 
        active_cell=None,
        selected_cells=[]
    )

    return html.Div([
        user_detail_modal,
        delete_confirm_modal,
        add_user_modal,
        dbc.Row([
            dbc.Col(html.P("Gestión de usuarios activos y sus credenciales.", className="text-muted"), width=True),
            dbc.Col(dbc.Button("+ Nuevo Usuario", id="btn-open-add-user", color="success", size="sm"), width="auto")
        ], className="mb-3 align-items-center"),
        table
    ])


# --- ABRIR MODAL INFO ---
@callback(
    [Output("user-detail-modal", "is_open"),
     Output("users-table", "active_cell"), 
     Output("admin-selected-user-id", "data"),
     Output("admin-selected-username", "data"), # Guardamos username
     Output("detail-display-name", "children"),
     Output("detail-username", "children"),
     Output("detail-id-badge", "children"),
     Output("detail-created", "children"),
     Output("detail-last-login", "children"),
     Output("edit-display-name", "value"),
     Output("edit-email", "value"),
     Output("detail-save-msg", "children"),
     Output("reset-pass-msg", "children")],
    [Input("users-table", "active_cell"),
     Input("btn-close-detail", "n_clicks")],
    [State("users-table", "data")],
    prevent_initial_call=True
)
def toggle_info_modal(active_cell, close, table_data):
    ctx_id = ctx.triggered_id
    
    if ctx_id == "btn-close-detail":
        # Cerrar todo y limpiar
        return False, None, no_update, no_update, no_update, no_update, no_update, no_update, no_update, no_update, no_update, "", ""

    if active_cell and active_cell['column_id'] == 'info_btn':
        row = table_data[active_cell['row']]
        uid = row['id']
        username = row['username']
        
        return (True, no_update, uid, username, # Guardamos username
                row['display_name'], f"@{username}", f"ID: {uid}",
                row['created_at'] or "-", row['last_login'] or "Nunca",
                row['display_name'], row['email'], "", "")
                
    return no_update, no_update, no_update, no_update, no_update, no_update, no_update, no_update, no_update, no_update, no_update, no_update


# --- CREAR NUEVO USUARIO ---
@callback(
    [Output("add-user-modal", "is_open"),
     Output("add-user-msg", "children"),
     Output("admin-refresh-signal", "data", allow_duplicate=True),
     Output("admin-success-toast", "is_open", allow_duplicate=True),
     Output("admin-success-toast", "children", allow_duplicate=True)],
    [Input("btn-open-add-user", "n_clicks"), 
     Input("btn-create-user", "n_clicks"),
     Input("btn-cancel-add", "n_clicks")],
    [State("add-user-modal", "is_open"),
     State("new-user-name", "value"), 
     State("new-user-pass", "value"),
     State("new-user-email", "value"), 
     State("new-display-name", "value"),
     State("admin-refresh-signal", "data")],
    prevent_initial_call=True
)
def create_user_logic(open_n, create_n, cancel_n, is_open, user, pwd, email, display, signal):
    trig = ctx.triggered_id
    
    if trig == "btn-open-add-user": 
        return True, "", no_update, False, no_update
    
    if trig == "btn-cancel-add":
        return False, "", no_update, False, no_update

    if trig == "btn-create-user":
        if not user or not pwd:
            return True, html.Span("Error: Usuario y Contraseña obligatorios.", className="text-danger"), no_update, False, no_update
        
        success, msg = dm.register_user(user, pwd, email, display)
        
        if success:
            # Éxito: Cerrar modal, refrescar tabla y MOSTRAR TOAST
            return False, "", (signal + 1), True, f"Usuario '{user}' creado exitosamente."
        else:
            return True, html.Span(msg, className="text-danger"), no_update, False, no_update
            
    return is_open, "", no_update, False, no_update


# --- GUARDAR CAMBIOS DE DETALLE ---
@callback(
    [Output("detail-save-msg", "children", allow_duplicate=True),
     Output("admin-refresh-signal", "data", allow_duplicate=True)],
    Input("btn-save-details", "n_clicks"),
    [State("admin-selected-user-id", "data"),
     State("edit-email", "value"),
     State("edit-display-name", "value"),
     State("admin-refresh-signal", "data")],
    prevent_initial_call=True
)
def save_details(n, uid, email, display, signal):
    if not uid: return no_update, no_update
    success, msg = dm.admin_update_user_details(uid, email, display)
    cls = "text-success fw-bold" if success else "text-danger fw-bold"
    return html.Span(msg, className=cls), (signal + 1)


# --- RESET PASSWORD ---
@callback(
    Output("reset-pass-msg", "children", allow_duplicate=True),
    Input("btn-reset-pass", "n_clicks"),
    [State("admin-selected-user-id", "data"), State("reset-password-input", "value")],
    prevent_initial_call=True
)
def reset_pass(n, uid, new_pass):
    if not new_pass: return html.Span("Escribe una contraseña", className="text-warning")
    success, msg = dm.admin_reset_password(uid, new_pass)
    cls = "text-success fw-bold" if success else "text-danger fw-bold"
    return html.Span(msg, className=cls)


# ==============================================================================
# LÓGICA DE BORRADO SEGURO
# ==============================================================================

# 1. ABRIR MODAL DE CONFIRMACIÓN Y PREPARAR TEXTO
@callback(
    [Output("delete-confirm-modal", "is_open"),
     Output("delete-target-text", "children"),
     Output("delete-confirm-input", "value"),
     Output("btn-final-delete-confirm", "disabled")], # Deshabilitar botón al inicio
    [Input("btn-pre-delete-user", "n_clicks"),
     Input("btn-cancel-delete", "n_clicks")],
    [State("admin-selected-username", "data")],
    prevent_initial_call=True
)
def toggle_delete_modal(pre_delete, cancel, username):
    trig = ctx.triggered_id
    
    # ABRIR
    if trig == "btn-pre-delete-user" and username:
        target_text = f"eliminar {username}"
        return True, target_text, "", True # Modal abierto, Texto objetivo, Input vacío, Botón deshabilitado
    
    # CERRAR
    if trig == "btn-cancel-delete":
        return False, "", "", True
        
    return no_update, no_update, no_update, no_update


# 2. VALIDAR TEXTO DE CONFIRMACIÓN EN TIEMPO REAL
@callback(
    Output("btn-final-delete-confirm", "disabled", allow_duplicate=True),
    Input("delete-confirm-input", "value"),
    State("delete-target-text", "children"),
    prevent_initial_call=True
)
def validate_delete_input(input_val, target_text):
    if not input_val or not target_text:
        return True # Deshabilitado
    
    if input_val.strip() == target_text:
        return False # HABILITADO
    
    return True # Deshabilitado


# 3. EJECUTAR ELIMINACIÓN FINAL
@callback(
    [Output("delete-confirm-modal", "is_open", allow_duplicate=True),
     Output("user-detail-modal", "is_open", allow_duplicate=True), # Cerrar el de detalle también
     Output("admin-refresh-signal", "data", allow_duplicate=True),
     Output("admin-success-toast", "is_open", allow_duplicate=True),
     Output("admin-success-toast", "children", allow_duplicate=True)],
    Input("btn-final-delete-confirm", "n_clicks"),
    [State("admin-selected-user-id", "data"),
     State("admin-selected-username", "data"),
     State("admin-refresh-signal", "data")],
    prevent_initial_call=True
)
def execute_final_delete(n, uid, username, signal):
    if not n or not uid: return no_update, no_update, no_update, no_update, no_update
    
    # Llamar al backend
    success, msg = dm.admin_delete_user(uid)
    
    if success:
        # Cierra AMBOS modales, refresca tabla, muestra Toast
        return False, False, (signal + 1), True, f"Usuario '{username}' eliminado correctamente."
    else:
        # Aquí podrías manejar error, pero por ahora solo cerramos si falla
        return False, False, no_update, True, f"Error: {msg}"