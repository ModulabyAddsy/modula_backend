# app/routes/auth.py
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse
from app.services.models import RegistroCuenta
from app.controller import auth_controller

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