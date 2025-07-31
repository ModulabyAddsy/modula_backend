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

def activar_suscripcion_y_terminal(id_cuenta: int, id_empresa_addsy: str, id_terminal_uuid: str, id_stripe: str):
    """
    Activa la suscripción, crea la primera sucursal, la primera terminal
    y guarda la ruta de la nube para la sucursal.
    """
    conn = get_connection()
    if not conn: return None, None  # Devolvemos None para la ruta si falla la conexión

    try:
        with conn.cursor() as cur:
            fecha_vencimiento_prueba = datetime.utcnow() + timedelta(days=14)
            
            # 1. Crear la suscripción
            cur.execute(
                "INSERT INTO suscripciones_software (id_cuenta_addsy, software_nombre, estado_suscripcion, fecha_vencimiento) VALUES (%s, 'modula', 'prueba_gratis', %s) RETURNING id;",
                (id_cuenta, fecha_vencimiento_prueba)
            )
            suscripcion_id = cur.fetchone()['id']

            # 2. Crear la primera sucursal
            cur.execute(
                "INSERT INTO sucursales (id_cuenta_addsy, nombre, id_suscripcion) VALUES (%s, %s, %s) RETURNING id;",
                (id_cuenta, 'Sucursal Principal', suscripcion_id)
            )
            sucursal_id = cur.fetchone()['id']

            # 3. CONSTRUIR Y GUARDAR LA RUTA DE LA NUBE (NUEVO)
            # Construimos la ruta usando el ID de la empresa y el nuevo ID de la sucursal
            ruta_cloud_sucursal = f"{id_empresa_addsy}/suc_{sucursal_id}/"
            print(f"🔗 Vinculando sucursal ID {sucursal_id} con la ruta: {ruta_cloud_sucursal}")
            
            # Actualizamos el registro de la sucursal con su ruta en la nube
            cur.execute(
                "UPDATE sucursales SET ruta_cloud = %s WHERE id = %s;",
                (ruta_cloud_sucursal, sucursal_id)
            )

            # 4. Crear la primera terminal
            cur.execute(
                "INSERT INTO modula_terminales (id_terminal, id_cuenta_addsy, id_sucursal, nombre_terminal, activa) VALUES (%s, %s, %s, %s, true);", 
                (id_terminal_uuid, id_cuenta, sucursal_id, 'Terminal Principal')
            )
            
            # 5. Actualizar la cuenta con el ID de Stripe
            cur.execute(
                "UPDATE cuentas_addsy SET id_suscripcion_stripe = %s WHERE id = %s;", 
                (id_stripe, id_cuenta)
            )
            
            conn.commit()
            print(f"✅ Suscripción, sucursal y terminal activadas para cuenta ID {id_cuenta}.")
            # Devolvemos True y la ruta creada para que el endpoint pueda usarla
            return True, ruta_cloud_sucursal
    except Exception as e:
        conn.rollback()
        print(f"🔥🔥 ERROR en la activación de servicios: {e}")
        # Devolvemos False y None en caso de error
        return False, None
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
        
def buscar_terminal_activa_por_id(id_terminal: str):
    """
    Busca una terminal por su ID y se une con sucursales y cuentas
    para obtener toda la información necesaria para la sesión.
    """
    conn = get_connection()
    if not conn: return None
    
    # ✅ CORRECCIÓN: Añadir "t.direccion_ip" a la lista de columnas seleccionadas.
    query = """
        SELECT 
            t.id_terminal, t.activa, t.direccion_ip,
            s.id as id_sucursal, s.nombre as nombre_sucursal,
            c.id as id_cuenta_addsy, c.id_empresa_addsy, c.nombre_empresa, c.correo
        FROM 
            modula_terminales t
        JOIN 
            sucursales s ON t.id_sucursal = s.id
        JOIN 
            cuentas_addsy c ON s.id_cuenta_addsy = c.id
        WHERE 
            t.id_terminal = %s AND t.activa = TRUE;
    """
    try:
        with conn.cursor() as cur:
            cur.execute(query, (id_terminal,))
            terminal_data = cur.fetchone()
        return terminal_data
    except Exception as e:
        print(f"🔥🔥 ERROR al buscar terminal activa por ID: {e}")
        return None
    finally:
        if conn: conn.close()
        
def actualizar_y_verificar_suscripcion(id_cuenta: int):
    """
    Actualiza el estado de la suscripción si ha vencido y luego devuelve
    el estado actual.
    """
    conn = get_connection()
    if not conn: return None
    try:
        with conn.cursor() as cur:
            # Primero, actualizamos las suscripciones vencidas de prueba o activas
            cur.execute("""
                UPDATE suscripciones_software
                SET estado_suscripcion = 'vencida'
                WHERE id_cuenta_addsy = %s AND fecha_vencimiento < NOW() 
                AND estado_suscripcion IN ('prueba_gratis', 'activa');
            """, (id_cuenta,))
            
            # Luego, obtenemos el estado actual de la suscripción
            cur.execute(
                "SELECT estado_suscripcion FROM suscripciones_software WHERE id_cuenta_addsy = %s;",
                (id_cuenta,)
            )
            suscripcion = cur.fetchone()
            conn.commit()
            return suscripcion
    except Exception as e:
        conn.rollback()
        print(f"🔥🔥 ERROR al actualizar/verificar suscripción: {e}")
        return None
    finally:
        if conn: conn.close()

def actualizar_contadores_suscripcion(id_cuenta: int):
    """
    Recuenta las sucursales y terminales activas y actualiza la tabla de suscripciones.
    """
    conn = get_connection()
    if not conn: return
    try:
        with conn.cursor() as cur:
            # Contar sucursales
            cur.execute("SELECT count(*) FROM sucursales WHERE id_cuenta_addsy = %s;", (id_cuenta,))
            num_sucursales = cur.fetchone()['count']
            
            # Contar terminales activas
            cur.execute("SELECT count(*) FROM modula_terminales WHERE id_cuenta_addsy = %s AND activa = TRUE;", (id_cuenta,))
            num_terminales = cur.fetchone()['count']

            # Actualizar la tabla de suscripciones
            cur.execute("""
                UPDATE suscripciones_software
                SET numero_sucursales = %s, terminales_activas = %s
                WHERE id_cuenta_addsy = %s;
            """, (num_sucursales, num_terminales, id_cuenta))
            conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"🔥🔥 ERROR al actualizar contadores: {e}")
    finally:
        if conn: conn.close()

def actualizar_ip_terminal(id_terminal: str, ip: str):
    """Actualiza la dirección IP y la última sincronización de una terminal."""
    conn = get_connection()
    if not conn: return
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE modula_terminales SET direccion_ip = %s, ultima_sincronizacion = NOW() WHERE id_terminal = %s;",
                (ip, id_terminal)
            )
            conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"🔥🔥 ERROR al actualizar IP de terminal: {e}")
    finally:
        if conn: conn.close()
        
def crear_nueva_sucursal(id_cuenta: int, id_empresa_addsy: str, nombre_sucursal: str):
    """
    Crea un nuevo registro de sucursal, construye su ruta en la nube y la guarda en una transacción.
    """
    conn = get_connection()
    if not conn: return None
    
    try:
        with conn.cursor() as cur:
            # 1. Obtener el id de la suscripción activa de la cuenta
            cur.execute(
                "SELECT id FROM suscripciones_software WHERE id_cuenta_addsy = %s ORDER BY fecha_vencimiento DESC LIMIT 1;",
                (id_cuenta,)
            )
            suscripcion = cur.fetchone()
            if not suscripcion:
                raise Exception("No se encontró una suscripción activa para la cuenta.")
            suscripcion_id = suscripcion['id']

            # 2. Insertar la nueva sucursal y obtener su ID
            cur.execute(
                "INSERT INTO sucursales (id_cuenta_addsy, nombre, id_suscripcion) VALUES (%s, %s, %s) RETURNING id;",
                (id_cuenta, nombre_sucursal, suscripcion_id)
            )
            sucursal_id = cur.fetchone()['id']

            # 3. Construir la ruta y actualizar el registro
            ruta_cloud_sucursal = f"{id_empresa_addsy}/suc_{sucursal_id}/"
            cur.execute(
                "UPDATE sucursales SET ruta_cloud = %s WHERE id = %s RETURNING *;",
                (ruta_cloud_sucursal, sucursal_id)
            )
            nueva_sucursal_completa = cur.fetchone()
            
            conn.commit()
            print(f"✅ Sucursal '{nombre_sucursal}' (ID: {sucursal_id}) creada y vinculada a '{ruta_cloud_sucursal}'.")
            return nueva_sucursal_completa

    except Exception as e:
        conn.rollback()
        print(f"🔥🔥 ERROR creando nueva sucursal: {e}")
        return None
    finally:
        if conn: conn.close()

def buscar_sucursal_por_ip_en_otra_terminal(id_terminal_actual: str, ip: str, id_cuenta: int):
    """
    Busca si otra terminal de la misma cuenta comparte la misma IP,
    lo que sugiere que el usuario está en una sucursal ya registrada.
    """
    conn = get_connection()
    if not conn: return None
    query = """
        SELECT s.id, s.nombre FROM modula_terminales t
        JOIN sucursales s ON t.id_sucursal = s.id
        WHERE t.id_cuenta_addsy = %s AND t.direccion_ip = %s AND t.id_terminal != %s
        LIMIT 1;
    """
    try:
        with conn.cursor() as cur:
            cur.execute(query, (id_cuenta, ip, id_terminal_actual))
            return cur.fetchone()
    finally:
        if conn: conn.close()

def get_sucursales_por_cuenta(id_cuenta: int):
    """Obtiene una lista de todas las sucursales de una cuenta."""
    conn = get_connection()
    if not conn: return []
    query = "SELECT id, nombre FROM sucursales WHERE id_cuenta_addsy = %s ORDER BY nombre;"
    try:
        with conn.cursor() as cur:
            cur.execute(query, (id_cuenta,))
            return cur.fetchall()
    finally:
        if conn: conn.close()

def actualizar_sucursal_de_terminal(id_terminal: str, id_sucursal_nueva: int):
    """Mueve una terminal a una nueva sucursal."""
    conn = get_connection()
    if not conn: return False
    query = "UPDATE modula_terminales SET id_sucursal = %s WHERE id_terminal = %s;"
    try:
        with conn.cursor() as cur:
            cur.execute(query, (id_sucursal_nueva, id_terminal))
            updated_rows = cur.rowcount
        conn.commit()
        return updated_rows > 0
    except Exception as e:
        conn.rollback()
        print(f"🔥🔥 ERROR al actualizar sucursal de terminal: {e}")
        return False
    finally:
        if conn: conn.close()
