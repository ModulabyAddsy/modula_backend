# app/services/cloud/setup_empresa_cloud.py
# Inicializa la estructura de carpetas en R2 al crear una nueva empresa,
# basándose en una carpeta modelo y renombrando las subcarpetas necesarias.

import boto3
import os
from dotenv import load_dotenv

# Cargar variables de entorno desde el archivo .env
load_dotenv()

# --- Credenciales y Configuración de R2 ---
access_key = os.getenv("R2_ACCESS_KEY")
secret_key = os.getenv("R2_SECRET_ACCESS_KEY")
account_id = os.getenv("R2_ACCOUNT_ID")
bucket_name = os.getenv("R2_BUCKET_NAME")

# --- Constantes para nombres de carpetas ---
# Usar constantes hace el código más fácil de leer y mantener.
MODELO_FOLDER = "_modelo/"
PLANTILLA_SUCURSAL_FOLDER = "plantilla_sucursal/"
NUEVA_SUCURSAL_FOLDER = "suc_001/"

# --- Cliente Boto3 para S3 ---
# Este cliente se usará para todas las operaciones con R2.
s3 = boto3.client(
    "s3",
    endpoint_url=f"https://{account_id}.r2.cloudflarestorage.com",
    aws_access_key_id=access_key,
    aws_secret_access_key=secret_key,
    region_name="auto"  # 'auto' es específico para Cloudflare R2
)


def inicializar_empresa_nueva(empresa_id: str) -> bool:
    """
    Inicializa la estructura de carpetas para una nueva empresa, clonando todos
    los objetos de la carpeta modelo y renombrando la carpeta de la plantilla
    de sucursal a 'suc_001'.

    Args:
        empresa_id: El identificador único para la nueva empresa (ej. 'MOD_EMP_1001').

    Returns:
        True si la operación fue exitosa, False en caso de error.
    """
    try:
        print(f"📦 Iniciando clonación desde '{MODELO_FOLDER}' para la nueva empresa '{empresa_id}'...")

        # 1. Listar todos los objetos dentro de la carpeta modelo.
        response = s3.list_objects_v2(Bucket=bucket_name, Prefix=MODELO_FOLDER)
        
        if 'Contents' not in response:
            print(f"⚠️ Advertencia: La carpeta modelo '{MODELO_FOLDER}' está vacía o no existe.")
            return True  # No es un error, simplemente no hay nada que copiar.

        template_objects = response['Contents']
        print(f"📂 Se encontraron {len(template_objects)} objetos/archivos en el modelo.")

        # 2. Iterar sobre cada objeto del modelo para copiarlo a la nueva ubicación.
        for obj in template_objects:
            original_key = obj['Key']
            
            # Omitir la carpeta raíz del modelo para evitar errores.
            if original_key == MODELO_FOLDER:
                continue

            # 3. Determinar la ruta de destino del nuevo objeto.
            # Primero, se reemplaza la carpeta raíz del modelo por el ID de la nueva empresa.
            # Ejemplo: '_modelo/path/file' -> 'MOD_EMP_1001/path/file'
            destino_key = original_key.replace(MODELO_FOLDER, f"{empresa_id}/", 1)
            
            # Segundo, si la ruta contiene la carpeta de plantilla de sucursal, se renombra.
            # Ejemplo: 'MOD_EMP_1001/plantilla_sucursal/file' -> 'MOD_EMP_1001/suc_001/file'
            destino_key = destino_key.replace(PLANTILLA_SUCURSAL_FOLDER, NUEVA_SUCURSAL_FOLDER, 1)
            
            # Definir el origen para la operación de copia.
            copy_source = {
                'Bucket': bucket_name,
                'Key': original_key
            }
            
            # Ejecutar la copia, lo que efectivamente crea el nuevo objeto en la ruta de destino.
            s3.copy_object(
                CopySource=copy_source,
                Bucket=bucket_name,
                Key=destino_key
            )
            print(f"  -> Copiado: {original_key}  ->  {destino_key}")

        print(f"✅ Estructura en la nube creada exitosamente para '{empresa_id}'.")
        return True
        
    except Exception as e:
        print(f"❌ Error crítico en inicializar_empresa_nueva: {e}")
        return False