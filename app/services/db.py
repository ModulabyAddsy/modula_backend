# app/services/db.py
import os
import psycopg
from psycopg.rows import dict_row
from dotenv import load_dotenv
from datetime import datetime, timedelta
from uuid import UUID

def get_connection():
    try:
        db_url = os.getenv("DATABASE_URL") + "?sslmode=require"
        conn = psycopg.connect(db_url, row_factory=dict_row)
        return conn
    except (Exception) as e:
        print(f"🔥🔥 ERROR DE CONEXIÓN A LA BASE DE DATOS: {e}")
        return None

def buscar_cuenta_addsy_por_correo(correo: str):
    conn = get_connection()
    if not conn: return None
    query = "SELECT * FROM cuentas_addsy WHERE correo = %s;"
    try:
        with conn.cursor() as cur:
            cur.execute(query, (correo,))
            cuenta = cur.fetchone()
        return cuenta
    finally:
        if conn: conn.close()

def crear_cuenta_addsy(data: dict):
    conn = get_connection()
    if not conn: return None
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM cuentas_addsy;")
            total_cuentas = cur.fetchone()['count']
            id_empresa_addsy = f"MOD_EMP_{1001 + total_cuentas}"
            sql = """
                INSERT INTO cuentas_addsy (
                    id_empresa_addsy, nombre_empresa, rfc, nombre_completo, 
                    telefono, correo, contrasena_hash, estatus_cuenta, fecha_nacimiento
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id;
            """
            params = (
                id_empresa_addsy, data['nombre_empresa'], data.get('rfc'), data['nombre_completo'],
                data['telefono'], data['correo'], data['contrasena_hash'],
                'pendiente_pago', data['fecha_nacimiento']
            )
            cur.execute(sql, params)
            cuenta_id = cur.fetchone()['id']
            conn.commit()
            print(f"✅ Pre-registro de Cuenta ID:{cuenta_id} exitoso.")
            return cuenta_id
    except Exception as e:
        conn.rollback()
        print(f"🔥🔥 ERROR en transacción de creación de cuenta: {e}")
        return None
    finally:
        if conn: conn.close()

def actualizar_cuenta_para_verificacion(correo, token, token_expira):
    conn = get_connection()
    if not conn: return False
    query = "UPDATE cuentas_addsy SET estatus_cuenta = 'pendiente_verificacion', token_recuperacion = %s, token_expira = %s WHERE correo = %s AND estatus_cuenta = 'pendiente_pago';"
    try:
        with conn.cursor() as cur:
            cur.execute(query, (token, token_expira, correo))
            updated_rows = cur.rowcount
        conn.commit()
        return updated_rows > 0
    finally:
        if conn: conn.close()

def verificar_token_y_activar_cuenta(token: str):
    conn = get_connection()
    if not conn: return None
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM cuentas_addsy WHERE token_recuperacion = %s;", (token,))
            cuenta = cur.fetchone()
            if not cuenta:
                return "invalid_token"
            if not cuenta["token_expira"] or cuenta["token_expira"] < datetime.now(cuenta["token_expira"].tzinfo):
                return "expired_token"
            cur.execute(
                "UPDATE cuentas_addsy SET estatus_cuenta = 'verificada', token_recuperacion = NULL, token_expira = NULL WHERE id = %s RETURNING *;",
                (cuenta["id"],)
            )
            cuenta_activada = cur.fetchone()
            conn.commit()
            return cuenta_activada
    except Exception as e:
        print(f"🔥🔥 ERROR al verificar token: {e}")
        conn.rollback()
        return None
    finally:
        if conn:
            conn.close()

def activar_suscripcion_y_terminal(id_cuenta: int, id_terminal: str, id_stripe: str):
    conn = get_connection()
    if not conn: return False
    try:
        with conn.cursor() as cur:
            fecha_vencimiento_prueba = datetime.utcnow() + timedelta(days=14)
            cur.execute("INSERT INTO suscripciones_software (id_cuenta_addsy, software_nombre, estado_suscripcion, fecha_vencimiento) VALUES (%s, 'modula', 'prueba_gratis', %s)", (id_cuenta, fecha_vencimiento_prueba))
            
            # 👉 CORRECCIÓN: Usar la columna 'id_cuenta_addsy' en SUCURSALES
            cur.execute("INSERT INTO sucursales (id_cuenta_addsy, nombre) VALUES (%s, %s) RETURNING id;", (id_cuenta, 'Sucursal Principal'))
            sucursal_id = cur.fetchone()['id']

            # 👉 CORRECCIÓN: Usar la columna 'id_cuenta_addsy' en TERMINALES
            cur.execute("INSERT INTO modula_terminales (id_terminal, id_cuenta_addsy, id_sucursal, nombre_terminal, activa) VALUES (%s, %s, %s, %s, true);", (id_terminal, id_cuenta, sucursal_id, 'Terminal Principal'))
            
            cur.execute("UPDATE cuentas_addsy SET id_suscripcion_stripe = %s WHERE id = %s;", (id_stripe, id_cuenta))
            conn.commit()
            print(f"✅ Suscripción, sucursal y terminal activadas para cuenta ID {id_cuenta}.")
            return True
    except Exception as e:
        conn.rollback()
        print(f"🔥🔥 ERROR en la activación de servicios: {e}")
        return False
    finally:
        if conn: conn.close()

def get_suscripciones_por_cuenta(id_cuenta: int):
    conn = get_connection()
    if not conn: return []
    query = "SELECT * FROM suscripciones_software WHERE id_cuenta_addsy = %s;"
    try:
        with conn.cursor() as cur:
            cur.execute(query, (id_cuenta,))
            suscripciones = cur.fetchall()
        return suscripciones
    finally:
        if conn: conn.close()

def get_terminales_por_cuenta(id_cuenta: int):
    conn = get_connection()
    if not conn: return []
    # 👉 CORRECCIÓN: Usar la columna 'id_cuenta_addsy' para la consulta
    query = "SELECT * FROM modula_terminales WHERE id_cuenta_addsy = %s;"
    try:
        with conn.cursor() as cur:
            cur.execute(query, (id_cuenta,))
            terminales = cur.fetchall()
        return terminales
    finally:
        if conn: conn.close()

def crear_terminal(id_cuenta: int, terminal_data: dict):
    conn = get_connection()
    if not conn: return None
    sql = """
        INSERT INTO modula_terminales 
            (id_terminal, id_cuenta_addsy, id_sucursal, nombre_terminal, activa)
        VALUES (%s, %s, %s, %s, true)
        RETURNING *;
    """
    # 👉 CORRECCIÓN: Usar la columna 'id_cuenta_addsy' en el INSERT
    params = (
        terminal_data['id_terminal'],
        id_cuenta,
        terminal_data['id_sucursal'],
        terminal_data['nombre_terminal']
    )
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            nueva_terminal = cur.fetchone()
        conn.commit()
        return nueva_terminal
    except Exception as e:
        conn.rollback()
        print(f"🔥🔥 ERROR al crear terminal: {e}")
        return None
    finally:
        if conn: conn.close()
