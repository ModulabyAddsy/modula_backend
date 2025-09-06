# app/services/employee_service.py
import sqlite3
import io
import os
import uuid
from datetime import datetime
from app.services.security import hash_contrasena
import tempfile

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

def obtener_info_empleado(db_bytes: bytes, nombre_usuario: str) -> dict | None:
    """
    Toma el contenido de una DB SQLite (en bytes), busca un empleado por su
    nombre de usuario y devuelve sus datos como un diccionario.
    """
    temp_db_path = f"temp_query_{nombre_usuario}.sqlite"
    
    try:
        # 1. Escribe los bytes descargados a un archivo temporal para poder consultarlo
        with open(temp_db_path, "wb") as f:
            f.write(db_bytes)

        # 2. Conecta al archivo temporal y busca al empleado
        with sqlite3.connect(temp_db_path) as con:
            con.row_factory = sqlite3.Row # Esto hace que los resultados se puedan tratar como diccionarios
            cur = con.cursor()
            
            cur.execute("SELECT * FROM empleados WHERE nombre_usuario = ?", (nombre_usuario,))
            empleado_row = cur.fetchone()
            
            # 3. Si se encontró, lo convierte a un diccionario estándar y lo devuelve
            if empleado_row:
                return dict(empleado_row)
        
        # Si no se encontró, devuelve None
        return None

    except Exception as e:
        print(f"🔥🔥 ERROR obteniendo info del empleado '{nombre_usuario}': {e}")
        return None
    finally:
        # 4. Asegurarse de borrar el archivo temporal
        if os.path.exists(temp_db_path):
            os.remove(temp_db_path)
            
def anadir_primer_administrador_general(
    db_bytes: bytes,
    datos_propietario: dict,
    username_empleado: str,
    contrasena_temporal: str
) -> bytes | None:
    """
    Agrega el primer usuario (administrador) a la base de datos de 'usuarios.sqlite'.
    Toma los bytes de la DB, inserta el nuevo registro y devuelve los bytes actualizados.
    
    Args:
        db_bytes (bytes): Contenido del archivo de base de datos 'usuarios.sqlite'.
        datos_propietario (dict): Datos del propietario de la cuenta desde la DB de PostgreSQL.
        username_empleado (str): El nombre de usuario que se generó (e.g., "11001").
        contrasena_temporal (str): La contraseña temporal generada.
        
    Returns:
        bytes | None: El contenido de la base de datos actualizado, o None si hubo un error.
    """
    
    temp_db_path = None
    try:
        # 1. Escribir los bytes descargados a un archivo temporal para poder conectarnos
        with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False) as tmp_db:
            temp_db_path = tmp_db.name
            tmp_db.write(db_bytes)
        
        # 2. Conectar al archivo temporal y preparar los datos para la inserción
        with sqlite3.connect(temp_db_path) as conn:
            cursor = conn.cursor()
            
            # Generar UUID y hashear la contraseña
            uuid_empleado = str(uuid.uuid4())
            contrasena_hash = hash_contrasena(contrasena_temporal)
            
            # Fecha actual para 'last_modified'
            last_modified_timestamp = int(datetime.utcnow().timestamp())
            
            # Preparamos el SQL para la inserción
            sql = """
            INSERT INTO usuarios (
                uuid, last_modified, needs_sync, nombre_usuario, numero_empleado,
                contrasena, fecha_ingreso, fecha_nacimiento, correo_electronico,
                numero_telefonico, activo, rol, cuenta_master,
                cambio_contrasena_obligatorio
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """
            
            # Preparamos la tupla de datos
            # El campo 'numero_empleado' debe coincidir con el 'username_empleado'
            # 'datos_propietario' debe contener los campos del registro de PostgreSQL
            data = (
                uuid_empleado, 
                last_modified_timestamp,
                1, # needs_sync: 1 (siempre necesita sincronizarse la primera vez)
                username_empleado,
                # El 'numero_empleado' y el 'username_empleado' probablemente sean el mismo
                int(username_empleado),
                contrasena_hash,
                # La fecha de ingreso es hoy
                datetime.utcnow().strftime('%Y-%m-%d'),
                datos_propietario.get('fecha_nacimiento'),
                datos_propietario.get('correo'),
                datos_propietario.get('telefono'),
                1, # activo: 1 (True)
                'Administrador', # rol: 'Administrador' por ser el primer usuario
                1, # cuenta_master: 1 (True)
                1 # cambio_contrasena_obligatorio: 1 (True)
            )
            
            # 3. Ejecutar la inserción y guardar los cambios
            cursor.execute(sql, data)
            conn.commit()
            
        # 4. Leer los bytes del archivo modificado para devolverlos
        with open(temp_db_path, "rb") as f:
            db_bytes_modificado = f.read()
        
        return db_bytes_modificado

    except Exception as e:
        print(f"🔥🔥 ERROR añadiendo el primer administrador a la DB de usuarios: {e}")
        return None
    finally:
        # 5. Asegurarse de borrar el archivo temporal
        if temp_db_path and os.path.exists(temp_db_path):
            os.remove(temp_db_path)

