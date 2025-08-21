# app/routes/update.py
from fastapi import APIRouter, Query, HTTPException, Response
from fastapi.responses import JSONResponse
from app.controller import update_controller

router = APIRouter()

@router.get("/check", summary="Verifica si hay una nueva versión del software")
async def check_for_updates_route(version: str = Query(..., description="La versión actual del cliente")):
    """
    Compara la versión del cliente con la última versión disponible.
    """
    # La ruta ahora solo llama al controlador
    result = update_controller.check_for_updates_logic(version)
    
    status = result.get("status")

    if status == "up-to-date":
        return Response(status_code=204) # 204 No Content
        
    elif status == "update-available":
        return JSONResponse(content=result.get("data"))
        
    else: # status == "error"
        raise HTTPException(status_code=503, detail=result.get("message"))