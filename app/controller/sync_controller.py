# app/controller/sync_controller.py (Solo Lógica)

from fastapi import HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
import io
import sqlite3
import tempfile

# --- Importaciones de Lógica y Servicios ---
# (Nota: Ya no importamos APIRouter, Depends, etc. aquí)
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
    id_empresa = current_user['id_empresa_addsy']
    key_path = push_request.db_relative_path
    print(f"🔄 Recibiendo {len(push_request.records)} registros para fusionar en '{key_path}'")

    db_bytes = descargar_archivo_de_r2(key_path)
    if not db_bytes:
        raise HTTPException(status_code=404, detail=f"La base de datos '{key_path}' no se encontró en la nube.")

    with tempfile.NamedTemporaryFile(suffix=".sqlite") as tmp_db:
        # ... (El resto de la lógica de fusión de datos se mantiene exactamente igual) ...
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


def descargar_archivo_db_logic(key_path: str, current_user: dict):
    id_empresa = current_user['id_empresa_addsy']
    if not key_path.startswith(id_empresa):
        raise HTTPException(status_code=403, detail="Acceso denegado a este recurso.")
    
    contenido_bytes = descargar_archivo_de_r2(key_path)
    if contenido_bytes is None:
        raise HTTPException(status_code=404, detail="Archivo no encontrado en la nube.")
    
    return StreamingResponse(io.BytesIO(contenido_bytes), media_type="application/x-sqlite3")