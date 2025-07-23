# app/controller/suscripcion_controller.py
from fastapi import HTTPException
from app.services.db import get_suscripciones_por_cuenta

def get_mis_suscripciones(current_user: dict):
    """
    Obtiene las suscripciones del usuario actualmente autenticado.
    'current_user' es inyectado por la dependencia de seguridad.
    """
    id_cuenta = current_user.get('id')
    suscripciones = get_suscripciones_por_cuenta(id_cuenta)
    if not suscripciones:
        # Esto no debería pasar si el flujo de registro es correcto, pero es un buen control
        raise HTTPException(status_code=404, detail="No se encontraron suscripciones para esta cuenta.")
    return suscripciones