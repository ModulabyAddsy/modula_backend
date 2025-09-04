# app/controller/sync_controller.py (Solo Lógica)

from fastapi import HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
import io
import logging
import sqlite3
import tempfile
import os

# --- Importaciones de Lógica y Servicios ---
from app.services.cloud.setup_empresa_cloud import (
    listar_archivos_con_metadata,
    descargar_archivo_de_r2,
    subir_archivo_a_r2
)
from app.services.models import PushRecordsRequest
from app.services.db import get_sucursal_info
from app.controller.sync_logic import stage_1_align_cloud_files, stage_2_migrate_cloud_schemas


# --- Las funciones de lógica ahora son independientes ---

async def inicializar_sincronizacion_logic(current_user: dict):
    id_empresa = current_user['id_empresa_addsy']
    id_sucursal = current_user['id_sucursal']
    print(f"🚀 Iniciando sincronización para empresa '{id_empresa}', sucursal '{id_sucursal}'")

    sucursal = get_sucursal_info(id_sucursal)
    if not sucursal or not sucursal.get('ruta_cloud'):
        raise HTTPException(status_code=404, detail="No se encontró la configuración de la sucursal.")
    ruta_cloud_sucursal = sucursal['ruta_cloud']

    await stage_1_align_cloud_files(id_empresa, ruta_cloud_sucursal)
    print("✅ Etapa 1: Estructura de archivos en la nube verificada y alineada.")

    await stage_2_migrate_cloud_schemas(id_empresa, ruta_cloud_sucursal)
    print("✅ Etapa 2: Esquemas de bases de datos en la nube verificados y migrados.")

    ruta_datos_generales = f"{id_empresa}/databases_generales/"
    archivos_generales = listar_archivos_con_metadata(ruta_datos_generales)
    archivos_sucursal = listar_archivos_con_metadata(ruta_cloud_sucursal)
    files_to_pull = [f['key'] for f in archivos_generales] + [f['key'] for f in archivos_sucursal]
    
    return {
        "status": "cloud_ready",
        "id_empresa": id_empresa,
        "files_to_pull": files_to_pull
    }


async def recibir_registros_locales_logic(push_request: PushRecordsRequest, current_user: dict):
    """
    Lógica definitiva de sincronización. El UUID es el ancla para inserciones y actualizaciones.
    """
    logging.warning("--- ✅ EJECUTANDO LÓGICA DE SINCRONIZACIÓN DEFINITIVA BASADA EN UUID ---")

    key_path = f"{push_request.db_relative_path}"
    
    logging.info(f"🔄 Sincronizando {len(push_request.records)} registros para '{key_path}' usando PK='{push_request.primary_key_column}'")
    
    db_bytes = descargar_archivo_de_r2(key_path)
    if not db_bytes:
        raise HTTPException(status_code=404, detail=f"El archivo '{push_request.db_relative_path}' no existe en la nube.")

    temp_file_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False) as tmp_db:
            temp_file_path = tmp_db.name
            tmp_db.write(db_bytes)

        conn = sqlite3.connect(temp_file_path)
        cursor = conn.cursor()
        
        for record in push_request.records:
            columns = ", ".join(record.keys())
            placeholders = ", ".join(["?"] * len(record))
            pk_column = push_request.primary_key_column # Ahora será 'uuid'
            
            # --- ▼▼▼ LÓGICA DE UPDATE MEJORADA ▼▼▼ ---
            # Excluimos la PK ('uuid') y también el 'id' numérico del update.
            # El 'id' de la nube NUNCA debe ser modificado por un cliente.
            update_assignments = ", ".join([f"{key} = excluded.{key}" for key in record.keys() if key not in [pk_column, 'id']])
            # --- ▲▲▲ FIN DE LA MEJORA ▲▲▲ ---

            sql = (f"INSERT INTO {push_request.table_name} ({columns}) VALUES ({placeholders}) "
                   f"ON CONFLICT({pk_column}) DO UPDATE SET {update_assignments} "
                   f"WHERE excluded.last_modified > {push_request.table_name}.last_modified;")

            try:
                cursor.execute(sql, list(record.values()))
            except sqlite3.Error as e:
                logging.error(f"Error de SQL: {e}")
                conn.close()
                raise HTTPException(status_code=409, detail=f"Conflicto de SQL: {e}")
        
        conn.commit()
        conn.close()

        with open(temp_file_path, "rb") as f:
            updated_db_bytes = f.read()

        if not subir_archivo_a_r2(key_path, updated_db_bytes):
            raise HTTPException(status_code=500, detail="Error al resubir la base de datos a R2.")

    finally:
        if temp_file_path and os.path.exists(temp_file_path):
            os.remove(temp_file_path)

    return JSONResponse(content={"status": "push_success", "merged_records": len(push_request.records)})


def descargar_archivo_db_logic(key_path: str, current_user: dict):
    id_empresa = current_user['id_empresa_addsy']
    if not key_path.startswith(id_empresa):
        raise HTTPException(status_code=403, detail="Acceso denegado a este recurso.")
    
    contenido_bytes = descargar_archivo_de_r2(key_path)
    if contenido_bytes is None:
        raise HTTPException(status_code=404, detail="Archivo no encontrado en la nube.")
    
    return StreamingResponse(io.BytesIO(contenido_bytes), media_type="application/x-sqlite3")