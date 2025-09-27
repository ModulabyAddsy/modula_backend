# app/services/cloud/r2_service.py

import os
import boto3
from botocore.client import Config

# 1. Cargar las credenciales de R2 desde las variables de entorno de Render
R2_ACCOUNT_ID = os.getenv("R2_ACCOUNT_ID")
R2_ACCESS_KEY = os.getenv("R2_ACCESS_KEY")
R2_SECRET_ACCESS_KEY = os.getenv("R2_SECRET_ACCESS_KEY")
R2_BUCKET_NAME = os.getenv("R2_BUCKET_NAME")

# Endpoint URL para Cloudflare R2
ENDPOINT_URL = f'https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com'

# 2. Crear un cliente S3 reutilizable para mayor eficiencia
#    Nos aseguramos de que las credenciales existan antes de crear el cliente
s3_client = None
if R2_ACCESS_KEY and R2_SECRET_ACCESS_KEY and ENDPOINT_URL and R2_BUCKET_NAME:
    s3_client = boto3.client('s3',
        endpoint_url=ENDPOINT_URL,
        aws_access_key_id=R2_ACCESS_KEY,
        aws_secret_access_key=R2_SECRET_ACCESS_KEY,
        config=Config(signature_version='s3v4')
    )
else:
    print("⚠️ ADVERTENCIA: Faltan credenciales de R2 en las variables de entorno. El servicio de descarga de módulos no funcionará.")


def generate_download_url(file_key: str) -> str | None:
    """
    Genera una URL pre-firmada y segura para descargar un archivo desde R2.
    
    Args:
        file_key (str): La ruta del archivo en el bucket (ej: "modules/modula_pos_v1.0.1.zip").

    Returns:
        str | None: La URL temporal de descarga, o None si hay un error.
    """
    if not s3_client:
        return None
        
    try:
        url = s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': R2_BUCKET_NAME, 'Key': file_key},
            ExpiresIn=3600  # La URL será válida por 1 hora
        )
        return url
    except Exception as e:
        print(f"🔥🔥 ERROR al generar la URL pre-firmada para '{file_key}': {e}")
        return None