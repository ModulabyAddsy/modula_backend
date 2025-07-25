# app/routes/sucursales.py
from fastapi import APIRouter, Depends, status
from app.controller import sucursal_controller
from app.services.models import Sucursal, SucursalCreate
from app.services.security import get_current_active_user

router = APIRouter(
    prefix="/sucursales",
    tags=["Sucursales"]
)

@router.post("/", response_model=Sucursal, status_code=status.HTTP_201_CREATED)
def endpoint_crear_sucursal(
    sucursal_data: SucursalCreate,
    current_user: dict = Depends(get_current_active_user)
):
    """
    Crea una nueva sucursal para la cuenta del usuario autenticado.
    Requiere un token JWT válido.
    """
    return sucursal_controller.registrar_nueva_sucursal(sucursal_data, current_user)