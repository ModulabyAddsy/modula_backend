# app/controller/sync_logic.py
import sqlite3
import tempfile
from app.services.cloud.setup_empresa_cloud import (
    listar_archivos_con_metadata,
    descargar_archivo_de_r2,
    subir_archivo_a_r2,
    s3, BUCKET_NAME # Importamos el cliente s3 y el bucket
)

MODELO_GENERALES_PREFIX = "_modelo/databases_generales/"
MODELO_SUCURSAL_PREFIX = "_modelo/plantilla_sucursal/"

async def stage_1_align_cloud_files(id_empresa: str, ruta_cloud_sucursal: str):
    """Asegura que todos los archivos del modelo existan en las carpetas de la empresa."""
    
    # Lógica para archivos generales
    archivos_modelo_gen = listar_archivos_con_metadata(MODELO_GENERALES_PREFIX)
    archivos_empresa_gen = listar_archivos_con_metadata(f"{id_empresa}/databases_generales/")
    nombres_empresa_gen = {f['key'].split('/')[-1] for f in archivos_empresa_gen}

    for archivo_modelo in archivos_modelo_gen:
        nombre_modelo = archivo_modelo['key'].split('/')[-1]
        if nombre_modelo not in nombres_empresa_gen:
            destino_key = f"{id_empresa}/databases_generales/{nombre_modelo}"
            s3.copy_object(CopySource={'Bucket': BUCKET_NAME, 'Key': archivo_modelo['key']}, Bucket=BUCKET_NAME, Key=destino_key)
            print(f"✨ Archivo general '{nombre_modelo}' copiado al cliente.")

    # Lógica para archivos de sucursal
    archivos_modelo_suc = listar_archivos_con_metadata(MODELO_SUCURSAL_PREFIX)
    archivos_empresa_suc = listar_archivos_con_metadata(ruta_cloud_sucursal)
    nombres_empresa_suc = {f['key'].split('/')[-1] for f in archivos_empresa_suc}

    for archivo_modelo in archivos_modelo_suc:
        nombre_modelo = archivo_modelo['key'].split('/')[-1]
        if nombre_modelo not in nombres_empresa_suc:
            destino_key = f"{ruta_cloud_sucursal}{nombre_modelo}"
            s3.copy_object(CopySource={'Bucket': BUCKET_NAME, 'Key': archivo_modelo['key']}, Bucket=BUCKET_NAME, Key=destino_key)
            print(f"✨ Archivo de sucursal '{nombre_modelo}' copiado al cliente.")


async def stage_2_migrate_cloud_schemas(id_empresa: str, ruta_cloud_sucursal: str):
    """Compara y migra los esquemas de las DB en la nube."""
    # Procesar bases de datos generales
    await _compare_and_migrate_set(MODELO_GENERALES_PREFIX, f"{id_empresa}/databases_generales/")
    # Procesar bases de datos de sucursal
    await _compare_and_migrate_set(MODELO_SUCURSAL_PREFIX, ruta_cloud_sucursal)


async def _compare_and_migrate_set(prefix_modelo, prefix_empresa):
    """Función helper para migrar un conjunto de bases de datos."""
    archivos_modelo = {f['key'].split('/')[-1]: f['key'] for f in listar_archivos_con_metadata(prefix_modelo)}
    archivos_empresa = {f['key'].split('/')[-1]: f['key'] for f in listar_archivos_con_metadata(prefix_empresa)}

    for nombre_db, key_modelo in archivos_modelo.items():
        if nombre_db in archivos_empresa:
            key_empresa = archivos_empresa[nombre_db]
            bytes_modelo = descargar_archivo_de_r2(key_modelo)
            bytes_empresa = descargar_archivo_de_r2(key_empresa)

            if not bytes_modelo or not bytes_empresa: continue

            comandos_sql = _comparar_esquemas_db(bytes_modelo, bytes_empresa)

            if comandos_sql:
                print(f"🔄 Migrando esquema para {key_empresa}...")
                with tempfile.NamedTemporaryFile(suffix=".sqlite") as tmp_db:
                    tmp_db.write(bytes_empresa)
                    tmp_db.seek(0)
                    conn = sqlite3.connect(tmp_db.name)
                    cursor = conn.cursor()
                    for comando in comandos_sql:
                        try:
                            cursor.execute(comando)
                        except sqlite3.OperationalError as e:
                            print(f"⚠️  Advertencia al migrar {nombre_db}: {e}. Probablemente la columna ya existe.")
                    conn.commit()
                    conn.close()
                    tmp_db.seek(0)
                    subir_archivo_a_r2(key_empresa, tmp_db.read())
                print(f"✅ Esquema de {key_empresa} actualizado.")


def _get_table_schema(cursor, table_name):
    """Obtiene el esquema y las columnas de una tabla."""
    cursor.execute(f"SELECT sql FROM sqlite_master WHERE type='table' AND name='{table_name}'")
    create_sql_tuple = cursor.fetchone()
    if not create_sql_tuple: return None, {}
    
    create_sql = create_sql_tuple[0]
    cursor.execute(f"PRAGMA table_info('{table_name}')")
    columns_info = cursor.fetchall()
    return create_sql, {info[1]: info for info in columns_info}


def _comparar_esquemas_db(bytes_db_modelo: bytes, bytes_db_cliente: bytes) -> list[str]:
    """Compara dos DBs y devuelve los comandos SQL para actualizar el cliente."""
    comandos_sql = []
    with tempfile.NamedTemporaryFile() as tmp_modelo, tempfile.NamedTemporaryFile() as tmp_cliente:
        tmp_modelo.write(bytes_db_modelo)
        tmp_cliente.write(bytes_db_cliente)
        tmp_modelo.seek(0); tmp_cliente.seek(0)

        conn_modelo = sqlite3.connect(tmp_modelo.name)
        conn_cliente = sqlite3.connect(tmp_cliente.name)
        cur_modelo = conn_modelo.cursor()
        cur_cliente = conn_cliente.cursor()

        cur_modelo.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tablas_modelo = {row[0] for row in cur_modelo.fetchall() if not row[0].startswith('sqlite_')}
        cur_cliente.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tablas_cliente = {row[0] for row in cur_cliente.fetchall() if not row[0].startswith('sqlite_')}

        for tabla in tablas_modelo - tablas_cliente:
            create_sql, _ = _get_table_schema(cur_modelo, tabla)
            if create_sql: comandos_sql.append(create_sql)

        for tabla in tablas_modelo.intersection(tablas_cliente):
            _, cols_modelo_info = _get_table_schema(cur_modelo, tabla)
            _, cols_cliente_info = _get_table_schema(cur_cliente, tabla)
            
            for col_name in set(cols_modelo_info.keys()) - set(cols_cliente_info.keys()):
                col_info = cols_modelo_info[col_name]
                comando = f"ALTER TABLE {tabla} ADD COLUMN {col_info[1]} {col_info[2]}"
                if col_info[4] is not None:
                    comando += f" DEFAULT {col_info[4]}"
                if col_info[3]:
                    comando += " NOT NULL DEFAULT 0" if "INT" in col_info[2].upper() else " NOT NULL DEFAULT ''"
                comandos_sql.append(comando + ";")

        conn_modelo.close(); conn_cliente.close()
    return comandos_sql