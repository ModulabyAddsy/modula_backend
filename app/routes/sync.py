# app/routes/sync.py
from fastapi import APIRouter, Depends
from app.controller import sync_controller
from app.services.models import SyncCheckRequest, SyncCheckResponse
from app.services.security import get_current_active_user

router = APIRouter(
    prefix="/sync",
    tags=["Sincronización"]
)

@router.post("/check", response_model=SyncCheckResponse)
def endpoint_check_sync(
    sync_request: SyncCheckRequest,
    current_user: dict = Depends(get_current_active_user)
):
    """
    Recibe el estado de los archivos locales del cliente y devuelve un
    plan de acción para sincronizar el esquema y los datos.
    """
    return sync_controller.verificar_y_planificar_sincronizacion(sync_request, current_user)