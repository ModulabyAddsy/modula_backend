from fastapi import APIRouter, HTTPException
from app.services.db import get_connection

router = APIRouter(prefix="/terminal", tags=["Terminales"])

@router.post("/registrar")
def registrar_terminal(id_terminal: str, id_empresa: str, ip_terminal: str):
    conn = get_connection()
    cur = conn.cursor()

    # 1. ¿Ya existe esta terminal?
    cur.execute("""
        SELECT * FROM terminales 
        WHERE id_terminal = %s AND id_empresa = %s;
    """, (id_terminal, id_empresa))
    terminal = cur.fetchone()
    
    if terminal:
        conn.close()
        return {"mensaje": "Terminal ya registrada", "datos": terminal}

    # 2. ¿Hay otra terminal de esta empresa con esta IP?
    cur.execute("""
        SELECT numero_sucursal FROM terminales 
        WHERE id_empresa = %s AND ip_terminal = %s LIMIT 1;
    """, (id_empresa, ip_terminal))
    sucursal_existente = cur.fetchone()

    if sucursal_existente:
        numero_sucursal = sucursal_existente["numero_sucursal"]
    else:
        # 3. Contar sucursales existentes para esta empresa
        cur.execute("""
            SELECT COUNT(DISTINCT numero_sucursal) FROM terminales WHERE id_empresa = %s;
        """, (id_empresa,))
        total = cur.fetchone()["count"]
        numero_sucursal = f"SUC{str(total + 1).zfill(2)}"

    # 4. Registrar nueva terminal
    cur.execute("""
        INSERT INTO terminales (id_terminal, id_empresa, numero_sucursal, ip_terminal, activa)
        VALUES (%s, %s, %s, %s, TRUE);
    """, (id_terminal, id_empresa, numero_sucursal, ip_terminal))

    conn.commit()
    conn.close()

    return {
        "mensaje": "✅ Terminal registrada correctamente",
        "id_terminal": id_terminal,
        "id_empresa": id_empresa,
        "numero_sucursal": numero_sucursal,
        "ip_detectada": ip_terminal
    }