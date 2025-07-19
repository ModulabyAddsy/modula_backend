# db.py
# Módulo de conexión y operaciones básicas con la base de datos PostgreSQL

import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

# Conexión a PostgreSQL usando variables .env
def get_connection():
    return psycopg2.connect(
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT"),
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASS"),
        cursor_factory=RealDictCursor
    )

# Inicializa la tabla de usuarios si no existe
def crear_tabla_usuarios():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id SERIAL PRIMARY KEY,
            nombre_completo TEXT NOT NULL,
            telefono TEXT NOT NULL,
            fecha_nacimiento DATE NOT NULL,
            correo TEXT NOT NULL UNIQUE,
            correo_recuperacion TEXT,
            contrasena TEXT NOT NULL,
            nombre_empresa TEXT NOT NULL,
            id_empresa TEXT NOT NULL,
            rfc TEXT,
            token TEXT,
            token_expira TIMESTAMP,
            estatus TEXT DEFAULT 'pendiente',
            fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    conn.commit()
    conn.close()

# Obtiene usuario por correo (para validar duplicados o verificar estatus)
def obtener_usuario_por_correo(correo):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM usuarios WHERE correo = %s;", (correo,))
    usuario = cur.fetchone()
    conn.close()
    return usuario

# Busca si ya existe la empresa, si no, genera un nuevo ID (MOD_EMP_####)
def obtener_o_crear_id_empresa(nombre_empresa):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT id_empresa FROM usuarios WHERE nombre_empresa = %s LIMIT 1;", (nombre_empresa,))
    empresa_existente = cur.fetchone()

    if empresa_existente:
        conn.close()
        return empresa_existente['id_empresa']

    cur.execute("SELECT COUNT(DISTINCT id_empresa) FROM usuarios;")
    total_empresas = cur.fetchone()["count"]
    nuevo_id = f"MOD_EMP_{1001 + total_empresas}"
    conn.close()
    return nuevo_id

# --- VERSIÓN CORREGIDA Y ÚNICA DE registrar_usuario ---
def registrar_usuario(data: dict):
    """
    Inserta un nuevo usuario en la base de datos y devuelve su ID.
    Devuelve None si la inserción falla.
    """
    conn = get_connection()
    cur = conn.cursor()
    nuevo_id = None
    estatus = data.get("estatus", "pendiente_pago")

    try:
        cur.execute("""
            INSERT INTO usuarios (
                nombre_completo, telefono, fecha_nacimiento, correo,
                correo_recuperacion, contrasena, nombre_empresa,
                id_empresa, rfc, token, token_expira, estatus
            ) VALUES (
                %(nombre_completo)s, %(telefono)s, %(fecha_nacimiento)s, %(correo)s,
                %(correo_recuperacion)s, %(contrasena)s, %(nombre_empresa)s,
                %(id_empresa)s, %(rfc)s, %(token)s, %(token_expira)s, %(estatus)s
            ) RETURNING id;
        """, {
            "nombre_completo": data["nombre_completo"],
            "telefono": data["telefono"],
            "fecha_nacimiento": data["fecha_nacimiento"],
            "correo": data["correo"],
            "correo_recuperacion": data.get("correo_recuperacion"),
            "contrasena": data["contrasena"],
            "nombre_empresa": data["nombre_empresa"],
            "id_empresa": data["id_empresa"],
            "rfc": data.get("rfc"),
            "token": data.get("token"),
            "token_expira": data.get("token_expira"),
            "estatus": estatus
        })
        # Obtenemos el ID del registro recién insertado
        resultado = cur.fetchone()
        if resultado:
            nuevo_id = resultado['id']
        
        conn.commit()
        print(f"✅ Usuario '{data['correo']}' insertado con ID: {nuevo_id}. Commit realizado.")
    
    except Exception as e:
        conn.rollback()
        print(f"❌ ERROR al registrar usuario en la BD: {e}")
        # No relanzamos el error, simplemente devolveremos None
    
    finally:
        conn.close()
        
    return nuevo_id

def actualizar_usuario_para_verificacion(correo: str, token: str, token_expira):
    """
    Actualiza el estado del usuario a 'pendiente' y guarda su token de verificación.
    """
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        UPDATE usuarios
        SET estatus = 'pendiente',
            token = %s,
            token_expira = %s
        WHERE correo = %s AND estatus = 'pendiente_pago';
    """, (token, token_expira, correo))
    conn.commit()
    conn.close()
    print(f"ℹ️ Usuario {correo} actualizado a 'pendiente' para verificación.")