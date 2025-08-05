# app/services/employee_service.py
import sqlite3
import io
import os
from datetime import datetime
from app.services.security import hash_contrasena

def anadir_primer_administrador(db_bytes: bytes, datos_propietario: dict, username_empleado: str, contrasena_temporal: str) -> bytes | None:
    """
    Toma el contenido de una DB SQLite (en bytes), guarda los cambios en un
    archivo temporal y devuelve los bytes modificados.
    """
    # Usaremos un nombre de archivo temporal único para evitar conflictos
    temp_db_path = f"temp_{username_empleado}.sqlite"
    
    try:
        # 1. Escribir los bytes descargados a un archivo temporal
        with open(temp_db_path, "wb") as f:
            f.write(db_bytes)

        # 2. Conectar al archivo temporal y modificarlo
        with sqlite3.connect(temp_db_path) as con:
            contrasena_hash_temporal = hash_contrasena(contrasena_temporal)
            cur = con.cursor()
            cur.execute("""
                INSERT INTO empleados (
                    nombre_usuario, nombre_completo, contrasena_hash, correo_recuperacion,
                    fecha_nacimiento, telefono, puesto, id_sucursal_labora,
                    fecha_creacion, id_cuenta_addsy
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                username_empleado,
                datos_propietario['nombre_completo'],
                contrasena_hash_temporal,
                datos_propietario['correo'],
                datos_propietario['fecha_nacimiento'],
                datos_propietario['telefono'],
                'Administrador',
                datos_propietario['id_primera_sucursal'],
                datetime.utcnow(),
                datos_propietario['id']
            ))
            con.commit()

        # 3. Leer los bytes del archivo modificado para devolverlos
        with open(temp_db_path, "rb") as f:
            db_bytes_modificado = f.read()
        
        return db_bytes_modificado

    except Exception as e:
        print(f"🔥🔥 ERROR añadiendo el primer administrador a la DB de empleados: {e}")
        return None
    finally:
        # 4. Asegurarse de borrar el archivo temporal
        if os.path.exists(temp_db_path):
            os.remove(temp_db_path)
