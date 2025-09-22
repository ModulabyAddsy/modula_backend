# app/routes/auth.py
from fastapi import APIRouter, Request, HTTPException, Depends 
from fastapi.responses import HTMLResponse
from app.services.models import RegistroCuenta
from app.controller import auth_controller
from app.services.models import LoginData, Token
from typing import Union

from sqlalchemy.orm import Session
from fastapi import APIRouter, Depends
from app.services import models
from fastapi import Form

router = APIRouter()

# --- CORRECCIÓN AQUÍ ---
# El endpoint sigue siendo /registrar-cuenta, pero ahora llama a la función
# con su nuevo nombre: registrar_cuenta_y_crear_pago
@router.post("/registrar-cuenta")
async def registrar_cuenta(data: RegistroCuenta):
    # Llamamos a la función renombrada en el controlador
    return await auth_controller.registrar_cuenta_y_crear_pago(data)


# Este endpoint para verificar la cuenta ya está correcto.
@router.get("/verificar-cuenta", response_class=HTMLResponse)
async def verificar_cuenta(request: Request):
    return await auth_controller.verificar_cuenta(request)

@router.post("/login", response_model=Token)
async def login(data: LoginData, request: Request): # 1. Añadir 'request: Request'
    """Endpoint para iniciar sesión y obtener un token JWT."""
    # 2. Pasar el client_ip al controlador
    return await auth_controller.login_para_access_token(
        form_data=data, 
        client_ip=request.client.host
    )

# --- Endpoint para la verificación de terminal en el arranque ---

# --- PUNTO DE VERIFICACIÓN UNIFICADO Y CORREGIDO ---
# --- PUNTO DE VERIFICACIÓN ÚNICO Y OFICIAL ---
@router.post(
    "/verificar-terminal", # Esta es la ruta que usará toda la aplicación
    # El modelo de respuesta necesita ser flexible
    response_model=Union[models.TerminalVerificationResponse, dict],
    summary="Verifica una terminal usando red local y comprueba suscripción",
    tags=["Autenticación"]
)
def verificar_terminal_route(
    request_data: models.TerminalVerificationRequest, 
    request: Request 
):
    """
    Endpoint único y robusto para la verificación de terminales al arranque.
    """
    return auth_controller.verificar_y_autorizar_terminal(
        request_data=request_data,
        client_ip=request.client.host
    )

@router.get("/check-activation-status/{claim_token}", response_model=models.ActivationStatusResponse)
async def check_activation_status_route(claim_token: str):
    return await auth_controller.check_activation_status(claim_token)

@router.post("/solicitar-reseteo")
async def solicitar_reseteo_route(data: models.SolicitudReseteo):
    data.email = data.email.lower().strip()
    return await auth_controller.solicitar_reseteo_contrasena(data)

@router.get("/pagina-reseteo", response_class=HTMLResponse)
async def pagina_reseteo_route(token: str):
    return await auth_controller.mostrar_pagina_reseteo(token)

@router.post("/ejecutar-reseteo", response_class=HTMLResponse)
async def ejecutar_reseteo_route(request: Request):
    return await auth_controller.ejecutar_reseteo_contrasena(request)
