# Importaciones de FastAPI y de sistema
from fastapi import HTTPException, Request
from fastapi.responses import HTMLResponse
from datetime import datetime

# Importaciones de nuestros modelos
from app.services.models import RegistroCuenta, LoginData, Token

# Importaciones de nuestros servicios y lógica de negocio
from app.services.terminal_service import crear_terminal_si_no_existe
from app.services.stripe_service import crear_sesion_checkout_para_registro
from app.services.db import (
    get_connection,
    obtener_usuario_por_correo,
    obtener_o_crear_id_empresa,
    registrar_usuario,
)
from app.services.mail import enviar_correo_verificacion
from app.services.cloud.setup_empresa_cloud import inicializar_empresa_nueva

# --- CORRECCIÓN DE IMPORTACIONES DE SEGURIDAD ---
# El token de verificación sigue en utils, pero la contraseña ahora está en security.
from app.services.utils import generar_token_verificacion
from app.services.security import hash_contrasena, verificar_contrasena, crear_access_token


async def registrar_cuenta_y_crear_pago(data: RegistroCuenta):
    # 1. Buscar si el correo ya está registrado y activo
    usuario = obtener_usuario_por_correo(data.correo)
    if usuario and usuario["estatus"] == "verificada":
        raise HTTPException(status_code=400, detail="Este correo ya está en uso.")

    # 2. Hashear la contraseña usando la función desde security.py
    contrasena_segura = hash_contrasena(data.contrasena)
    id_empresa = obtener_o_crear_id_empresa(data.nombre_empresa)

    # 3. Preparar los datos del nuevo usuario
    nuevo_usuario_data = {
        "nombre_completo": data.nombre_completo,
        "telefono": data.telefono,
        "fecha_nacimiento": data.fecha_nacimiento,
        "correo": data.correo,
        "correo_recuperacion": data.correo_recuperacion,
        "contrasena": contrasena_segura,
        "nombre_empresa": data.nombre_empresa,
        "id_empresa": id_empresa,
        "rfc": data.rfc,
        "token": None,
        "token_expira": None,
        "estatus": "pendiente_pago"
    }
    
    id_nuevo_usuario = registrar_usuario(nuevo_usuario_data)

    if id_nuevo_usuario is None:
        print("🔥🔥🔥 La inserción en la base de datos falló silenciosamente. No se obtuvo ID.")
        raise HTTPException(
            status_code=500, 
            detail="Error crítico: No se pudo guardar el registro de usuario en la base de datos."
        )
    
    print(f"➡️ Usuario pre-registrado con ID: {id_nuevo_usuario}. Procediendo a crear pago en Stripe.")

    # 4. Crear la sesión de pago en Stripe
    aplica_prueba = True 

    try:
        checkout_session = await crear_sesion_checkout_para_registro(
            nombre_completo=data.nombre_completo,
            correo=data.correo,
            id_terminal=data.id_terminal,
            aplica_prueba=aplica_prueba
        )
        return {"url_checkout": checkout_session.url}
    except Exception as e:
        print(f"🔥🔥🔥 Falló la creación de la sesión de Stripe: {e}")
        raise HTTPException(status_code=500, detail=f"Error al contactar con el servicio de pago: {e}")


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
            SET estatus = 'verificada', token = NULL, token_expira = NULL
            WHERE id = %s;
        """, (usuario["id"],))
        conn.commit()
        
        ip_terminal = request.client.host
        id_terminal = request.query_params.get("id_terminal")

        if id_terminal:
            terminal_nueva = crear_terminal_si_no_existe(id_terminal, usuario["id_empresa"], ip_terminal)
            if not terminal_nueva:
                print("⚠️ Terminal ya registrada. Desactivando prueba gratis.")
                cur.execute("UPDATE usuarios SET prueba_gratis = FALSE WHERE id = %s;", (usuario["id"],))
                conn.commit()
        
        conn.close()

        exito = inicializar_empresa_nueva(usuario["id_empresa"])
        if not exito:
            return HTMLResponse("<h3>✅ Cuenta verificada, pero falló la creación en la nube.</h3>", status_code=500)

        return HTMLResponse("<h2>✅ Cuenta verificada. ¡Ya puedes iniciar sesión!</h2>")
    
    except Exception as e:
        return HTMLResponse(f"<h3>❌ Error al verificar cuenta: {e}</h3>", status_code=500)


async def login_para_access_token(form_data: LoginData):
    usuario = obtener_usuario_por_correo(form_data.correo)

    if not usuario or not verificar_contrasena(form_data.contrasena, usuario["contrasena"]):
        raise HTTPException(
            status_code=401,
            detail="Correo o contraseña incorrectos",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if usuario["estatus"] != "verificada":
        raise HTTPException(
            status_code=400,
            detail="La cuenta no ha sido verificada. Revisa tu correo."
        )

    access_token_data = {
        "sub": usuario["correo"],
        "id_empresa": usuario["id_empresa"]
    }
    access_token = crear_access_token(data=access_token_data)

    return {"access_token": access_token, "token_type": "bearer"}
