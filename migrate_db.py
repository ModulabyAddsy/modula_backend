# migrate_db.py
import os
import psycopg
from dotenv import load_dotenv

# Cargar variables de entorno (asegúrate de tener tu archivo .env)
load_dotenv()

def crear_tabla_sucursales():
    """
    Crea la tabla 'sucursales' en la base de datos si no existe,
    con la estructura correcta vinculada a 'cuentas_addsy'.
    """
    conn = None
    try:
        # Obtener la URL de la base de datos y asegurar la conexión SSL
        db_url = os.getenv("DATABASE_URL")
        if not db_url:
            raise Exception("La variable de entorno DATABASE_URL no está definida.")
        if "sslmode" not in db_url:
            db_url += "?sslmode=require"
        
        print("🔌 Conectando a la base de datos de Render...")
        conn = psycopg.connect(db_url)
        cur = conn.cursor()
        print("✅ Conexión exitosa.")

        # Comando SQL para crear la tabla
        sql_command = """
        CREATE TABLE IF NOT EXISTS sucursales (
            id BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
            id_cuenta_addsy BIGINT NOT NULL REFERENCES cuentas_addsy(id) ON DELETE CASCADE,
            nombre VARCHAR(255) NOT NULL,
            fecha_creacion TIMESTAMPTZ DEFAULT NOW(),
            id_sucursal_addsy VARCHAR(50)
        );
        """

        print("\n--- Creando la tabla 'sucursales'...")
        cur.execute(sql_command)
        conn.commit()
        print("✅ ¡Tabla 'sucursales' creada o ya existente!")

    except Exception as e:
        print(f"\n🔥🔥🔥 ERROR: La operación falló. 🔥🔥🔥")
        print(e)
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()
            print("\n🔌 Conexión a la base de datos cerrada.")

if __name__ == '__main__':
    crear_tabla_sucursales()