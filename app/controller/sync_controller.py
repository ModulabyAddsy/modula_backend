# app/routes/sync_controller.py (Versión Completa y Funcional)
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
import io
import sqlite3
import tempfile

# --- Importaciones Corregidas y Completas ---
from app.services.security import get_current_user_from_token
from app.services.cloud.setup_empresa_cloud import (
    listar_archivos_con_metadata,
    descargar_archivo_de_r2,
    subir_archivo_a_r2,
    crear_estructura_base_empresa,
    crear_estructura_sucursal
)
from app.services.models import PushRecordsRequest
from app.services.db import get_sucursal_info
from app.controller.sync_logic import stage_1_align_cloud_files, stage_2_migrate_cloud_schemas # Lógica encapsulada

router = APIRouter()

# --- Endpoint 1: El nuevo punto de partida para la sincronización ---
@router.post("/sync/initialize")
async def inicializar_sincronizacion(current_user: dict = Depends(get_current_user_from_token)):
    """
    Orquesta las Etapas 1 y 2: Prepara la nube para la sincronización.
    """
    id_empresa = current_user['id_empresa_addsy']
    id_sucursal = current_user['id_sucursal']
    
    print(f"🚀 Iniciando sincronización para empresa '{id_empresa}', sucursal '{id_sucursal}'")

    # Obtenemos la ruta_cloud de la sucursal, ¡aquí usamos get_sucursal_info!
    sucursal = get_sucursal_info(id_sucursal)
    if not sucursal or not sucursal.get('ruta_cloud'):
        raise HTTPException(status_code=404, detail="No se encontró la configuración de la sucursal.")
    
    ruta_cloud_sucursal = sucursal['ruta_cloud']

    # --- ETAPA 1: ALINEACIÓN DE ARCHIVOS EN R2 ---
    # Usamos las funciones importadas para asegurar la estructura base.
    # Esta lógica es idempotente: si las carpetas ya existen, no hace nada dañino.
    await stage_1_align_cloud_files(id_empresa, ruta_cloud_sucursal)
    print("✅ Etapa 1: Estructura de archivos en la nube verificada y alineada.")

    # --- ETAPA 2: MIGRACIÓN DE ESQUEMAS EN R2 ---
    await stage_2_migrate_cloud_schemas(id_empresa, ruta_cloud_sucursal)
    print("✅ Etapa 2: Esquemas de bases de datos en la nube verificados y migrados.")

    # --- RESPUESTA: LISTA DE ARCHIVOS A DESCARGAR ---
    ruta_datos_generales = f"{id_empresa}/databases_generales/"
    
    archivos_generales = listar_archivos_con_metadata(ruta_datos_generales)
    archivos_sucursal = listar_archivos_con_metadata(ruta_cloud_sucursal)
    
    files_to_pull = [f['key'] for f in archivos_generales] + [f['key'] for f in archivos_sucursal]
    
    return {
        "status": "cloud_ready",
        "id_empresa": id_empresa,
        "files_to_pull": files_to_pull
    }


# --- Endpoint 2: El corazón de la sincronización de datos (sin cambios) ---
@router.post("/sync/push-records")
async def recibir_registros_locales(push_request: PushRecordsRequest, current_user: dict = Depends(get_current_user_from_token)):
    id_empresa = current_user['id_empresa_addsy']
    key_path = f"{id_empresa}/{push_request.db_relative_path}"
    print(f"🔄 Recibiendo {len(push_request.records)} registros para fusionar en '{key_path}'")

    db_bytes = descargar_archivo_de_r2(key_path)
    if not db_bytes:
        raise HTTPException(status_code=404, detail=f"La base de datos '{key_path}' no se encontró en la nube.")

    with tempfile.NamedTemporaryFile(suffix=".sqlite") as tmp_db:
        tmp_db.write(db_bytes)
        tmp_db.seek(0)
        conn = sqlite3.connect(tmp_db.name)
        cursor = conn.cursor()
        
        for record in push_request.records:
            columns = ", ".join(record.keys())
            placeholders = ", ".join(["?"] * len(record))
            update_assignments = ", ".join([f"{key} = excluded.{key}" for key in record.keys() if key != 'uuid'])
            sql = f"INSERT INTO {push_request.table_name} ({columns}) VALUES ({placeholders}) ON CONFLICT(uuid) DO UPDATE SET {update_assignments};"
            
            try:
                cursor.execute(sql, list(record.values()))
            except sqlite3.Error as e:
                conn.close()
                raise HTTPException(status_code=500, detail=f"Error de SQL al fusionar: {e}")

        conn.commit()
        conn.close()
        
        tmp_db.seek(0)
        updated_db_bytes = tmp_db.read()
        if not subir_archivo_a_r2(key_path, updated_db_bytes):
            raise HTTPException(status_code=500, detail="Error al resubir la base de datos fusionada a R2.")

    return JSONResponse(content={"status": "push_success", "merged_records": len(push_request.records)})


# --- Endpoint 3: Descarga segura de archivos (sin cambios) ---
@router.get("/sync/pull-db/{key_path:path}")
def descargar_archivo_db(key_path: str, current_user: dict = Depends(get_current_user_from_token)):
    id_empresa = current_user['id_empresa_addsy']
    if not key_path.startswith(id_empresa):
        raise HTTPException(status_code=403, detail="Acceso denegado a este recurso.")
    
    contenido_bytes = descargar_archivo_de_r2(key_path)
    if contenido_bytes is None:
        raise HTTPException(status_code=404, detail="Archivo no encontrado en la nube.")
    
    return StreamingResponse(io.BytesIO(contenido_bytes), media_type="application/x-sqlite3")