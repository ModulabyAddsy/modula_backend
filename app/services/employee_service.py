# app/services/employee_service.py
import sqlite3
import io
from datetime import datetime
from app.services.security import hash_contrasena

def anadir_primer_administrador(db_bytes: bytes, datos_propietario: dict, username_empleado: str, contrasena_temporal: str) -> bytes | None:
    """
    Toma el contenido de una base de datos SQLite (en bytes), añade el primer 
    registro de administrador a la tabla 'empleados' y la devuelve como bytes.
    """
    try:
        # Convertimos los bytes a un stream para que sqlite3 pueda leerlo
        db_stream = io.BytesIO(db_bytes)
        
        # Guardamos el stream en un archivo temporal en memoria para la conexión
        with sqlite3.connect(':memory:') as con_mem:
            con_mem.executescript(db_stream.read().decode('utf-8'))
            
            # Insertar el primer registro del administrador/propietario
            contrasena_hash_temporal = hash_contrasena(contrasena_temporal)
            cur = con_mem.cursor()
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
            con_mem.commit()

            # Volvemos a guardar la base de datos modificada en un buffer de bytes
            buffer_modificado = io.BytesIO()
            for line in con_mem.iterdump():
                buffer_modificado.write(f'{line}\n'.encode('utf-8'))
            buffer_modificado.seek(0)

            return buffer_modificado.getvalue()

    except Exception as e:
        print(f"🔥🔥 ERROR añadiendo el primer administrador a la DB de empleados: {e}")
        return None