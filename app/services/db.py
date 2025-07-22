# app/services/db.py
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
from datetime import datetime # <-- ¡AQUÍ ESTÁ LA CORRECCIÓN!

load_dotenv()

def get_connection():
    """Establece la conexión con la base de datos PostgreSQL en Render."""
    try:
        # La URL completa es más robusta para la conexión
        db_url = os.getenv("DATABASE_URL")
        if db_url and "sslmode" not in db_url:
            db_url += "?sslmode=require"
            
        conn = psycopg2.connect(db_url, cursor_factory=RealDictCursor)
        return conn
    except (Exception, psycopg2.OperationalError) as e:
        print(f"🔥🔥 ERROR DE CONEXIÓN A LA BASE DE DATOS: {e}")
        return None

# --- FUNCIONES PARA LA ARQUITECTURA v2 ---

def buscar_usuario_admin_por_correo(correo: str):
    """Busca un admin por su correo y une la información de su empresa."""
    conn = get_connection()
    if not conn: return None
    
    query = """
        SELECT ua.*, e.id_empresa_addsy, e.nombre_empresa
        FROM usuarios_admin ua
        JOIN empresas e ON ua.id_empresa = e.id
        WHERE ua.correo = %s;
    """
    try:
        with conn.cursor() as cur:
            cur.execute(query, (correo,))
            usuario = cur.fetchone()
        return usuario
    finally:
        if conn:
            conn.close()

def crear_empresa_y_usuario_inicial(data: dict):
    """Crea una nueva empresa, su primera sucursal y el primer admin en una transacción."""
    conn = get_connection()
    if not conn: return None, None

    try:
        with conn.cursor() as cur:
            # Generar el ID legible para la empresa
            cur.execute("SELECT COUNT(*) FROM empresas;")
            total_empresas = cur.fetchone()['count']
            id_empresa_addsy = f"MOD_EMP_{1001 + total_empresas}"

            # 1. Crear la Empresa
            cur.execute(
                "INSERT INTO empresas (id_empresa_addsy, nombre_empresa, rfc, estatus_suscripcion) VALUES (%s, %s, %s, %s) RETURNING id;",
                (id_empresa_addsy, data['nombre_empresa'], data.get('rfc'), 'pendiente_pago')
            )
            empresa_id = cur.fetchone()['id']

            # 2. Crear el Usuario Administrador
            cur.execute(
                "INSERT INTO usuarios_admin (id_empresa, nombre_completo, telefono, correo, correo_recuperacion, contrasena_hash, estatus, fecha_nacimiento) VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id;",
                (empresa_id, data['nombre_completo'], data['telefono'], data['correo'], data.get('correo_recuperacion'), data['contrasena_hash'], 'pendiente_pago', data['fecha_nacimiento'])
            )
            usuario_id = cur.fetchone()['id']

            # 3. Crear la primera Sucursal por defecto
            cur.execute(
                "INSERT INTO sucursales (id_empresa, id_sucursal_addsy, nombre) VALUES (%s, %s, %s);",
                (empresa_id, 'SUC01', 'Sucursal Principal')
            )

            conn.commit()
            print(f"✅ Empresa '{data['nombre_empresa']}' y Admin '{data['correo']}' creados exitosamente.")
            return empresa_id, usuario_id
    
    except Exception as e:
        conn.rollback()
        print(f"🔥🔥 ERROR en transacción de creación: {e}")
        return None, None
    finally:
        if conn:
            conn.close()

def actualizar_estatus_admin_para_verificacion(correo: str, token: str, token_expira):
    """Actualiza el estatus del admin a 'pendiente' y guarda el token de verificación."""
    conn = get_connection()
    if not conn: return False
    
    query = "UPDATE usuarios_admin SET estatus = 'pendiente', token = %s, token_expira = %s WHERE correo = %s AND estatus = 'pendiente_pago';"
    try:
        with conn.cursor() as cur:
            cur.execute(query, (token, token_expira, correo))
            updated_rows = cur.rowcount
        conn.commit()
        print(f"ℹ️ Usuario admin {correo} actualizado para verificación. Filas afectadas: {updated_rows}")
        return updated_rows > 0
    finally:
        if conn:
            conn.close()

def verificar_token_y_activar_admin(token: str):
    """Busca un usuario por token, lo activa si es válido y devuelve sus datos."""
    conn = get_connection()
    if not conn: return None

    try:
        with conn.cursor() as cur:
            # 1. Buscar el usuario por el token
            cur.execute("SELECT * FROM usuarios_admin WHERE token = %s;", (token,))
            usuario = cur.fetchone()

            if not usuario:
                return "invalid_token"
            
            # 2. Verificar si el token ha expirado
            if usuario["token_expira"] < datetime.now(usuario["token_expira"].tzinfo):
                return "expired_token"

            # 3. Activar el usuario y limpiar el token
            cur.execute(
                "UPDATE usuarios_admin SET estatus = 'verificada', token = NULL, token_expira = NULL WHERE id = %s RETURNING *;",
                (usuario["id"],)
            )
            usuario_activado = cur.fetchone()
            conn.commit()
            return usuario_activado
    except Exception as e:
        print(f"🔥🔥 ERROR al verificar token: {e}")
        conn.rollback()
        return None
    finally:
        if conn:
            conn.close()