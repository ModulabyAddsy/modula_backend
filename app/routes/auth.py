from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse
from app.services.models import RegistroCuenta
from app.controller import auth_controller

router = APIRouter()

@router.post("/registrar-cuenta")
async def registrar_cuenta(data: RegistroCuenta):
    return await auth_controller.registrar_cuenta(data)

@router.get("/verificar-cuenta", response_class=HTMLResponse)
async def verificar_cuenta(request: Request):
    return await auth_controller.verificar_cuenta(request)