# app/controller/sync_controller.py
from app.services.models import SyncCheckRequest, SyncCheckResponse, SyncSchemaAction, SyncDataAction
from app.services.cloud.setup_empresa_cloud import listar_archivos_con_metadata
from app.services.db import buscar_terminal_activa_por_id
from app.services.cloud.setup_empresa_cloud import descargar_archivo_de_r2, subir_archivo_a_r2
from fastapi.responses import StreamingResponse
from fastapi import HTTPException, UploadFile
import io
import sqlite3
import tempfile

MODELO_DATABASES_GENERALES = "_modelo/databases_generales/"
MODELO_DATABASES_SUCURSAL = "_modelo/plantilla_sucursal/"

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
    id_empresa = current_user['id_empresa_addsy']
    id_sucursal_actual = sync_request.id_sucursal_actual
    
    plan_acciones = []

    # --- RUTAS EN LA NUBE ---
    # Rutas del modelo de la aplicación
    MODELO_GENERALES = "_modelo/databases_generales/"
    MODELO_SUCURSAL = "_modelo/plantilla_sucursal/"
    
    # Rutas de los datos específicos de la empresa
    # La estructura es: ID_EMPRESA/TIPO/NOMBRE_DB.sqlite
    # ej: MOD_EMP_1001/databases_generales/clientes.sqlite
    # ej: MOD_EMP_1001/suc_25/ventas.sqlite
    RUTA_DATOS_GENERALES = f"{id_empresa}/databases_generales/"
    RUTA_DATOS_SUCURSAL = f"{id_empresa}/suc_{id_sucursal_actual}/"

    archivos_locales = {f.key: f for f in sync_request.archivos_locales}

    # --- FUNCIÓN DE AYUDA INTERNA ---
    def procesar_conjunto_de_dbs(ruta_modelo, ruta_datos, tipo_db):
        """Procesa un conjunto (generales o de sucursal) para generar acciones."""
        archivos_cloud_modelo = {f['key'].split('/')[-1]: f for f in listar_archivos_con_metadata(ruta_modelo)}
        archivos_cloud_datos = {f['key'].split('/')[-1]: f for f in listar_archivos_con_metadata(ruta_datos)}

        for nombre_db, meta_modelo in archivos_cloud_modelo.items():
            key_modelo = meta_modelo['key']
            key_datos_nube = f"{ruta_datos}{nombre_db}"
            
            # La ruta relativa que usará el cliente para guardar el archivo
            ruta_relativa_cliente = f"{tipo_db}/{nombre_db}"

            if nombre_db not in archivos_cloud_datos:
                # CASO 1: La DB del modelo no existe para este cliente. Hay que crearla.
                plan_acciones.append({
                    "accion": "descargar_db_modelo",
                    "origen_cloud": key_modelo,
                    "destino_relativo": ruta_relativa_cliente
                })
            else:
                # CASO 2: La DB ya existe. Hay que comparar esquema y fechas.
                meta_datos = archivos_cloud_datos[nombre_db]

                # Comparar esquemas
                bytes_modelo = descargar_archivo_de_r2(key_modelo)
                bytes_cliente = descargar_archivo_de_r2(key_datos_nube)
                comandos_sql = comparar_esquemas_db(bytes_modelo, bytes_cliente)
                
                if comandos_sql:
                    plan_acciones.append({
                        "accion": "migrar_esquema",
                        "db_relativa": ruta_relativa_cliente,
                        "comandos_sql": comandos_sql
                    })

                # Comparar timestamps para sincronización de datos
                key_local = f"{id_empresa}/{ruta_relativa_cliente}"
                if key_local in archivos_locales:
                    fecha_local = archivos_locales[key_local].last_modified
                    fecha_cloud = meta_datos['last_modified']
                    
                    if fecha_cloud > fecha_local:
                        plan_acciones.append({"accion": "actualizar_datos", "key_cloud": key_datos_nube, "destino_relativo": ruta_relativa_cliente})
                    elif fecha_local > fecha_cloud:
                        plan_acciones.append({"accion": "subir_db", "origen_relativo": ruta_relativa_cliente, "key_cloud": key_datos_nube})
                else:
                    # Si no está local, hay que bajarla
                    plan_acciones.append({"accion": "actualizar_datos", "key_cloud": key_datos_nube, "destino_relativo": ruta_relativa_cliente})

    # --- EJECUCIÓN DEL PROCESO ---
    # Primero, asegurar que los directorios base existan en el cliente
    plan_acciones.append({"accion": "ensure_dir", "ruta_relativa": "databases_generales/"})
    plan_acciones.append({"accion": "ensure_dir", "ruta_relativa": f"suc_{id_sucursal_actual}/"})

    # Procesar bases de datos generales
    procesar_conjunto_de_dbs(MODELO_GENERALES, RUTA_DATOS_GENERALES, "databases_generales")
    # Procesar bases de datos de sucursal
    procesar_conjunto_de_dbs(MODELO_SUCURSAL, RUTA_DATOS_SUCURSAL, f"suc_{id_sucursal_actual}")

    return {
        "status": "plan_generado",
        "id_empresa": id_empresa,
        "id_sucursal_activa": id_sucursal_actual,
        "acciones": plan_acciones
    }