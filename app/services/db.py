# app/services/db.py
import os
import psycopg 
from psycopg.rows import dict_row
from dotenv import load_dotenv
from datetime import datetime, timedelta
from uuid import UUID

# ... (la función get_connection y las de autenticación no cambian) ...

# (pegar aquí las funciones existentes de la respuesta anterior: get_connection, buscar_cuenta_addsy_por_correo, etc.)
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

# ... (resto de funciones de auth)

# --- 👉 Nuevas Funciones para Suscripciones ---

def get_suscripciones_por_cuenta(id_cuenta: int):
    """Obtiene todas las suscripciones de una cuenta."""
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

# --- 👉 Nuevas Funciones para Terminales ---

def get_terminales_por_cuenta(id_cuenta: int):
    """Obtiene todas las terminales asociadas a una cuenta."""
    conn = get_connection()
    if not conn: return []
    query = "SELECT * FROM modula_terminales WHERE id_empresa = %s;"
    try:
        with conn.cursor() as cur:
            cur.execute(query, (id_cuenta,))
            terminales = cur.fetchall()
        return terminales
    finally:
        if conn: conn.close()

def crear_terminal(id_cuenta: int, terminal_data: dict):
    """Crea un nuevo registro de terminal en la base de datos."""
    conn = get_connection()
    if not conn: return None
    
    sql = """
        INSERT INTO modula_terminales 
            (id_terminal, id_empresa, id_sucursal, nombre_terminal, activa)
        VALUES (%s, %s, %s, %s, true)
        RETURNING *;
    """
    params = (
        terminal_data['id_terminal'],
        id_cuenta, # id_empresa ahora es el id de la cuenta
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