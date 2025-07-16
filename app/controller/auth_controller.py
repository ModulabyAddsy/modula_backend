from fastapi import HTTPException, Request
from fastapi.responses import HTMLResponse
from datetime import datetime
from app.services.db import (
    get_connection,
    obtener_usuario_por_correo,
    obtener_o_crear_id_empresa,
    registrar_usuario,
)
from app.services.utils import hash_contrasena, generar_token_verificacion
from app.services.mail import enviar_correo_verificacion
from app.services.cloud.setup_empresa_cloud import inicializar_empresa_nueva

async def registrar_cuenta(data):
    usuario = obtener_usuario_por_correo(data.correo)
    if usuario:
        if usuario["estatus"] == "verificada":
            raise HTTPException(400, "Este correo ya está verificado.")
        raise HTTPException(400, "Este correo ya fue registrado pero no verificado.")

    id_empresa = obtener_o_crear_id_empresa(data.nombre_empresa)
    token, token_expira = generar_token_verificacion()
    contrasena_segura = hash_contrasena(data.contrasena)

    nuevo_usuario = {
        "nombre_completo": data.nombre_completo,
        "telefono": data.telefono,
        "fecha_nacimiento": data.fecha_nacimiento,
        "correo": data.correo,
        "correo_recuperacion": data.correo_recuperacion,
        "contrasena": contrasena_segura,
        "nombre_empresa": data.nombre_empresa,
        "id_empresa": id_empresa,
        "rfc": data.rfc,
        "token": token,
        "token_expira": token_expira,
    }
    registrar_usuario(nuevo_usuario)
    enviar_correo_verificacion(data.correo, data.nombre_completo, token)

    return {
        "mensaje": "Cuenta registrada correctamente. Revisa tu correo.",
        "id_empresa": id_empresa
    }

async def verificar_cuenta(request: Request):
    token = request.query_params.get("token")
    if not token:
        return HTMLResponse("<h3>❌ Token inválido</h3>", status_code=400)

    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM usuarios WHERE token = %s;", (token,))
        usuario = cur.fetchone()

        if not usuario:
            return HTMLResponse("<h3>❌ Token no válido</h3>", status_code=404)

        if usuario["token_expira"] < datetime.utcnow():
            return HTMLResponse("<h3>⚠️ Token expirado.</h3>", status_code=403)

        cur.execute("""
            UPDATE usuarios
            SET estatus = 'verificada',
                token = NULL,
                token_expira = NULL
            WHERE id = %s;
        """, (usuario["id"],))
        conn.commit()
        conn.close()

        exito = inicializar_empresa_nueva(usuario["id_empresa"])
        if not exito:
            return HTMLResponse("<h3>✅ Cuenta verificada, pero falló la creación en la nube.</h3>", status_code=500)

        return HTMLResponse("<h2>✅ Cuenta verificada. ¡Ya puedes iniciar sesión!</h2>")
    
    except Exception as e:
        return HTMLResponse(f"<h3>❌ Error al verificar cuenta: {e}</h3>", status_code=500)