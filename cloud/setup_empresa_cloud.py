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

# Cliente boto3 para R2
s3 = boto3.client(
    "s3",
    aws_access_key_id=access_key,
    aws_secret_access_key=secret_key,
    endpoint_url=endpoint_url,
    region_name=region
)

# Crear una carpeta virtual (mediante archivo vacío .keep)
def crear_directorio(path):
    try:
        s3.put_object(Bucket=bucket_name, Key=f"{path}/.keep", Body=b'')
        print(f"✅ Carpeta creada: {path}/")
    except Exception as e:
        print(f"❌ Error al crear carpeta {path}: {e}")

# Crear estructura: MOD_A001/SUC01/[bases, respaldos, logs, reportes]
def inicializar_estructura_sucursal(empresa_id, sucursal_id):
    ruta_base = f"{empresa_id}/{sucursal_id}"
    subcarpetas = ["bases", "respaldos", "logs", "reportes"]
    for sub in subcarpetas:
        crear_directorio(f"{ruta_base}/{sub}")

# --- Ejemplo de uso (puedes quitar esto si se usará como módulo) ---
if __name__ == "__main__":
    inicializar_estructura_sucursal("MOD_A001", "SUC01")