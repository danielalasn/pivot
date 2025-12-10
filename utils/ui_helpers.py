<<<<<<< HEAD
import dash_bootstrap_components as dbc
from dash import html

def get_feedback_toast(id_name):
    """
    Crea el componente visual del Toast (Notificación) para poner en el layout.
    """
    return dbc.Toast(
        "Mensaje por defecto",
        id=id_name,
        header="Notificación",
        is_open=False,
        dismissable=True,
        duration=4000, # 4 segundos
        icon="success",
        style={"position": "fixed", "top": 20, "right": 20, "width": 350, "zIndex": 2100},
    )

def mensaje_alerta_exito(tipo, mensaje):
    """
    Helper para retornar los valores correctos al callback.
    tipo: 'success', 'danger', 'warning', 'info'
    mensaje: Texto a mostrar
    Retorna: (is_open, children, icon/color)
    """
    # Mapeamos tipos a iconos/colores de Bootstrap
    valid_types = ["primary", "secondary", "success", "danger", "warning", "info", "light", "dark"]
    color = tipo if tipo in valid_types else "info"
    
=======
import dash_bootstrap_components as dbc
from dash import html

def get_feedback_toast(id_name):
    """
    Crea el componente visual del Toast (Notificación) para poner en el layout.
    """
    return dbc.Toast(
        "Mensaje por defecto",
        id=id_name,
        header="Notificación",
        is_open=False,
        dismissable=True,
        duration=4000, # 4 segundos
        icon="success",
        style={"position": "fixed", "top": 20, "right": 20, "width": 350, "zIndex": 2100},
    )

def mensaje_alerta_exito(tipo, mensaje):
    """
    Helper para retornar los valores correctos al callback.
    tipo: 'success', 'danger', 'warning', 'info'
    mensaje: Texto a mostrar
    Retorna: (is_open, children, icon/color)
    """
    # Mapeamos tipos a iconos/colores de Bootstrap
    valid_types = ["primary", "secondary", "success", "danger", "warning", "info", "light", "dark"]
    color = tipo if tipo in valid_types else "info"
    
>>>>>>> b74f1b0a886c27181c8264a954a4baf9f2b71029
    return True, mensaje, color