# app/services/cloud/setup_empresa_cloud.py
# Inicializa la estructura de carpetas en R2 al crear una nueva empresa,
# basándose en una carpeta modelo y renombrando las subcarpetas necesarias.

import boto3
import os
from dotenv import load_dotenv

load_dotenv()

# --- Cargar credenciales desde .env ---
access_key = os.getenv("R2_ACCESS_KEY")
secret_key = os.getenv("R2_SECRET_ACCESS_KEY")
account_id = os.getenv("R2_ACCOUNT_ID")
bucket_name = os.getenv("R2_BUCKET_NAME")

# Definimos los nombres de las carpetas como constantes
TEMPLATE_FOLDER = "_modelo/"
TEMPLATE_SUCURSAL_FOLDER = "plantilla_sucursal/"
NUEVA_SUCURSAL_FOLDER = "suc_001/"

# --- Cliente boto3 ---
s3 = boto3.client(
    "s3",
    endpoint_url=f"https://{account_id}.r2.cloudflarestorage.com",
    aws_access_key_id=access_key,
    aws_secret_access_key=secret_key,
    region_name="auto"
)


def inicializar_empresa_nueva(empresa_id: str):
    """
    Inicializa la estructura de carpetas para una nueva empresa
    copiando todos los objetos de la carpeta modelo y renombrando la
    carpeta de la plantilla de sucursal a 'suc_001'.
    """
    try:
        print(f"📦 Iniciando clonación desde '{TEMPLATE_FOLDER}' para la nueva empresa '{empresa_id}'...")

        # 1. Listar todos los objetos en la carpeta modelo
        response = s3.list_objects_v2(Bucket=bucket_name, Prefix=TEMPLATE_FOLDER)
        
        if 'Contents' not in response:
            print(f"⚠️  Advertencia: La carpeta modelo '{TEMPLATE_FOLDER}' está vacía o no existe.")
            return True

        template_objects = response['Contents']
        print(f"📂 Se encontraron {len(template_objects)} objetos/archivos en el modelo.")

        # 2. Iterar sobre cada objeto del modelo y copiarlo a la nueva ubicación
        for obj in template_objects:
            template_key = obj['Key']
            
            # Crear la nueva ruta base reemplazando el prefijo del modelo por el ID de la empresa
            path_after_prefix = template_key.replace(TEMPLATE_FOLDER, f"{empresa_id}/", 1)
            
            # 👉 CORRECCIÓN: Renombrar la carpeta de la plantilla de sucursal a 'suc_001'
            new_key = path_after_prefix.replace(TEMPLATE_SUCURSAL_FOLDER, NUEVA_SUCURSAL_FOLDER, 1)
            
            # Definir el origen de la copia
            copy_source = {
                'Bucket': bucket_name,
                'Key': template_key
            }
            
            if template_key == TEMPLATE_FOLDER:
                continue

            # Ejecutar la operación de copia
            s3.copy_object(
                CopySource=copy_source,
                Bucket=bucket_name,
                Key=new_key
            )
            print(f"  -> Copiado: {template_key} -> {new_key}")

        print(f"✅ Estructura en la nube creada exitosamente para '{empresa_id}'.")
        return True
        
    except Exception as e:
        print(f"❌ Error crítico en inicializar_empresa_nueva: {e}")
        return False