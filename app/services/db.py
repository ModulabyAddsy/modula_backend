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

    # Buscar si ya existe un id_empresa para ese nombre de empresa
    cur.execute("SELECT id_empresa FROM usuarios WHERE nombre_empresa = %s LIMIT 1;", (nombre_empresa,))
    empresa_existente = cur.fetchone()

    if empresa_existente:
        conn.close()
        return empresa_existente['id_empresa']

    # Si no existe, generar nuevo ID MOD_EMP_####
    cur.execute("SELECT COUNT(DISTINCT id_empresa) FROM usuarios;")
    total_empresas = cur.fetchone()["count"]
    nuevo_id = f"MOD_EMP_{1001 + total_empresas}"

    conn.close()
    return nuevo_id

# Registra un nuevo usuario con datos completos
def registrar_usuario(data: dict):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO usuarios (
            nombre_completo, telefono, fecha_nacimiento, correo,
            correo_recuperacion, contrasena, nombre_empresa,
            id_empresa, rfc, token, token_expira, estatus
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, (
        data["nombre_completo"],
        data["telefono"],
        data["fecha_nacimiento"],
        data["correo"],
        data["correo_recuperacion"],
        data["contrasena"],
        data["nombre_empresa"],
        data["id_empresa"],
        data["rfc"],
        data["token"],
        data["token_expira"],
        "pendiente"
    ))

    conn.commit()
    conn.close()