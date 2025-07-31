from fastapi import APIRouter, Depends, Request
from typing import List
from app.controller import terminal_controller
from app.services.security import get_current_active_user
from app.services.models import (Terminal, TerminalCreate, AsignarTerminalRequest, 
                                 CrearSucursalYAsignarRequest, Token)

router = APIRouter()

@router.get("/mi-cuenta", response_model=List[Terminal])
def leer_terminales_usuario(current_user: dict = Depends(get_current_active_user)):
    """Endpoint protegido para listar todas las terminales de la cuenta."""
    return terminal_controller.get_mis_terminales(current_user)

@router.post("/", response_model=Terminal, status_code=201)
def crear_nueva_terminal(terminal: TerminalCreate, current_user: dict = Depends(get_current_active_user)):
    """Endpoint protegido para registrar una nueva terminal."""
    return terminal_controller.registrar_nueva_terminal(terminal, current_user)

@router.post("/asignar-a-sucursal", status_code=200)
def endpoint_asignar_terminal(
    # ✅ CORRECCIÓN: 'request' debe ir antes de los argumentos con valor por defecto.
    request: Request, 
    request_data: AsignarTerminalRequest,
    current_user: dict = Depends(get_current_active_user)
):
    """Asigna o migra una terminal a una sucursal existente."""
    return terminal_controller.migrar_terminal_a_sucursal(request_data, current_user, request)

@router.post("/crear-sucursal-y-asignar", response_model=Token, status_code=201)
def endpoint_crear_sucursal_y_asignar(
    # ✅ CORRECCIÓN: 'request' debe ir antes de los argumentos con valor por defecto.
    request: Request,
    request_data: CrearSucursalYAsignarRequest,
    current_user: dict = Depends(get_current_active_user)
):
    """Crea una nueva sucursal y le asigna la terminal de origen."""
    return terminal_controller.crear_sucursal_y_asignar_terminal(request_data, current_user, request)