# app/services/cloud/setup_empresa_cloud.py
# Gestiona la creación de estructuras de carpetas en Cloudflare R2 para empresas y sucursales.

import boto3
import os
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