# app/routes/terminal.py
from fastapi import APIRouter, Depends
from typing import List
from app.controller import terminal_controller
from app.services.models import Terminal, TerminalCreate
from app.services.security import get_current_active_user

router = APIRouter()

@router.get("/mi-cuenta", response_model=List[Terminal])
def leer_terminales_usuario(current_user: dict = Depends(get_current_active_user)):
    """Endpoint protegido para listar todas las terminales de la cuenta."""
    return terminal_controller.get_mis_terminales(current_user)

@router.post("/", response_model=Terminal, status_code=201)
def crear_nueva_terminal(terminal: TerminalCreate, current_user: dict = Depends(get_current_active_user)):
    """Endpoint protegido para registrar una nueva terminal."""
    return terminal_controller.registrar_nueva_terminal(terminal, current_user)