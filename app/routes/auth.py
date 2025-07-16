# ✅ Importaciones necesarias de FastAPI y componentes propios del proyecto
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse
# ✅ Modelo de datos que valida los campos del formulario de registro
from app.services.models import RegistroCuenta
# ✅ Controlador donde está la lógica principal del registro y verificación
from app.controller import auth_controller

# ✅ Crear un enrutador para agrupar endpoints relacionados con autenticación
router = APIRouter()


# ✅ Endpoint para registrar una cuenta nueva
# Este endpoint recibe un objeto tipo RegistroCuenta y delega la lógica al controlador
@router.post("/registrar-cuenta")
async def registrar_cuenta(data: RegistroCuenta):
    return await auth_controller.registrar_cuenta(data)


# ✅ Endpoint para verificar cuenta desde el enlace con token (HTML)
# Se recibe el token por parámetro en la URL y se pasa al controlador
@router.get("/verificar-cuenta", response_class=HTMLResponse)
async def verificar_cuenta(request: Request):
    return await auth_controller.verificar_cuenta(request)