# app/services/cloud/setup_empresa_cloud.py
# Gestiona la creación de estructuras de carpetas en Cloudflare R2 para empresas y sucursales.
import os
import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv
# Cargar variables de entorno
load_dotenv()

# --- Configuración de R2 ---
s3 = boto3.client(
    "s3",
    endpoint_url=f"https://{os.getenv('R2_ACCOUNT_ID')}.r2.cloudflarestorage.com",
    aws_access_key_id=os.getenv("R2_ACCESS_KEY"),
    aws_secret_access_key=os.getenv("R2_SECRET_ACCESS_KEY"),
    region_name="auto"
)

BUCKET_NAME = os.getenv("R2_BUCKET_NAME")
# --- Constantes Simplificadas ---
MODELO_FOLDER = "_modelo/"
MODELO_SUCURSAL_FOLDER = "_modelo/plantilla_sucursal/"


def crear_estructura_base_empresa(empresa_id: str) -> bool:
    """
    Crea la estructura de carpetas base para una nueva empresa, copiando
    los elementos generales desde la carpeta '_modelo/'.
    OMITE la carpeta de plantilla de sucursal y sus contenidos.
    """
    try:
        print(f"🏢 Creando estructura base para la empresa '{empresa_id}'...")
        
        # 1. Listar todos los objetos dentro de la carpeta modelo raíz.
        response = s3.list_objects_v2(Bucket=BUCKET_NAME, Prefix=MODELO_FOLDER)
        if 'Contents' not in response:
            print(f"⚠️ La carpeta modelo '{MODELO_FOLDER}' está vacía o no existe.")
            return True

        # 2. Iterar sobre cada objeto para copiarlo.
        for obj in response['Contents']:
            original_key = obj['Key']
            
            # 3. Omitir la carpeta raíz del modelo y la plantilla de sucursal.
            if original_key == MODELO_FOLDER or original_key.startswith(MODELO_SUCURSAL_FOLDER):
                continue
            
            # 4. Construir la nueva ruta de destino.
            # Ej: '_modelo/databases_generales/' -> 'MOD_EMP_1001/databases_generales/'
            destino_key = original_key.replace(MODELO_FOLDER, f"{empresa_id}/", 1)
            
            # 5. Ejecutar la copia.
            copy_source = {'Bucket': BUCKET_NAME, 'Key': original_key}
            s3.copy_object(CopySource=copy_source, Bucket=BUCKET_NAME, Key=destino_key)
            print(f"   -> Copiado general: {original_key} -> {destino_key}")
            
        print(f"✅ Estructura base para '{empresa_id}' creada exitosamente.")
        return True
    except Exception as e:
        print(f"❌ Error creando estructura base para la empresa: {e}")
        return False


def crear_estructura_sucursal(ruta_cloud_sucursal: str) -> bool:
    """
    Crea la estructura de carpetas para una nueva sucursal, basándose en una plantilla.
    Copia todo desde '_modelo/plantilla_sucursal/' a la ruta especificada.
    (Esta función no necesita cambios, ya funcionaba bien).
    """
    try:
        print(f"🌿 Creando estructura para la sucursal en '{ruta_cloud_sucursal}'...")
        
        response = s3.list_objects_v2(Bucket=BUCKET_NAME, Prefix=MODELO_SUCURSAL_FOLDER)

        if 'Contents' not in response:
            print(f"⚠️ La plantilla de sucursal '{MODELO_SUCURSAL_FOLDER}' está vacía o no existe.")
            s3.put_object(Bucket=BUCKET_NAME, Key=ruta_cloud_sucursal)
            return True

        template_objects = response['Contents']
        print(f"📄 Se encontraron {len(template_objects)} archivos en la plantilla de sucursal.")

        for obj in template_objects:
            original_key = obj['Key']
            if original_key == MODELO_SUCURSAL_FOLDER:
                continue

            destino_key = original_key.replace(MODELO_SUCURSAL_FOLDER, ruta_cloud_sucursal, 1)
            copy_source = {'Bucket': BUCKET_NAME, 'Key': original_key}
            
            s3.copy_object(CopySource=copy_source, Bucket=BUCKET_NAME, Key=destino_key)
            print(f"   -> Copiado de sucursal: {original_key} -> {destino_key}")

        print(f"✅ Estructura para la sucursal en '{ruta_cloud_sucursal}' creada exitosamente.")
        return True
    except Exception as e:
        print(f"❌ Error creando estructura de sucursal: {e}")
        return False

def subir_archivo_db(ruta_cloud_destino: str, contenido_archivo: bytes) -> bool:
    """Sube un archivo de base de datos (en bytes) a una ruta específica en R2."""
    try:
        s3.put_object(Bucket=BUCKET_NAME, Key=ruta_cloud_destino, Body=contenido_archivo)
        print(f"✅ Archivo subido exitosamente a '{ruta_cloud_destino}'.")
        return True
    except Exception as e:
        print(f"❌ Error subiendo archivo a R2 en '{ruta_cloud_destino}': {e}")
        return False
    
def descargar_archivo_db(ruta_cloud_origen: str) -> bytes | None:
    """Descarga un archivo desde una ruta de R2 y lo devuelve como bytes."""
    try:
        response = s3.get_object(Bucket=BUCKET_NAME, Key=ruta_cloud_origen)
        print(f"✅ Archivo descargado exitosamente de '{ruta_cloud_origen}'.")
        return response['Body'].read()
    except Exception as e:
        # Es normal que aquí pueda dar un error si el archivo no existe aún
        print(f"⚠️  No se pudo descargar el archivo de R2 en '{ruta_cloud_origen}': {e}")
        return None
    
def listar_archivos_con_metadata(prefix: str) -> list:
    """
    Lista todos los archivos bajo un prefijo en R2 y devuelve su metadata clave.
    IGNORA los directorios y AÑADE el ETag (hash).
    """
    lista_archivos = []
    try:
        paginator = s3.get_paginator('list_objects_v2')
        pages = paginator.paginate(Bucket=BUCKET_NAME, Prefix=prefix)
        for page in pages:
            if 'Contents' in page:
                for obj in page['Contents']:
                    # Guardia de seguridad: Omitimos las carpetas, solo nos interesan los archivos.
                    if not obj['Key'].endswith('/'):
                        lista_archivos.append({
                            'key': obj['Key'],
                            'LastModified': obj['LastModified'],  # <-- CORREGIDO: Usamos la 'L' mayúscula original de boto3
                            'httpEtag': obj['ETag'].strip('"') # <-- AÑADIDO: Incluimos el hash y lo nombramos igual que en la otra función
                        })
    except Exception as e:
        print(f"❌ Error listando archivos en R2 para el prefijo '{prefix}': {e}")
    
    return lista_archivos

def descargar_archivo_de_r2(ruta_cloud_origen: str) -> bytes | None:
    """Descarga el contenido de un archivo de R2 como bytes."""
    try:
        response = s3.get_object(Bucket=BUCKET_NAME, Key=ruta_cloud_origen)
        return response['Body'].read()
    except Exception as e:
        print(f"❌ Error al descargar {ruta_cloud_origen} de R2: {e}")
        return None

def subir_archivo_a_r2(ruta_cloud_destino: str, contenido_archivo: bytes) -> bool:
    """Sube un contenido en bytes a una ruta específica en R2."""
    try:
        s3.put_object(Bucket=BUCKET_NAME, Key=ruta_cloud_destino, Body=contenido_archivo)
        return True
    except Exception as e:
        print(f"❌ Error al subir a R2 en '{ruta_cloud_destino}': {e}")
        return False

def obtener_metadata_de_r2(key_path: str) -> dict | None:
    """
    Obtiene la metadata de un objeto en R2 sin descargar el archivo completo.
    Devuelve un diccionario con la metadata o None si el archivo no existe.
    """
    try:
        # CAMBIO 1: Usamos tu cliente 's3' en lugar de 'r2_client'
        response = s3.head_object(
            # CAMBIO 2: Usamos tu variable 'BUCKET_NAME'
            Bucket=BUCKET_NAME,
            Key=key_path
        )
        # El ETag (hash MD5 en R2) viene con comillas, hay que quitarlas.
        http_etag = response.get('ETag', '').strip('"')
        
        return {
            "httpEtag": http_etag,
            "lastModified": response.get('LastModified'),
            "contentLength": response.get('ContentLength')
        }
    except ClientError as e:
        if e.response['Error']['Code'] == '404':
            return None
        print(f"Error obteniendo metadata de '{key_path}': {e}")
        raise