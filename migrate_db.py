import sys
import psycopg2
from psycopg2 import errors

def migrate_database():
    """
    Ejecuta una migración completa de la base de datos para adoptar la nueva arquitectura de Addsy.
    - Elimina tablas obsoletas.
    - Renombra y reestructura tablas existentes.
    - Crea nuevas tablas y tipos de datos.
    """
    # --- URL DE CONEXIÓN EXTERNA DIRECTA DE RENDER ---
    DATABASE_URL = "postgres://modula_db_user:yBJv2Jd4053Y1y4pscoRbSc0NtS04JV5@oregon-postgres.render.com/modula_db"

    conn = None
    try:
        print("🔌 Conectando a la base de datos de Render...")
        connection_url_with_ssl = DATABASE_URL
        if "sslmode" not in connection_url_with_ssl:
            connection_url_with_ssl += "?sslmode=require"
            
        conn = psycopg2.connect(connection_url_with_ssl)
        cur = conn.cursor()
        print("✅ Conexión exitosa.")

        print("\n🚀 INICIANDO MIGRACIÓN DE LA BASE DE DATOS...\n")

        # PASO 1: Crear los tipos ENUM
        print("--- [Paso 1/7] Creando tipos ENUM personalizados...")
        cur.execute("""
            DO $$ BEGIN CREATE TYPE estatus_cuenta AS ENUM ('verificada', 'no_verificada', 'bloqueada'); EXCEPTION WHEN duplicate_object THEN null; END $$;
            DO $$ BEGIN CREATE TYPE software_nombre AS ENUM ('modula', 'addsy_citas'); EXCEPTION WHEN duplicate_object THEN null; END $$;
            DO $$ BEGIN CREATE TYPE estado_suscripcion AS ENUM ('prueba_gratis', 'activa', 'suspendida_pago'); EXCEPTION WHEN duplicate_object THEN null; END $$;
        """)
        print("✅ Tipos ENUM creados o verificados.")

        # PASO 2: Habilitar extensión 'uuid-ossp'
        print("\n--- [Paso 2/7] Habilitando extensión 'uuid-ossp'...")
        cur.execute("CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\";")
        print("✅ Extensión 'uuid-ossp' habilitada.")

        # PASO 3: Eliminar tablas obsoletas
        print("\n--- [Paso 3/7] Eliminando tablas obsoletas...")
        cur.execute("""
            DROP TABLE IF EXISTS usuarios_v1;
            DROP TABLE IF EXISTS productos_maestro;
        """)
        print("✅ Tablas 'usuarios_v1' y 'productos_maestro' eliminadas.")

        # PASO 4: Migrar 'usuarios_admin' a 'cuentas_addsy'
        print("\n--- [Paso 4/7] Migrando tabla a 'cuentas_addsy'...")
        cur.execute("""
            ALTER TABLE IF EXISTS usuarios_admin RENAME TO cuentas_addsy;

            ALTER TABLE cuentas_addsy
            ADD COLUMN IF NOT EXISTS nombre_empresa VARCHAR(255) NOT NULL DEFAULT 'Empresa sin nombre',
            ADD COLUMN IF NOT EXISTS rfc VARCHAR(13),
            ADD COLUMN IF NOT EXISTS estatus_cuenta estatus_cuenta DEFAULT 'no_verificada',
            ADD COLUMN IF NOT EXISTS fecha_creacion TIMESTAMPTZ DEFAULT NOW(),
            ADD COLUMN IF NOT EXISTS bloqueado BOOLEAN DEFAULT false;
            
            ALTER TABLE cuentas_addsy 
            ALTER COLUMN id TYPE BIGINT,
            ALTER COLUMN id_empresa TYPE BIGINT;

            ALTER TABLE cuentas_addsy
            DROP COLUMN IF EXISTS estatus,
            DROP COLUMN IF EXISTS token,
            DROP COLUMN IF EXISTS token_expira;
        """)
        # CORRECCIÓN AQUÍ: Se añade la restricción en un bloque separado para manejar el error si ya existe
        try:
            cur.execute("ALTER TABLE cuentas_addsy ADD CONSTRAINT uq_correo UNIQUE (correo);")
        except errors.DuplicateTable: # psycopg2.errors.DuplicateTable is the error for existing constraint
            pass # Ignorar el error si la restricción ya existe
        print("✅ Tabla 'cuentas_addsy' migrada y estructurada.")
        
        # PASO 5: Migrar 'terminales_v1' a 'modula_terminales'
        print("\n--- [Paso 5/7] Migrando tabla a 'modula_terminales'...")
        cur.execute("""
            ALTER TABLE IF EXISTS terminales_v1 RENAME TO modula_terminales;
            
            ALTER TABLE modula_terminales
            ADD COLUMN IF NOT EXISTS id_sucursal BIGINT,
            ADD COLUMN IF NOT EXISTS nombre_terminal VARCHAR(100),
            ADD COLUMN IF NOT EXISTS ultima_sincronizacion TIMESTAMPTZ,
            ADD COLUMN IF NOT EXISTS activa BOOLEAN DEFAULT true;

            ALTER TABLE modula_terminales RENAME COLUMN ip_terminal TO ultima_ip_registrada;
            ALTER TABLE modula_terminales 
            ALTER COLUMN id_terminal SET DATA TYPE UUID USING uuid_generate_v4(),
            ALTER COLUMN id_empresa SET DATA TYPE BIGINT USING id_empresa::BIGINT,
            ALTER COLUMN ultima_ip_registrada SET DATA TYPE INET USING NULLIF(ultima_ip_registrada, '')::INET;
            
            ALTER TABLE modula_terminales DROP COLUMN IF EXISTS numero_sucursal;
        """)
        print("✅ Tabla 'modula_terminales' migrada y estructurada.")
        
        # PASO 6: Actualizar 'productos_plantilla_global'
        print("\n--- [Paso 6/7] Actualizando 'productos_plantilla_global'...")
        cur.execute("""
            ALTER TABLE productos_plantilla_global
            ADD COLUMN IF NOT EXISTS precio_sugerido NUMERIC(10, 2) DEFAULT 0.00,
            ADD COLUMN IF NOT EXISTS costo_promedio NUMERIC(10, 2) DEFAULT 0.00,
            ADD COLUMN IF NOT EXISTS requiere_inventario BOOLEAN DEFAULT true,
            ADD COLUMN IF NOT EXISTS locacion_almacen VARCHAR(50);
        """)
        # CORRECCIÓN AQUÍ: Se añade la restricción en un bloque separado para manejar el error si ya existe
        try:
            cur.execute("ALTER TABLE productos_plantilla_global ADD CONSTRAINT uq_sku UNIQUE (sku);")
        except errors.DuplicateTable:
            pass # Ignorar el error si la restricción ya existe
        print("✅ Tabla 'productos_plantilla_global' actualizada.")

        # PASO 7: Crear la nueva tabla 'suscripciones_software'
        print("\n--- [Paso 7/7] Creando nueva tabla 'suscripciones_software'...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS suscripciones_software (
                id BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
                id_cuenta_addsy BIGINT NOT NULL REFERENCES cuentas_addsy(id) ON DELETE CASCADE,
                software_nombre software_nombre NOT NULL,
                estado_suscripcion estado_suscripcion NOT NULL,
                fecha_vencimiento TIMESTAMPTZ,
                terminales_activas INTEGER DEFAULT 1,
                usuarios_activos INTEGER DEFAULT 1,
                espacio_total_gb NUMERIC(10, 2) DEFAULT 1.00,
                espacio_usado_bytes BIGINT DEFAULT 0,
                UNIQUE (id_cuenta_addsy, software_nombre)
            );
        """)
        print("✅ Tabla 'suscripciones_software' creada.")

        conn.commit()
        print("\n\n🎉 ¡MIGRACIÓN COMPLETADA EXITOSAMENTE! 🎉")
        print("La base de datos está ahora en la nueva estructura de Addsy.")

    except (Exception, psycopg2.DatabaseError) as error:
        print(f"\n🔥🔥🔥 ERROR: La migración falló. Se revirtieron los cambios. 🔥🔥🔥")
        print(error)
        if conn is not None:
            conn.rollback()
    finally:
        if conn is not None:
            conn.close()
            print("\n🔌 Conexión a la base de datos cerrada.")

if __name__ == '__main__':
    migrate_database()