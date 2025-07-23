# app/routes/suscripcion_routes.py
from fastapi import APIRouter, Depends
from typing import List
from app.services.models import Suscripcion
from app.controller import suscripcion_controller
from app.services.security import get_current_active_user

router = APIRouter()

@router.get("/mi-cuenta", response_model=List[Suscripcion])
def leer_suscripciones_usuario(current_user: dict = Depends(get_current_active_user)):
    """
    Endpoint protegido para obtener las suscripciones del usuario que realiza la petición.
    """
    return suscripcion_controller.get_mis_suscripciones(current_user)