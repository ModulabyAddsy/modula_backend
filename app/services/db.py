# app/services/db.py
import os
import psycopg
from psycopg.rows import dict_row
from dotenv import load_dotenv
from datetime import datetime, timedelta, timezone # Asegúrate de importar timezone
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
                    telefono, correo, contrasena_hash, estatus_cuenta, fecha_nacimiento,
                    claim_token
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id;
            """
            params = (
                id_empresa_addsy, data['nombre_empresa'], data.get('rfc'), data['nombre_completo'],
                data['telefono'], data['correo'], data['contrasena_hash'],
                'pendiente_pago', data['fecha_nacimiento'],
                data.get('claim_token') # <-- Añadir el nuevo valor
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
        
def buscar_cuenta_por_claim_token(claim_token: str):
    conn = get_connection()
    if not conn: return None
    query = "SELECT * FROM cuentas_addsy WHERE claim_token = %s;"
    try:
        with conn.cursor() as cur:
            cur.execute(query, (claim_token,))
            cuenta = cur.fetchone()
        return cuenta
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
    Activa la suscripción, crea la primera sucursal y crea o asigna la primera terminal.
    Devuelve un diccionario con los resultados.
    """
    conn = get_connection()
    if not conn: return {'exito': False}

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

            # 3. Construir y guardar la ruta de la nube
            ruta_cloud_sucursal = f"{id_empresa_addsy}/suc_{sucursal_id}/"
            print(f"🔗 Vinculando sucursal ID {sucursal_id} con la ruta: {ruta_cloud_sucursal}")
            cur.execute(
                "UPDATE sucursales SET ruta_cloud = %s WHERE id = %s;",
                (ruta_cloud_sucursal, sucursal_id)
            )

            # --- ¡NUEVA LÓGICA INTELIGENTE PARA LA TERMINAL! ---
            # 4. Comprobar si la terminal ya existe
            cur.execute("SELECT * FROM modula_terminales WHERE id_terminal = %s;", (id_terminal_uuid,))
            terminal_existente = cur.fetchone()

            if terminal_existente:
                # Si existe, la actualizamos para asignarla a la nueva cuenta y sucursal
                print(f"Terminal {id_terminal_uuid} ya existe. Asignando a nueva cuenta y sucursal.")
                cur.execute(
                    """
                    UPDATE modula_terminales 
                    SET id_cuenta_addsy = %s, id_sucursal = %s, nombre_terminal = %s, activa = true
                    WHERE id_terminal = %s;
                    """,
                    (id_cuenta, sucursal_id, 'Terminal Principal', id_terminal_uuid)
                )
            else:
                # Si no existe, la creamos como antes
                print(f"Terminal {id_terminal_uuid} no existe. Creando nuevo registro.")
                cur.execute(
                    "INSERT INTO modula_terminales (id_terminal, id_cuenta_addsy, id_sucursal, nombre_terminal, activa) VALUES (%s, %s, %s, %s, true);", 
                    (id_terminal_uuid, id_cuenta, sucursal_id, 'Terminal Principal')
                )
            
            conn.commit()
            print(f"✅ Suscripción, sucursal y terminal activadas para cuenta ID {id_cuenta}.")
            
            return {
                'exito': True, 
                'ruta_cloud': ruta_cloud_sucursal, 
                'id_sucursal': sucursal_id
            }
    except Exception as e:
        conn.rollback()
        print(f"🔥🔥 ERROR en la activación de servicios: {e}")
        return {'exito': False}
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

def crear_terminal(id_cuenta: int, terminal_data: dict, client_ip: str): 
    conn = get_connection()
    if not conn: return None
    sql = """
        INSERT INTO modula_terminales 
            (id_terminal, id_cuenta_addsy, id_sucursal, nombre_terminal, activa, direccion_ip)
        VALUES (%s, %s, %s, %s, true, %s) 
        RETURNING *;
    """
    params = (
        terminal_data['id_terminal'],
        id_cuenta,
        terminal_data['id_sucursal'],
        terminal_data['nombre_terminal'],
        client_ip 
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
        
def guardar_stripe_subscription_id(id_cuenta: int, stripe_sub_id: str):
    conn = get_connection()
    if not conn: return False
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE cuentas_addsy SET id_suscripcion_stripe = %s WHERE id = %s;",
                (stripe_sub_id, id_cuenta)
            )
            conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        print(f"🔥🔥 ERROR guardando stripe_subscription_id: {e}")
        return False
    finally:
        if conn: conn.close()
        
def actualizar_suscripcion_tras_pago(stripe_sub_id: str, nuevo_periodo_fin_ts: int):
    """
    Busca una suscripción por su ID de Stripe y actualiza su estado a 'activa'
    y la fecha de vencimiento con el nuevo periodo.
    """
    conn = get_connection()
    if not conn: return False
    
    # Convertir el timestamp de Stripe a un objeto datetime
    nuevo_vencimiento = datetime.fromtimestamp(nuevo_periodo_fin_ts, tz=timezone.utc)
    
    try:
        with conn.cursor() as cur:
            # Encontramos el id_cuenta_addsy a través de la tabla cuentas_addsy
            cur.execute(
                "SELECT id FROM cuentas_addsy WHERE id_suscripcion_stripe = %s;",
                (stripe_sub_id,)
            )
            cuenta = cur.fetchone()
            if not cuenta:
                print(f"ℹ️ Webhook 'invoice.paid' recibido para sub {stripe_sub_id}, pero no se encontró cuenta asociada.")
                return False
            
            id_cuenta = cuenta['id']

            # Actualizamos la tabla de suscripciones
            cur.execute(
                """
                UPDATE suscripciones_software
                SET estado_suscripcion = 'activa', fecha_vencimiento = %s
                WHERE id_cuenta_addsy = %s;
                """,
                (nuevo_vencimiento, id_cuenta)
            )
            conn.commit()
            print(f"✅ Suscripción para cuenta {id_cuenta} (Stripe: {stripe_sub_id}) actualizada a 'activa' hasta {nuevo_vencimiento}.")
            return True
    except Exception as e:
        conn.rollback()
        print(f"🔥🔥 ERROR actualizando suscripción tras pago: {e}")
        return False
    finally:
        if conn: conn.close()

def guardar_token_reseteo(correo: str, token: str, token_expira: datetime):
    """Guarda un token de reseteo para una cuenta."""
    conn = get_connection()
    if not conn: return False
    query = "UPDATE cuentas_addsy SET token_recuperacion = %s, token_expira = %s WHERE correo = %s;"
    try:
        with conn.cursor() as cur:
            cur.execute(query, (token, token_expira, correo))
        conn.commit()
        return True
    finally:
        if conn: conn.close()

def resetear_contrasena_con_token(token: str, nueva_contrasena_hash: str):
    """Busca una cuenta por token y, si es válido, resetea la contraseña."""
    conn = get_connection()
    if not conn: return "db_error"
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM cuentas_addsy WHERE token_recuperacion = %s;", (token,))
            cuenta = cur.fetchone()
            if not cuenta:
                return "invalid_token"
            if not cuenta["token_expira"] or cuenta["token_expira"] < datetime.now(cuenta["token_expira"].tzinfo):
                return "expired_token"
            
            # El token es válido, actualizamos la contraseña y lo anulamos
            cur.execute(
                "UPDATE cuentas_addsy SET contrasena_hash = %s, token_recuperacion = NULL, token_expira = NULL WHERE id = %s;",
                (nueva_contrasena_hash, cuenta["id"])
            )
            conn.commit()
            return "success"
    except Exception as e:
        conn.rollback()
        print(f"🔥🔥 ERROR reseteando contraseña: {e}")
        return "db_error"
    finally:
        if conn: conn.close()

def buscar_terminal_por_hardware_id(hardware_id: str):
    """Busca una terminal por su id_terminal (que ahora es el ID de hardware)."""
    # Reutilizamos la función que ya teníamos, ¡es la misma lógica!
    return buscar_terminal_activa_por_id(hardware_id)

def get_ubicaciones_autorizadas(id_sucursal: int):
    """Obtiene todas las ubicaciones autorizadas para una sucursal específica."""
    conn = get_connection()
    if not conn: return []
    query = "SELECT * FROM sucursal_ubicaciones WHERE id_sucursal = %s;"
    try:
        with conn.cursor() as cur:
            cur.execute(query, (id_sucursal,))
            return cur.fetchall()
    finally:
        if conn: conn.close()

def autorizar_nueva_ubicacion(id_sucursal: int, ip: str, geo_data: dict):
    """Guarda una nueva huella de ubicación como autorizada para una sucursal."""
    conn = get_connection()
    if not conn: return False
    query = """
        INSERT INTO sucursal_ubicaciones 
            (id_sucursal, ip_subnet, ciudad, region, pais, isp)
        VALUES (%s, %s, %s, %s, %s, %s);
    """
    params = (
        id_sucursal,
        ip, # PostgreSQL convierte automáticamente el string a tipo inet
        geo_data.get('ciudad'),
        geo_data.get('region'),
        geo_data.get('pais'),
        geo_data.get('isp')
    )
    try:
        with conn.cursor() as cur:
            cur.execute(query, params)
        conn.commit()
        print(f"✅ Nueva ubicación autorizada para sucursal {id_sucursal} con IP {ip}.")
        return True
    except Exception as e:
        conn.rollback()
        print(f"🔥🔥 ERROR autorizando nueva ubicación: {e}")
        return False
    finally:
        if conn: conn.close()
        
def get_sucursal_info(id_sucursal: int):
    """
    Busca y devuelve toda la información de una sucursal específica por su ID.
    Esencial para obtener la 'ruta_cloud' durante la sincronización.
    """
    conn = get_connection()
    if not conn: return None
    
    query = "SELECT * FROM sucursales WHERE id = %s;"
    
    try:
        with conn.cursor() as cur:
            cur.execute(query, (id_sucursal,))
            sucursal_data = cur.fetchone()
        return sucursal_data
    except Exception as e:
        print(f"🔥🔥 ERROR al buscar información de la sucursal por ID: {e}")
        return None
    finally:
        if conn: conn.close()
        
def get_latest_active_version():
    """
    Busca en la base de datos la única versión de la aplicación marcada como activa.
    """
    conn = get_connection()
    if not conn: return None
    
    query = "SELECT version, url, hash, notes FROM app_versions WHERE is_active = true LIMIT 1;"
    
    try:
        with conn.cursor() as cur:
            cur.execute(query)
            active_version = cur.fetchone()
        return active_version # Devuelve el diccionario de la versión o None si no se encuentra
    except Exception as e:
        print(f"🔥🔥 ERROR al buscar la versión activa de la app: {e}")
        return None
    finally:
        if conn: conn.close()
        
def guardar_stripe_customer_id(id_cuenta: int, stripe_customer_id: str):
    """Guarda el ID de Cliente de Stripe en la tabla de cuentas."""
    conn = get_connection()
    if not conn: return False
    try:
        with conn.cursor() as cur:
            # Asegúrate de que tu tabla 'cuentas_addsy' tenga la columna 'id_cliente_stripe'
            cur.execute(
                "UPDATE cuentas_addsy SET id_cliente_stripe = %s WHERE id = %s;",
                (stripe_customer_id, id_cuenta)
            )
            conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        print(f"🔥🔥 ERROR guardando stripe_customer_id: {e}")
        return False
    finally:
        if conn: conn.close()
        
def buscar_cuenta_addsy_por_id(id_cuenta: int):
    """Busca una cuenta por su ID primario."""
    conn = get_connection()
    if not conn: return None
    query = "SELECT * FROM cuentas_addsy WHERE id = %s;"
    try:
        with conn.cursor() as cur:
            cur.execute(query, (id_cuenta,))
            cuenta = cur.fetchone()
        return cuenta
    finally:
        if conn: conn.close()

