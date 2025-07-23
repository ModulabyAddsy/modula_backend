# app/controller/terminal_controller.py
from fastapi import HTTPException
from app.services.db import get_terminales_por_cuenta, crear_terminal
from app.services.models import TerminalCreate

def get_mis_terminales(current_user: dict):
    """Obtiene las terminales del usuario actualmente autenticado."""
    id_cuenta = current_user.get('id')
    return get_terminales_por_cuenta(id_cuenta)

def registrar_nueva_terminal(terminal_data: TerminalCreate, current_user: dict):
    """Registra una nueva terminal para la cuenta del usuario."""
    id_cuenta = current_user.get('id')
    nueva_terminal = crear_terminal(id_cuenta, terminal_data.dict())
    if not nueva_terminal:
        raise HTTPException(status_code=500, detail="Error al registrar la nueva terminal en la base de datos.")
    return nueva_terminal