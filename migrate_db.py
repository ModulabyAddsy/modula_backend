import os
import sqlite3
import boto3

# --- CONFIGURACIÓN DE CLOUDFLARE R2 ---
R2_ACCESS_KEY = "6175b9fea100b251193c62bccdca1746"
R2_SECRET_ACCESS_KEY = "dc95627399bc763e8f44198f0546d7f2c81f8353ac18253b501fe8d760431ae0"
R2_BUCKET_NAME = "modula-cloud"
R2_ACCOUNT_ID = "ef25b0c28e4a33386ce9d9202bd512cf"
R2_ENDPOINT_URL = f"https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com"
TEMPLATE_FOLDER = "_modelo"

# --- DEFINICIÓN DE ESQUEMAS DE BASE DE DATOS ---

USUARIOS_SCHEMA = """
CREATE TABLE usuarios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre_completo TEXT NOT NULL,
    fecha_nacimiento TEXT NOT NULL,
    rfc TEXT,
    telefono TEXT NOT NULL,
    correo TEXT NOT NULL UNIQUE,
    id_usuario TEXT NOT NULL UNIQUE,
    contrasena TEXT NOT NULL,
    permiso_sucursal TEXT,
    estado TEXT NOT NULL DEFAULT 'activo'
);
"""

CLIENTES_SCHEMA = """
CREATE TABLE clientes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre_completo TEXT NOT NULL,
    fecha_nacimiento TEXT NOT NULL,
    telefono TEXT NOT NULL,
    correo TEXT,
    numero_cliente TEXT UNIQUE
);
"""

PRODUCTOS_SERVICIOS_SCHEMA = """
CREATE TABLE productos_servicios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sku TEXT UNIQUE,
    descripcion TEXT,
    precio REAL,
    costo REAL,
    es_servicio INTEGER DEFAULT 0
);
"""

TICKETS_SCHEMA = """
CREATE TABLE tickets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    numero_transaccion TEXT UNIQUE NOT NULL,
    descripcion_venta TEXT,
    total_bruto REAL,
    costo REAL,
    ganancia_bruta REAL,
    nombre_cliente TEXT,
    numero_cliente TEXT,
    fecha_venta TEXT,
    id_usuario_venta TEXT
);
"""

EGRESOS_SCHEMA = """
CREATE TABLE egresos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    razon_egreso TEXT,
    monto_egreso REAL,
    fecha_egreso TEXT,
    id_usuario TEXT
);
"""

INGRESOS_SCHEMA = """
CREATE TABLE ingresos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    razon_ingreso TEXT,
    monto_ingreso REAL,
    fecha_ingreso TEXT,
    id_usuario TEXT
);
"""

# --- FUNCIÓN PRINCIPAL DEL SCRIPT ---

def create_and_upload_db(s3_client, local_path, r2_key, create_table_sql):
    """Crea una BD SQLite local, define su tabla y la sube a R2."""
    conn = None
    try:
        print(f"🔩 Creando base de datos local: {local_path}...")
        conn = sqlite3.connect(local_path)
        cursor = conn.cursor()
        cursor.execute(create_table_sql)
        conn.commit()
        conn.close()

        print(f"☁️  Subiendo {local_path} a R2 en la ruta: {r2_key}...")
        s3_client.upload_file(local_path, R2_BUCKET_NAME, r2_key)
        print(f"✅ Carga de {local_path} completada.")

    except Exception as e:
        print(f"🔥🔥 ERROR procesando {local_path}: {e}")
    finally:
        if conn:
            conn.close()
        if os.path.exists(local_path):
            os.remove(local_path)
            print(f"🧹 Archivo local {local_path} eliminado.")

def build_model_structure():
    """Coordina la creación y subida de toda la estructura modelo."""
    
    print("🚀 Iniciando creación de la estructura modelo en Cloudflare R2...")
    
    s3_client = boto3.client(
        "s3",
        endpoint_url=R2_ENDPOINT_URL,
        aws_access_key_id=R2_ACCESS_KEY,
        aws_secret_access_key=R2_SECRET_ACCESS_KEY,
        region_name="auto"
    )

    databases_to_create = [
        # Bases de Datos Generales
        {
            "local_path": "usuarios.sqlite",
            "r2_key": f"{TEMPLATE_FOLDER}/databases_generales/usuarios.sqlite",
            "schema": USUARIOS_SCHEMA
        },
        {
            "local_path": "clientes.sqlite",
            "r2_key": f"{TEMPLATE_FOLDER}/databases_generales/clientes.sqlite",
            "schema": CLIENTES_SCHEMA
        },
        {
            "local_path": "productos_servicios.sqlite",
            "r2_key": f"{TEMPLATE_FOLDER}/databases_generales/productos_servicios.sqlite",
            "schema": PRODUCTOS_SERVICIOS_SCHEMA
        },
        
        # 👉 **CORRECCIÓN**: Usando "plantilla_sucursal" como el nombre de la carpeta modelo.
        # Bases de Datos de la Plantilla de Sucursal
        {
            "local_path": "tickets.sqlite",
            "r2_key": f"{TEMPLATE_FOLDER}/plantilla_sucursal/tickets.sqlite",
            "schema": TICKETS_SCHEMA
        },
        {
            "local_path": "egresos.sqlite",
            "r2_key": f"{TEMPLATE_FOLDER}/plantilla_sucursal/egresos.sqlite",
            "schema": EGRESOS_SCHEMA
        },
        {
            "local_path": "ingresos.sqlite",
            "r2_key": f"{TEMPLATE_FOLDER}/plantilla_sucursal/ingresos.sqlite",
            "schema": INGRESOS_SCHEMA
        }
    ]

    for db_info in databases_to_create:
        create_and_upload_db(
            s3_client=s3_client,
            local_path=db_info["local_path"],
            r2_key=db_info["r2_key"],
            create_table_sql=db_info["schema"]
        )
        print("-" * 30)

    print("🎉 Proceso de creación de modelo finalizado.")

if __name__ == "__main__":
    build_model_structure()