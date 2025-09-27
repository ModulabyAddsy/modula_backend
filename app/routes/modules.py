# app/routes/modules.py

from fastapi import APIRouter, Depends
from ..controller import module_controller
from ..services.security import get_current_active_user

# Creamos el router sin prefijo, tal como en tus otros archivos de rutas
router = APIRouter(
    tags=["Modules"] # Etiqueta para la documentación de FastAPI
)

@router.get("/manifest", summary="Obtener el manifiesto de módulos")
def get_manifest(current_user: dict = Depends(get_current_active_user)):
    """
    Endpoint seguro que devuelve la lista de módulos disponibles, sus
    versiones y URLs de descarga. Requiere un token de autenticación válido.
    """
    # El controlador se encarga de llamar al servicio y devolver los datos
    response = module_controller.list_available_modules()
    return response