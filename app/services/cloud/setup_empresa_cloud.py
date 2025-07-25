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
MODELO_EMPRESA_FOLDER = "_modelo/plantilla_empresa/"
MODELO_SUCURSAL_FOLDER = "_modelo/plantilla_sucursal/"


def crear_estructura_base_empresa(empresa_id: str) -> bool:
    """
    Crea la estructura de carpetas base para una nueva empresa.
    Copia todo desde '_modelo/plantilla_empresa/' a la nueva carpeta de la empresa.
    
    Args:
        empresa_id: El ID de la empresa (ej. 'MOD_EMP_1001').
    
    Returns:
        True si fue exitoso, False si falló.
    """
    try:
        print(f"🏢 Creando estructura base para la empresa '{empresa_id}'...")
        # Lógica para copiar la plantilla base de la empresa (si la tienes, ej. para bases generales)
        # Este es un ejemplo, puedes adaptarlo a tu estructura en '_modelo/plantilla_empresa/'
        # Por ahora, solo crearemos el marcador de directorio de la empresa.
        s3.put_object(Bucket=BUCKET_NAME, Key=f"{empresa_id}/")
        print(f"✅ Estructura base para '{empresa_id}' creada.")
        return True
    except Exception as e:
        print(f"❌ Error creando estructura base para la empresa: {e}")
        return False


def crear_estructura_sucursal(ruta_cloud_sucursal: str) -> bool:
    """
    Crea la estructura de carpetas para una nueva sucursal, basándose en una plantilla.
    Copia todo desde '_modelo/plantilla_sucursal/' a la ruta especificada.

    Args:
        ruta_cloud_sucursal: La ruta completa donde se creará la carpeta de la sucursal 
                             (ej. 'MOD_EMP_1001/suc_1/').
    
    Returns:
        True si fue exitoso, False si falló.
    """
    try:
        print(f"🌿 Creando estructura para la sucursal en '{ruta_cloud_sucursal}'...")
        
        response = s3.list_objects_v2(Bucket=BUCKET_NAME, Prefix=MODELO_SUCURSAL_FOLDER)

        if 'Contents' not in response:
            print(f"⚠️ La plantilla de sucursal '{MODELO_SUCURSAL_FOLDER}' está vacía o no existe.")
            # Creamos al menos la carpeta "raíz" de la sucursal
            s3.put_object(Bucket=BUCKET_NAME, Key=ruta_cloud_sucursal)
            return True

        template_objects = response['Contents']
        print(f"📄 Se encontraron {len(template_objects)} archivos en la plantilla de sucursal.")

        for obj in template_objects:
            original_key = obj['Key']
            if original_key == MODELO_SUCURSAL_FOLDER:
                continue

            # Construye la nueva ruta reemplazando el prefijo del modelo por el de destino
            destino_key = original_key.replace(MODELO_SUCURSAL_FOLDER, ruta_cloud_sucursal, 1)
            
            copy_source = {'Bucket': BUCKET_NAME, 'Key': original_key}
            
            s3.copy_object(CopySource=copy_source, Bucket=BUCKET_NAME, Key=destino_key)
            print(f"   -> Copiado: {original_key} -> {destino_key}")

        print(f"✅ Estructura para la sucursal en '{ruta_cloud_sucursal}' creada exitosamente.")
        return True
    except Exception as e:
        print(f"❌ Error creando estructura de sucursal: {e}")
        return False