# app/controller/sync_controller.py
from app.services.models import SyncCheckRequest, SyncCheckResponse, SyncSchemaAction, SyncDataAction
from app.services.cloud.setup_empresa_cloud import listar_archivos_con_metadata
from app.services.db import buscar_terminal_activa_por_id
from app.services.cloud.setup_empresa_cloud import descargar_archivo_de_r2, subir_archivo_a_r2
from fastapi.responses import StreamingResponse
from fastapi import HTTPException, UploadFile
import io

MODELO_DATABASES_GENERALES = "_modelo/databases_generales/"
MODELO_DATABASES_SUCURSAL = "_modelo/plantilla_sucursal/"

def verificar_y_planificar_sincronizacion(sync_request: SyncCheckRequest, current_user: dict):
    id_empresa = current_user['id_empresa_addsy']
    id_sucursal = sync_request.id_sucursal_actual

    # Rutas específicas para este cliente
    ruta_cliente_generales = f"{id_empresa}/databases_generales/"
    ruta_cliente_sucursal = f"{id_empresa}/suc_{id_sucursal}/"

    # 1. --- VERIFICACIÓN DE ESQUEMA ---
    schema_actions = []
    
    # Comparamos las bases de datos generales
    archivos_modelo_generales = {f['key'].split('/')[-1]: f for f in listar_archivos_con_metadata(MODELO_DATABASES_GENERALES)}
    archivos_cliente_generales = {f['key'].split('/')[-1]: f for f in listar_archivos_con_metadata(ruta_cliente_generales)}

    for nombre_archivo, data_modelo in archivos_modelo_generales.items():
        if nombre_archivo not in archivos_cliente_generales:
            schema_actions.append(SyncSchemaAction(
                key_origen=data_modelo['key'],
                key_destino=f"{ruta_cliente_generales}{nombre_archivo}"
            ))

    # Comparamos las bases de datos de sucursal
    archivos_modelo_sucursal = {f['key'].split('/')[-1]: f for f in listar_archivos_con_metadata(MODELO_DATABASES_SUCURSAL)}
    archivos_cliente_sucursal = {f['key'].split('/')[-1]: f for f in listar_archivos_con_metadata(ruta_cliente_sucursal)}

    for nombre_archivo, data_modelo in archivos_modelo_sucursal.items():
        if nombre_archivo not in archivos_cliente_sucursal:
            schema_actions.append(SyncSchemaAction(
                key_origen=data_modelo['key'],
                key_destino=f"{ruta_cliente_sucursal}{nombre_archivo}"
            ))

    # 2. --- VERIFICACIÓN DE DATOS (TIMESTAMP) ---
    data_actions = []
    archivos_locales_dict = {f.key: f for f in sync_request.archivos_locales}
    
    # Combinamos todos los archivos del cliente en la nube
    todos_archivos_cloud = {**archivos_cliente_generales, **archivos_cliente_sucursal}

    for nombre_archivo, data_cloud in todos_archivos_cloud.items():
        key_cloud_completa = data_cloud['key']
        if key_cloud_completa in archivos_locales_dict:
            # El archivo existe en ambos lados, comparamos fechas
            fecha_local = archivos_locales_dict[key_cloud_completa].last_modified
            fecha_cloud = data_cloud['last_modified']
            
            if fecha_cloud > fecha_local:
                data_actions.append(SyncDataAction(accion="descargar_actualizacion", key=key_cloud_completa))
            elif fecha_local > fecha_cloud:
                data_actions.append(SyncDataAction(accion="subir_actualizacion", key=key_cloud_completa))
        else:
            # El archivo existe en la nube pero no localmente, hay que descargarlo
            data_actions.append(SyncDataAction(accion="descargar_actualizacion", key=key_cloud_completa))
            
    return SyncCheckResponse(schema_actions=schema_actions, data_actions=data_actions)

def descargar_archivo_sincronizacion(key_path: str, current_user: dict):
    # (En una versión futura, validaríamos que el 'key_path' pertenece al 'current_user')
    contenido_bytes = descargar_archivo_de_r2(key_path)
    if contenido_bytes is None:
        raise HTTPException(status_code=404, detail="Archivo no encontrado en la nube.")
    
    return StreamingResponse(io.BytesIO(contenido_bytes), media_type="application/x-sqlite3")

async def subir_archivo_sincronizacion(key_path: str, file: UploadFile, current_user: dict):
    contenido_bytes = await file.read()
    if subir_archivo_a_r2(key_path, contenido_bytes):
        return {"status": "ok", "message": "Archivo subido exitosamente."}
    else:
        raise HTTPException(status_code=500, detail="Error al subir el archivo a la nube.")