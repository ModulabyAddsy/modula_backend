# setup_empresa_cloud.py
# Inicializa la estructura de carpetas en R2 al crear una nueva empresa

import boto3
import os
from dotenv import load_dotenv

load_dotenv()

# Cargar credenciales desde .env
access_key = os.getenv("R2_ACCESS_KEY")
secret_key = os.getenv("R2_SECRET_ACCESS_KEY")
bucket_name = os.getenv("R2_BUCKET_NAME")
endpoint_url = os.getenv("R2_ENDPOINT")
region = os.getenv("R2_REGION")

# Cliente boto3
s3 = boto3.client(
    "s3",
    aws_access_key_id=access_key,
    aws_secret_access_key=secret_key,
    endpoint_url=endpoint_url,
    region_name=region
)

# Crear carpeta virtual mediante archivo .keep
def crear_directorio(path):
    try:
        s3.put_object(Bucket=bucket_name, Key=f"{path}/.keep", Body=b'')
        print(f"✅ Carpeta creada: {path}/")
    except Exception as e:
        raise Exception(f"❌ Error al crear carpeta {path}: {e}")

# Verificar si una carpeta ya existe
def carpeta_existe(path):
    try:
        response = s3.list_objects_v2(Bucket=bucket_name, Prefix=f"{path}/.keep")
        return 'Contents' in response
    except Exception as e:
        raise Exception(f"⚠️ Error al verificar carpeta {path}: {e}")

# Función principal para crear la estructura de una empresa nueva
def inicializar_empresa_nueva(empresa_id: str):
    """
    Inicializa la estructura de carpetas en R2:
    - Empresa/{SUC01}/{bases, respaldos, logs, reportes}
    - Empresa/Bases Generales
    """
    try:
        sucursal_id = "SUC01"
        ruta_sucursal = f"{empresa_id}/{sucursal_id}"
        subcarpetas = ["bases", "respaldos", "logs", "reportes"]

        for sub in subcarpetas:
            crear_directorio(f"{ruta_sucursal}/{sub}")

        ruta_generales = f"{empresa_id}/Bases Generales"
        if not carpeta_existe(ruta_generales):
            crear_directorio(ruta_generales)
            print("📦 'Bases Generales' creada correctamente")
        else:
            print("📁 'Bases Generales' ya existe, no se tocó")

        return True
    except Exception as e:
        print(f"❌ Error en inicializar_empresa_nueva: {e}")
        return False