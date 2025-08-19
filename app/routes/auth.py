# app/routes/auth.py
from fastapi import APIRouter, Request, HTTPException, Depends 
from fastapi.responses import HTMLResponse
from app.services.models import RegistroCuenta
from app.controller import auth_controller
from app.services.models import LoginData, Token


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

@router.post(
    "/verificar-terminal",
    response_model=models.TerminalVerificationResponse,
    summary="Verifica una terminal al arranque",
    tags=["Autenticación"]
)
async def verificar_terminal_activa_route(
    request_data: models.TerminalVerificationRequest, 
    request: Request 
):
    """
    Verifica si un ID de terminal es válido y está activo.
    Si es exitoso, devuelve un token de acceso y datos de la sesión.
    """
    # Llama a la función del controlador que contiene toda la lógica.
    # La ruta se mantiene limpia y solo se encarga de recibir la petición
    # y devolver la respuesta.
    return await auth_controller.verificar_terminal_activa_controller(
        request_data=request_data,
        client_ip=request.client.host
    )

@router.post("/login", response_model=Token)
async def login(data: LoginData, request: Request): # <-- 1. Añadir request: Request
    """Endpoint para iniciar sesión y obtener un token JWT."""
    # 2. Pasar el client_ip al controlador
    return await auth_controller.login_para_access_token(data, client_ip=request.client.host)

@router.get("/check-activation-status/{claim_token}", response_model=models.ActivationStatusResponse)
async def check_activation_status_route(claim_token: str):
    return await auth_controller.check_activation_status(claim_token)

@router.post("/solicitar-reseteo")
async def solicitar_reseteo_route(data: models.SolicitudReseteo):
    return await auth_controller.solicitar_reseteo_contrasena(data)

@router.get("/pagina-reseteo", response_class=HTMLResponse)
async def pagina_reseteo_route(token: str):
    return await auth_controller.mostrar_pagina_reseteo(token)

@router.post("/ejecutar-reseteo", response_class=HTMLResponse)
async def ejecutar_reseteo_route(request: Request):
    return await auth_controller.ejecutar_reseteo_contrasena(request)