# app/controller/auth_controller.py
from fastapi import HTTPException, Request
from fastapi.responses import HTMLResponse

# Importaciones de nuestros modelos y servicios
from app.services.models import RegistroCuenta, LoginData, Token
from app.services.stripe_service import crear_sesion_checkout_para_registro
from app.services.security import hash_contrasena, verificar_contrasena, crear_access_token
from app.services.cloud.setup_empresa_cloud import inicializar_empresa_nueva

# 👉 Importamos las NUEVAS funciones de la base de datos
from app.services.db import (
    buscar_cuenta_addsy_por_correo,
    crear_recursos_iniciales,
    verificar_token_y_activar_cuenta,
    activar_suscripcion_y_terminal
)


async def registrar_cuenta_y_crear_pago(data: RegistroCuenta):
    """Flujo de registro para la nueva arquitectura: Pre-registra y crea sesión de pago."""
    cuenta = buscar_cuenta_addsy_por_correo(data.correo)
    if cuenta and cuenta["estatus_cuenta"] == "verificada":
        raise HTTPException(status_code=400, detail="Este correo ya está en uso.")

    # Hashear contraseña y preparar datos
    nuevo_usuario_data = data.dict()
    nuevo_usuario_data['contrasena_hash'] = hash_contrasena(data.contrasena)
    
    # Pre-registrar la empresa y la cuenta addsy
    empresa_id, cuenta_id = crear_recursos_iniciales(nuevo_usuario_data)
    if not empresa_id or not cuenta_id:
        raise HTTPException(status_code=500, detail="Error crítico al crear el registro en la base de datos.")

    print(f"➡️ Cuenta ID:{cuenta_id} pre-registrada. Procediendo a Stripe.")

    # Crear sesión de pago en Stripe
    try:
        checkout_session = await crear_sesion_checkout_para_registro(
            nombre_completo=data.nombre_completo,
            correo=data.correo,
            id_terminal=data.id_terminal,
            aplica_prueba=True # Siempre aplica prueba en el registro inicial
        )
        return {"url_checkout": checkout_session.url}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al contactar con el servicio de pago: {e}")


async def login_para_access_token(form_data: LoginData):
    """Autentica a un usuario y devuelve un token JWT."""
    cuenta = buscar_cuenta_addsy_por_correo(form_data.correo)

    if not cuenta or not verificar_contrasena(form_data.contrasena, cuenta["contrasena_hash"]):
        raise HTTPException(status_code=401, detail="Correo o contraseña incorrectos")

    if cuenta["estatus_cuenta"] != "verificada":
        raise HTTPException(status_code=400, detail=f"La cuenta no ha sido verificada. Estatus actual: {cuenta['estatus_cuenta']}")

    # Datos para el token JWT
    access_token_data = {
        "sub": cuenta["correo"],
        "id_cuenta": cuenta["id"],
        "id_empresa": cuenta["id_empresa"]
    }
    access_token = crear_access_token(data=access_token_data)

    return {"access_token": access_token, "token_type": "bearer"}


async def verificar_cuenta(request: Request):
    """Verifica la cuenta del usuario, activa servicios y crea la estructura en la nube."""
    token = request.query_params.get("token")
    id_terminal = request.query_params.get("id_terminal") # Capturamos de la URL
    id_stripe_session = request.query_params.get("session_id") # Capturamos de la URL

    if not all([token, id_terminal, id_stripe_session]):
        return HTMLResponse("<h3>❌ Faltan parámetros en el enlace de verificación.</h3>", status_code=400)

    # 1. Verificar el token y activar la cuenta en 'cuentas_addsy'
    resultado = verificar_token_y_activar_cuenta(token)
    if isinstance(resultado, str): # Maneja los casos de error "invalid_token" o "expired_token"
        return HTMLResponse(f"<h3>❌ Error: {resultado.replace('_', ' ').capitalize()}.</h3>", status_code=400)
    if resultado is None:
        return HTMLResponse("<h3>❌ Ocurrió un error en el servidor al verificar tu cuenta.</h3>", status_code=500)

    cuenta_activada = resultado
    print(f"✅ Cuenta verificada para: {cuenta_activada['correo']}")
    
    # 2. 👉 Activar la suscripción, sucursal y terminal
    exito_servicios = activar_suscripcion_y_terminal(
        id_cuenta=cuenta_activada['id'],
        id_empresa=cuenta_activada['id_empresa'],
        id_terminal=id_terminal,
        id_stripe=id_stripe_session # Guardamos el ID de la sesión de Stripe
    )
    if not exito_servicios:
        return HTMLResponse("<h3>✅ Cuenta verificada, pero falló la activación de la suscripción. Contacta a soporte.</h3>", status_code=500)

    # 3. Crear estructura en la nube
    exito_cloud = inicializar_empresa_nueva(str(cuenta_activada['id_empresa']))
    if not exito_cloud:
        return HTMLResponse("<h3>✅ Cuenta y servicios activados, pero falló la creación en la nube. Contacta a soporte.</h3>", status_code=500)

    return HTMLResponse("<h2>✅ ¡Todo listo! Ya puedes iniciar sesión en el software Modula.</h2>")
