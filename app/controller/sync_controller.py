# app/controller/sync_controller.py
from app.services.models import SyncCheckRequest, SyncCheckResponse, SyncSchemaAction, SyncDataAction
from app.services.cloud.setup_empresa_cloud import listar_archivos_con_metadata
from app.services.db import buscar_terminal_activa_por_id
from app.services.cloud.setup_empresa_cloud import descargar_archivo_de_r2, subir_archivo_a_r2, obtener_metadata_de_r2
from fastapi.responses import StreamingResponse
from fastapi import HTTPException, UploadFile, Response, status # Añadir Response y status
import io
import sqlite3
import tempfile
from botocore.exceptions import ClientError

MODELO_DATABASES_GENERALES = "_modelo/databases_generales/"
MODELO_DATABASES_SUCURSAL = "_modelo/plantilla_sucursal/"

def descargar_archivo_sincronizacion(key_path: str, current_user: dict):
    # (En una versión futura, validaríamos que el 'key_path' pertenece al 'current_user')
    contenido_bytes = descargar_archivo_de_r2(key_path)
    if contenido_bytes is None:
        raise HTTPException(status_code=404, detail="Archivo no encontrado en la nube.")
    
    return StreamingResponse(io.BytesIO(contenido_bytes), media_type="application/x-sqlite3")

async def subir_archivo_sincronizacion(key_path: str, file: UploadFile, current_user: dict, base_hash: str | None):
    # Obtener el hash del archivo actual en la nube (si existe)
    metadata_nube = obtener_metadata_de_r2(key_path) # Necesitarás una función que solo traiga la metadata
    hash_actual_nube = metadata_nube.get('httpEtag') if metadata_nube else None

    # Si el cliente envió un hash base y no coincide con el hash actual, hay un conflicto
    if base_hash and hash_actual_nube and base_hash != hash_actual_nube:
        return Response(status_code=status.HTTP_409_CONFLICT, content="Conflicto: La versión en la nube ha cambiado.")

    # Si no hay conflicto, proceder con la subida
    contenido_bytes = await file.read()
    if subir_archivo_a_r2(key_path, contenido_bytes):
        return {"status": "ok", "message": "Archivo subido exitosamente."}
    else:
        raise HTTPException(status_code=500, detail="Error al subir el archivo a la nube.")
    
def _get_table_schema(cursor, table_name):
    """Obtiene el esquema y las columnas de una tabla."""
    # Obtener la sentencia CREATE TABLE original
    cursor.execute(f"SELECT sql FROM sqlite_master WHERE type='table' AND name='{table_name}'")
    create_sql = cursor.fetchone()[0]
    
    # Obtener la información detallada de las columnas
    cursor.execute(f"PRAGMA table_info('{table_name}')")
    columns_info = cursor.fetchall()
    # columns_info es una lista de tuplas: (cid, name, type, notnull, default_value, pk)
    return create_sql, {info[1]: info for info in columns_info}

def comparar_esquemas_db(bytes_db_modelo: bytes, bytes_db_cliente: bytes) -> list[str]:
    """
    Compara dos bases de datos SQLite (en bytes) y devuelve una lista de comandos SQL 
    necesarios para que la DB del cliente coincida con el esquema del modelo.
    """
    comandos_sql = []
    
    # Usar archivos temporales para trabajar con las bases de datos en memoria
    with tempfile.NamedTemporaryFile() as tmp_modelo, tempfile.NamedTemporaryFile() as tmp_cliente:
        tmp_modelo.write(bytes_db_modelo)
        tmp_cliente.write(bytes_db_cliente)
        tmp_modelo.seek(0)
        tmp_cliente.seek(0)

        conn_modelo = sqlite3.connect(tmp_modelo.name)
        conn_cliente = sqlite3.connect(tmp_cliente.name)
        cur_modelo = conn_modelo.cursor()
        cur_cliente = conn_cliente.cursor()

        # Obtener listas de tablas
        cur_modelo.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tablas_modelo = {row[0] for row in cur_modelo.fetchall()}
        cur_cliente.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tablas_cliente = {row[0] for row in cur_cliente.fetchall()}

        # 1. Detectar tablas faltantes en el cliente
        tablas_a_crear = tablas_modelo - tablas_cliente
        for tabla in tablas_a_crear:
            create_sql, _ = _get_table_schema(cur_modelo, tabla)
            comandos_sql.append(create_sql)

        # 2. Detectar columnas faltantes en tablas existentes
        tablas_comunes = tablas_modelo.intersection(tablas_cliente)
        for tabla in tablas_comunes:
            _, cols_modelo_info = _get_table_schema(cur_modelo, tabla)
            _, cols_cliente_info = _get_table_schema(cur_cliente, tabla)
            
            columnas_faltantes = set(cols_modelo_info.keys()) - set(cols_cliente_info.keys())
            
            for col_name in columnas_faltantes:
                # Construir el comando ALTER TABLE
                col_info = cols_modelo_info[col_name]
                col_type = col_info[2]
                default_val = col_info[4]
                not_null = col_info[3]
                
                comando = f"ALTER TABLE {tabla} ADD COLUMN {col_name} {col_type}"
                if not_null:
                    comando += " NOT NULL"
                if default_val is not None:
                    comando += f" DEFAULT {default_val}" # Cuidado con strings, necesitan comillas
                
                comandos_sql.append(comando + ";")

        conn_modelo.close()
        conn_cliente.close()
        
    return comandos_sql

def verificar_y_planificar_sincronizacion(sync_request: SyncCheckRequest, current_user: dict):
    """
    Genera un plan de sincronización inteligente comparando esquemas, fechas y hashes de contenido.
    """
    id_empresa = current_user['id_empresa_addsy']
    id_sucursal_actual = sync_request.id_sucursal_actual
    
    plan_acciones = []

    # --- RUTAS EN LA NUBE ---
    MODELO_GENERALES = "_modelo/databases_generales/"
    MODELO_SUCURSAL = "_modelo/plantilla_sucursal/"
    RUTA_DATOS_GENERALES = f"{id_empresa}/databases_generales/"
    RUTA_DATOS_SUCURSAL = f"{id_empresa}/suc_{id_sucursal_actual}/"

    # Convierte la lista de archivos locales en un diccionario para búsquedas rápidas
    archivos_locales = {f.key: f for f in sync_request.archivos_locales}

    # --- FUNCIÓN DE AYUDA INTERNA ---
    def procesar_conjunto_de_dbs(ruta_modelo, ruta_datos, tipo_db):
        archivos_cloud_modelo = {f['key'].split('/')[-1]: f for f in listar_archivos_con_metadata(ruta_modelo)}
        
        # Maneja el caso en que un directorio en la nube pueda no existir o estar vacío
        try:
            archivos_cloud_datos = {f['key'].split('/')[-1]: f for f in listar_archivos_con_metadata(ruta_datos)}
        except (ClientError, TypeError, Exception):
            archivos_cloud_datos = {}

        for nombre_db, meta_modelo in archivos_cloud_modelo.items():
            key_modelo = meta_modelo['key']
            key_datos_nube = f"{ruta_datos}{nombre_db}"
            ruta_relativa_cliente = f"{tipo_db}/{nombre_db}"

            if nombre_db not in archivos_cloud_datos:
                # CASO 1: La DB del modelo no existe para este cliente, se descarga por primera vez.
                plan_acciones.append({
                    "accion": "descargar_db_modelo",
                    "origen_cloud": key_modelo,
                    "destino_relativo": ruta_relativa_cliente
                })
            else:
                # CASO 2: La DB ya existe, se procede a comparar.
                meta_datos = archivos_cloud_datos[nombre_db]

                # Comparación de Esquema (sin cambios)
                bytes_modelo = descargar_archivo_de_r2(key_modelo)
                bytes_cliente = descargar_archivo_de_r2(key_datos_nube)
                comandos_sql = comparar_esquemas_db(bytes_modelo, bytes_cliente)
                
                if comandos_sql:
                    plan_acciones.append({
                        "accion": "migrar_esquema",
                        "db_relativa": ruta_relativa_cliente,
                        "comandos_sql": comandos_sql
                    })

                # --- LÓGICA DE SINCRONIZACIÓN DE DATOS MODIFICADA ---
                key_local_completa = f"{id_empresa}/{ruta_relativa_cliente}"
                archivo_local_info = archivos_locales.get(key_local_completa)
                hash_cloud = meta_datos.get('httpEtag')

                if archivo_local_info:  # El archivo existe en el cliente
                    hash_local = archivo_local_info.hash
                    
                    # Solo actuar si los contenidos (hashes) son diferentes
                    if hash_local != hash_cloud:
                        fecha_local = archivo_local_info.last_modified
                        fecha_cloud = meta_datos['LastModified']
                        
                        if fecha_cloud > fecha_local:
                            # La nube es más reciente, se descarga
                            plan_acciones.append({
                                "accion": "actualizar_datos", 
                                "key_cloud": key_datos_nube, 
                                "destino_relativo": ruta_relativa_cliente
                            })
                        else:
                            # El local es más reciente, se sube
                            plan_acciones.append({
                                "accion": "subir_db", 
                                "origen_relativo": ruta_relativa_cliente, 
                                "key_cloud": key_datos_nube,
                                "hash_base": hash_cloud  # Se envía el hash de la nube como base para el control de conflictos
                            })
                else:
                    # El archivo no existe localmente, se debe descargar
                    plan_acciones.append({
                        "accion": "actualizar_datos", 
                        "key_cloud": key_datos_nube, 
                        "destino_relativo": ruta_relativa_cliente
                    })

    # --- EJECUCIÓN DEL PROCESO ---
    plan_acciones.append({"accion": "ensure_dir", "ruta_relativa": "databases_generales/"})
    plan_acciones.append({"accion": "ensure_dir", "ruta_relativa": f"suc_{id_sucursal_actual}/"})

    procesar_conjunto_de_dbs(MODELO_GENERALES, RUTA_DATOS_GENERALES, "databases_generales")
    procesar_conjunto_de_dbs(MODELO_SUCURSAL, RUTA_DATOS_SUCURSAL, f"suc_{id_sucursal_actual}")

    return {
        "status": "plan_generado",
        "id_empresa": id_empresa,
        "id_sucursal_activa": id_sucursal_actual,
        "acciones": plan_acciones
    }
