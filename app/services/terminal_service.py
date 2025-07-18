# app/services/terminal_service.py
from app.services.db import get_connection

def crear_terminal_si_no_existe(id_terminal: str, id_empresa: str, ip_terminal: str) -> bool:
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT * FROM terminales WHERE id_terminal = %s AND id_empresa = %s;
    """, (id_terminal, id_empresa))
    if cur.fetchone():
        conn.close()
        return False  # Ya existía

    cur.execute("""
        SELECT numero_sucursal FROM terminales 
        WHERE id_empresa = %s AND ip_terminal = %s LIMIT 1;
    """, (id_empresa, ip_terminal))
    row = cur.fetchone()

    if row:
        numero_sucursal = row["numero_sucursal"]
    else:
        cur.execute("""
            SELECT COUNT(DISTINCT numero_sucursal) FROM terminales 
            WHERE id_empresa = %s;
        """, (id_empresa,))
        total = cur.fetchone()["count"]
        numero_sucursal = f"SUC{str(total + 1).zfill(2)}"

    cur.execute("""
        INSERT INTO terminales (id_terminal, id_empresa, numero_sucursal, ip_terminal, activa)
        VALUES (%s, %s, %s, %s, TRUE);
    """, (id_terminal, id_empresa, numero_sucursal, ip_terminal))

    conn.commit()
    conn.close()
    return True  # Nueva terminal registrada
   