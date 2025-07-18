from app.services.db import get_connection

def verificar_y_actualizar_estructura():
    conn = get_connection()
    cursor = conn.cursor()

    print("🔍 Verificando estructura de base de datos...")

    # --- 1. AÑADIR COLUMNA 'bloqueado' A USUARIOS ---
    cursor.execute("""
        SELECT column_name FROM information_schema.columns 
        WHERE table_name='usuarios' AND column_name='bloqueado';
    """)
    if not cursor.fetchone():
        print("🛠️ Añadiendo columna 'bloqueado'...")
        cursor.execute("ALTER TABLE usuarios ADD COLUMN bloqueado BOOLEAN DEFAULT FALSE;")
        conn.commit()
    else:
        print("✅ Columna 'bloqueado' ya existe.")

    # --- 2. CREAR TABLA TERMINALES SI NO EXISTE ---
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS terminales (
            id_terminal TEXT PRIMARY KEY,
            id_empresa TEXT NOT NULL,
            numero_sucursal TEXT NOT NULL,
            activa BOOLEAN DEFAULT TRUE
        );
    """)
    print("✅ Verificada tabla 'terminales'.")
    
    if not cursor.fetchone():
        print("🛠️ Añadiendo columna 'ip_terminal'...")
        cursor.execute("ALTER TABLE terminales ADD COLUMN IF NOT EXISTS ip_terminal TEXT;")
        conn.commit()
    else:
        print("✅ Columna 'ip_terminal' ya existe.")

    conn.commit()
    cursor.close()
    conn.close()
    print("✅ Estructura verificada.")