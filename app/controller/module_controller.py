# app/controller/module_controller.py

from fastapi import HTTPException
from ..services import module_service

def list_available_modules():
    """
    Orquesta la obtención de la lista de módulos disponibles, incluyendo
    sus URLs de descarga seguras.
    """
    try:
        # Llamamos a la función del servicio que ya está preparada para enriquecer los datos
        modules = module_service.get_active_modules()
        
        return {"status": "ok", "modules": modules}
    except Exception as e:
        print(f"🔥🔥 ERROR en el controlador de módulos: {e}")
        raise HTTPException(status_code=500, detail="Error interno al procesar la solicitud de módulos.")