# app/controller/auth_controller.py
from fastapi import HTTPException, Request
from fastapi.responses import HTMLResponse
from datetime import datetime

# Importaciones de nuestros modelos y servicios
from app.services.models import RegistroCuenta, LoginData, Token
from app.services.stripe_service import crear_sesion_checkout_para_registro
from app.services.security import hash_contrasena, verificar_contrasena, crear_access_token
from app.services.utils import generar_token_verificacion
from app.services.mail import enviar_correo_verificacion
from app.services.cloud.setup_empresa_cloud import inicializar_empresa_nueva

# Importamos las NUEVAS funciones de la base de datos
from app.services.db import (
    buscar_usuario_admin_por_correo,
    crear_empresa_y_usuario_inicial,
    actualizar_estatus_admin_para_verificacion,
    verificar_token_y_activar_admin
)


async def registrar_cuenta_y_crear_pago(data: RegistroCuenta):
    """Flujo de registro actualizado para la nueva arquitectura de BD."""
    usuario = buscar_usuario_admin_por_correo(data.correo)
    if usuario and usuario["estatus"] == "verificada":
        raise HTTPException(status_code=400, detail="Este correo ya está en uso.")

    contrasena_segura = hash_contrasena(data.contrasena)
    
    nuevo_usuario_data = data.dict()
    nuevo_usuario_data['contrasena_hash'] = contrasena_segura
    
    empresa_id, usuario_id = crear_empresa_y_usuario_inicial(nuevo_usuario_data)

    if not empresa_id or not usuario_id:
        raise HTTPException(status_code=500, detail="Error crítico al crear el registro en la base de datos.")

    print(f"➡️ Empresa ID:{empresa_id} y Usuario ID:{usuario_id} pre-registrados. Procediendo a Stripe.")

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
        raise HTTPException(status_code=500, detail=f"Error al contactar con el servicio de pago: {e}")


async def login_para_access_token(form_data: LoginData):
    """Autentica a un administrador y devuelve un token JWT."""
    usuario = buscar_usuario_admin_por_correo(form_data.correo)

    if not usuario or not verificar_contrasena(form_data.contrasena, usuario["contrasena_hash"]):
        raise HTTPException(status_code=401, detail="Correo o contraseña incorrectos")

    if usuario["estatus"] != "verificada":
        raise HTTPException(status_code=400, detail="La cuenta no ha sido verificada.")

    access_token_data = {
        "sub": usuario["correo"],
        "id_usuario_admin": usuario["id"],
        "id_empresa": usuario["id_empresa"],
        "id_empresa_addsy": usuario["id_empresa_addsy"]
    }
    access_token = crear_access_token(data=access_token_data)

    return {"access_token": access_token, "token_type": "bearer"}


async def verificar_cuenta(request: Request):
    """Verifica la cuenta del administrador usando el token del correo."""
    token = request.query_params.get("token")
    if not token:
        return HTMLResponse("<h3>❌ Token inválido</h3>", status_code=400)

    resultado = verificar_token_y_activar_admin(token)

    if resultado == "invalid_token":
        return HTMLResponse("<h3>❌ Token no válido o ya ha sido utilizado.</h3>", status_code=404)
    if resultado == "expired_token":
        return HTMLResponse("<h3>⚠️ El token ha expirado. Por favor, intenta registrarte de nuevo.</h3>", status_code=400)
    if resultado is None:
        return HTMLResponse("<h3>❌ Ocurrió un error en el servidor al verificar tu cuenta.</h3>", status_code=500)

    # Si llegamos aquí, 'resultado' es el diccionario del usuario activado
    usuario_activado = resultado
    print(f"✅ Cuenta verificada para el usuario: {usuario_activado['correo']}")
    
    # === CREAR ESTRUCTURA EN LA NUBE ===
    # Usamos el id_empresa_addsy que es el nombre de la carpeta
    id_empresa_carpeta = buscar_usuario_admin_por_correo(usuario_activado['correo'])['id_empresa_addsy']
    exito_cloud = inicializar_empresa_nueva(id_empresa_carpeta)
    if not exito_cloud:
        return HTMLResponse("<h3>✅ Cuenta verificada, pero falló la creación de la estructura en la nube. Contacta a soporte.</h3>", status_code=500)

    return HTMLResponse("<h2>✅ ¡Cuenta verificada! Ya puedes iniciar sesión en el software Modula.</h2>")