# app/services/db.py
import os
import psycopg 
from psycopg.rows import dict_row
from dotenv import load_dotenv
from datetime import datetime, timedelta

load_dotenv()

def get_connection():
    """Establece la conexión con la base de datos PostgreSQL en Render."""
    try:
        db_url = os.getenv("DATABASE_URL")
        if not db_url:
            raise Exception("La variable de entorno DATABASE_URL no está definida.")
            
        if "sslmode" not in db_url:
            db_url += "?sslmode=require"
            
        conn = psycopg.connect(db_url, row_factory=dict_row)
        return conn
    except (Exception, psycopg.OperationalError) as e:
        print(f"🔥🔥 ERROR DE CONEXIÓN A LA BASE DE DATOS: {e}")
        return None

# --- 👉 FUNCIONES ADAPTADAS A LA NUEVA ARQUITECTURA ---

def buscar_cuenta_addsy_por_correo(correo: str):
    """Busca una cuenta en 'cuentas_addsy' y une la información de su empresa."""
    conn = get_connection()
    if not conn: return None
    
    # 👉 Query adaptada a la nueva tabla 'cuentas_addsy'
    query = """
        SELECT ca.*, e.id AS id_empresa, e.nombre_empresa
        FROM cuentas_addsy ca
        JOIN empresas e ON ca.id_empresa = e.id
        WHERE ca.correo = %s;
    """
    try:
        with conn.cursor() as cur:
            cur.execute(query, (correo,))
            usuario = cur.fetchone()
        return usuario
    finally:
        if conn: conn.close()

def crear_recursos_iniciales(data: dict):
    """
    Crea una nueva empresa y la cuenta addsy inicial en una transacción.
    El estatus inicial será 'pendiente_pago'.
    """
    conn = get_connection()
    if not conn: return None, None

    try:
        with conn.cursor() as cur:
            # 1. Crear la empresa
            cur.execute(
                "INSERT INTO empresas (nombre_empresa, rfc) VALUES (%s, %s) RETURNING id;",
                (data['nombre_empresa'], data.get('rfc'))
            )
            empresa_id = cur.fetchone()['id']

            # 2. Crear la cuenta addsy principal
            # 👉 INSERT adaptado a la tabla y columnas de 'cuentas_addsy'
            cur.execute(
                """
                INSERT INTO cuentas_addsy 
                    (id_empresa, nombre_completo, telefono, correo, contrasena_hash, estatus_cuenta, fecha_nacimiento, nombre_empresa, rfc) 
                VALUES 
                    (%s, %s, %s, %s, %s, 'pendiente_pago', %s, %s, %s) RETURNING id;
                """,
                (
                    empresa_id, data['nombre_completo'], data['telefono'], data['correo'],
                    data['contrasena_hash'], data['fecha_nacimiento'], data['nombre_empresa'], data.get('rfc')
                )
            )
            cuenta_id = cur.fetchone()['id']

            conn.commit()
            print(f"✅ Pre-registro exitoso para Empresa ID:{empresa_id} y Cuenta ID:{cuenta_id}.")
            return empresa_id, cuenta_id
    
    except Exception as e:
        conn.rollback()
        print(f"🔥🔥 ERROR en transacción de creación inicial: {e}")
        return None, None
    finally:
        if conn: conn.close()

def actualizar_cuenta_para_verificacion(correo: str, token: str, token_expira: datetime):
    """Actualiza la cuenta a 'pendiente_verificacion' y guarda el token."""
    conn = get_connection()
    if not conn: return False
    
    query = """
        UPDATE cuentas_addsy 
        SET estatus_cuenta = 'pendiente_verificacion', token_recuperacion = %s, token_expira = %s 
        WHERE correo = %s AND estatus_cuenta = 'pendiente_pago';
    """
    try:
        with conn.cursor() as cur:
            cur.execute(query, (token, token_expira, correo))
            updated_rows = cur.rowcount
        conn.commit()
        print(f"ℹ️ Cuenta {correo} actualizada para verificación. Filas afectadas: {updated_rows}")
        return updated_rows > 0
    finally:
        if conn: conn.close()

def verificar_token_y_activar_cuenta(token: str):
    """Busca una cuenta por token, la activa si es válido y devuelve sus datos."""
    conn = get_connection()
    if not conn: return None
    
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM cuentas_addsy WHERE token_recuperacion = %s;", (token,))
            cuenta = cur.fetchone()

            if not cuenta: return "invalid_token"
            if not cuenta["token_expira"] or cuenta["token_expira"] < datetime.now(cuenta["token_expira"].tzinfo): return "expired_token"

            cur.execute(
                "UPDATE cuentas_addsy SET estatus_cuenta = 'verificada', token_recuperacion = NULL, token_expira = NULL WHERE id = %s RETURNING *;",
                (cuenta["id"],)
            )
            cuenta_activada = cur.fetchone()
            conn.commit()
            return cuenta_activada
    except Exception as e:
        conn.rollback()
        print(f"🔥🔥 ERROR al verificar token: {e}")
        return None
    finally:
        if conn: conn.close()
        
def activar_suscripcion_y_terminal(id_cuenta: int, id_empresa: int, id_terminal: str, id_stripe: str):
    """
    Crea la suscripción, la sucursal principal y la terminal asociada después de una verificación exitosa.
    """
    conn = get_connection()
    if not conn: return False
    
    try:
        with conn.cursor() as cur:
            # 1. Crear suscripción de prueba para Modula
            fecha_vencimiento_prueba = datetime.utcnow() + timedelta(days=14)
            cur.execute(
                """
                INSERT INTO suscripciones_software 
                    (id_cuenta_addsy, software_nombre, estado_suscripcion, fecha_vencimiento)
                VALUES (%s, 'modula', 'prueba_gratis', %s)
                """,
                (id_cuenta, fecha_vencimiento_prueba)
            )
            
            # 2. Crear sucursal principal
            cur.execute(
                "INSERT INTO sucursales (id_empresa, nombre) VALUES (%s, %s) RETURNING id;",
                (id_empresa, 'Sucursal Principal')
            )
            sucursal_id = cur.fetchone()['id']

            # 3. Registrar la terminal
            cur.execute(
                "INSERT INTO modula_terminales (id_terminal, id_empresa, id_sucursal, nombre_terminal, activa) VALUES (%s, %s, %s, %s, true);",
                (id_terminal, id_empresa, sucursal_id, 'Terminal Principal')
            )
            
            # 4. (Opcional) Guardar el ID de suscripción de Stripe en la tabla 'empresas'
            cur.execute("UPDATE empresas SET id_suscripcion_stripe = %s WHERE id = %s;", (id_stripe, id_empresa))

            conn.commit()
            print(f"✅ Suscripción, sucursal y terminal activadas para cuenta ID {id_cuenta}.")
            return True
    except Exception as e:
        conn.rollback()
        print(f"🔥🔥 ERROR en la activación de servicios: {e}")
        return False
    finally:
        if conn: conn.close()