# app/routes/sync.py (Responsable de las Rutas de API)

from fastapi import APIRouter, Depends
from app.services.security import get_current_user_from_token
from app.services.models import PushRecordsRequest

# Importamos las funciones de LÓGICA desde el controlador
from app.controller.sync_controller import (
    inicializar_sincronizacion_logic,
    recibir_registros_locales_logic,
    descargar_archivo_db_logic
)

router = APIRouter()

@router.post("/initialize")
async def inicializar_sincronizacion_route(current_user: dict = Depends(get_current_user_from_token)):
    return await inicializar_sincronizacion_logic(current_user)


@router.post("/push-records")
async def recibir_registros_locales_route(push_request: PushRecordsRequest, current_user: dict = Depends(get_current_user_from_token)):
    return await recibir_registros_locales_logic(push_request, current_user)


@router.get("/pull-db/{key_path:path}")
def descargar_archivo_db_route(key_path: str, current_user: dict = Depends(get_current_user_from_token)):
    return descargar_archivo_db_logic(key_path, current_user)