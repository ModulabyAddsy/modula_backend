import os
import psycopg

def migrate_and_delete_empresas():
    """
    Refactoriza la BD para eliminar la tabla 'empresas', moviendo sus columnas
    clave a 'cuentas_addsy' y actualizando las tablas dependientes.
    """
    DATABASE_URL = "postgres://modula_db_user:yBJv2Jd4053Y1y4pscoRbSc0NtS04JV5@oregon-postgres.render.com/modula_db"
    conn = None
    try:
        conn = psycopg.connect(DATABASE_URL)
        cur = conn.cursor()
        print("🔌 Conexión exitosa. Iniciando migración V3...")

        # Paso 1: Añadir columnas de 'empresas' a 'cuentas_addsy'
        print("--- [1/4] Alterando 'cuentas_addsy' para absorber columnas...")
        cur.execute("""
            ALTER TABLE cuentas_addsy
            ADD COLUMN IF NOT EXISTS id_empresa_addsy VARCHAR(255),
            ADD COLUMN IF NOT EXISTS id_suscripcion_stripe VARCHAR(255);
        """)

        # Paso 2: Migrar datos existentes (si los hay)
        # Para un entorno limpio, este paso puede no ser necesario, pero es una buena práctica.
        print("--- [2/4] Migrando datos de 'empresas' a 'cuentas_addsy'...")
        cur.execute("""
            UPDATE cuentas_addsy ca
            SET
                id_empresa_addsy = e.id_empresa_addsy,
                id_suscripcion_stripe = e.id_suscripcion_stripe
            FROM empresas e
            WHERE ca.id_empresa = e.id;
        """)

        # Paso 3: Eliminar la columna 'id_empresa' de 'cuentas_addsy'
        print("--- [3/4] Eliminando columna redundante 'id_empresa'...")
        cur.execute("ALTER TABLE cuentas_addsy DROP COLUMN IF EXISTS id_empresa;")

        # Paso 4: Eliminar la tabla 'empresas'
        print("--- [4/4] Eliminando la tabla 'empresas'...")
        cur.execute("DROP TABLE IF EXISTS empresas;")

        conn.commit()
        print("\n🎉 ¡MIGRACIÓN V3 COMPLETADA! La tabla 'empresas' ha sido eliminada y sus datos integrados.")

    except Exception as e:
        print(f"\n🔥🔥🔥 ERROR: La migración falló. Se revirtieron los cambios. 🔥🔥🔥")
        print(e)
        if conn: conn.rollback()
    finally:
        if conn: conn.close()
        print("\n🔌 Conexión cerrada.")

if __name__ == '__main__':
    migrate_and_delete_empresas()