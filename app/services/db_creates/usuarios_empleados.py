import sqlite3
import os

# Nombre del archivo de la base de datos que se creará
DB_FILENAME = "usuarios.sqlite"

# Sentencia SQL para crear la tabla 'empleados' con la estructura acordada
CREATE_EMPLEADOS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS empleados (
    id_empleado           INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre_usuario        TEXT UNIQUE NOT NULL,
    nombre_completo       TEXT NOT NULL,
    contrasena_hash       TEXT NOT NULL,
    correo_recuperacion   TEXT,
    fecha_nacimiento      DATE,
    telefono              TEXT,
    puesto                TEXT NOT NULL,
    bloqueado             BOOLEAN NOT NULL DEFAULT 0,
    contrasena_temporal   BOOLEAN NOT NULL DEFAULT 1,
    fecha_creacion        TIMESTAMP NOT NULL,
    fecha_termino         TIMESTAMP,
    id_sucursal_labora    INTEGER NOT NULL,
    id_cuenta_addsy       INTEGER NOT NULL
);
"""

def crear_base_de_datos():
    """
    Crea el archivo de base de datos SQLite y la tabla 'empleados' si no existen.
    """
    # Elimina el archivo de la base de datos si ya existe para empezar de cero.
    if os.path.exists(DB_FILENAME):
        os.remove(DB_FILENAME)
        print(f"Archivo existente '{DB_FILENAME}' eliminado.")

    conn = None
    try:
        # Conectar a la base de datos (la crea si no existe)
        conn = sqlite3.connect(DB_FILENAME)
        cursor = conn.cursor()
        print(f"Base de datos '{DB_FILENAME}' creada exitosamente.")

        # Ejecutar la sentencia SQL para crear la tabla
        cursor.execute(CREATE_EMPLEADOS_TABLE_SQL)
        print("Tabla 'empleados' creada exitosamente.")

        # Guardar (commit) los cambios
        conn.commit()

    except sqlite3.Error as e:
        print(f"Error al crear la base de datos: {e}")
    finally:
        # Cerrar la conexión
        if conn:
            conn.close()
            print("Conexión a la base de datos cerrada.")

if __name__ == "__main__":
    crear_base_de_datos()
