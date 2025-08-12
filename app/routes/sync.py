# app/routes/sync.py
from fastapi import APIRouter, Depends, UploadFile, File
from app.controller import sync_controller
from app.services.models import SyncCheckRequest, SyncCheckResponse, PlanSincronizacionResponse
from app.services.security import get_current_active_user
from fastapi.responses import StreamingResponse
from typing import Optional
from fastapi import Header, Depends, APIRouter # Header se importa desde fastapi

router = APIRouter(
    prefix="/sync",
    tags=["Sincronización"]
)

@router.post("/check", response_model=PlanSincronizacionResponse)
def endpoint_check_sync(
    sync_request: SyncCheckRequest,
    current_user: dict = Depends(get_current_active_user)
):
    """
    Recibe el estado de los archivos locales del cliente y devuelve un
    plan de acción para sincronizar el esquema y los datos.
    """
    return sync_controller.verificar_y_planificar_sincronizacion(sync_request, current_user)

@router.get("/download/{key_path:path}", response_class=StreamingResponse)
def endpoint_download_file(key_path: str, current_user: dict = Depends(get_current_active_user)):
    """
    Descarga un archivo específico de la nube del usuario.
    """
    return sync_controller.descargar_archivo_sincronizacion(key_path, current_user)

@router.post("/upload/{key_path:path}")
async def endpoint_upload_file(
    key_path: str,
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_active_user),
    x_base_version_hash: Optional[str] = Header(None) # Leemos el header personalizado
):
    """
    Sube un archivo del cliente a su nube, verificando conflictos.
    """
    return await sync_controller.subir_archivo_sincronizacion(key_path, file, current_user, x_base_version_hash)