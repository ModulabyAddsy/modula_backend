# app/controller/auth_controller.py
from fastapi import HTTPException, Request, status
from fastapi.responses import HTMLResponse

# Importaciones de modelos y servicios
from app.services.models import RegistroCuenta, LoginData, Token
from app.services import models
from app.services.stripe_service import crear_sesion_checkout_para_registro
from app.services.security import hash_contrasena, verificar_contrasena, crear_access_token
from app.services.cloud.setup_empresa_cloud import inicializar_empresa_nueva

#Importaciones para el endpoint de verificar la terminal
from sqlalchemy.orm import Session
from app.services.db import (
    buscar_terminal_activa_por_id,
    actualizar_y_verificar_suscripcion,
    actualizar_contadores_suscripcion,
    actualizar_ip_terminal
)
from app.services import security

# Importaciones de todas las funciones de base de datos necesarias para el flujo de autenticación
from app.services.db import (
    buscar_cuenta_addsy_por_correo,
    crear_cuenta_addsy,
    actualizar_cuenta_para_verificacion, # Usada por el webhook, pero es bueno tenerla aquí para claridad
    verificar_token_y_activar_cuenta,
    activar_suscripcion_y_terminal
)

# --- 1. REGISTRO Y PAGO ---
async def registrar_cuenta_y_crear_pago(data: RegistroCuenta):
    """
    Paso 1 del flujo: Valida el correo, pre-registra la cuenta en la BD 
    y crea una sesión de pago en Stripe.
    """
    cuenta_existente = buscar_cuenta_addsy_por_correo(data.correo)
    if cuenta_existente and cuenta_existente["estatus_cuenta"] == "verificada":
        raise HTTPException(status_code=400, detail="Este correo ya está en uso.")

    nuevo_usuario_data = data.dict()
    nuevo_usuario_data['contrasena_hash'] = hash_contrasena(data.contrasena)
    
    cuenta_id = crear_cuenta_addsy(nuevo_usuario_data)
    if not cuenta_id:
        raise HTTPException(status_code=500, detail="Error crítico al crear la cuenta en la base de datos.")

    print(f"➡️ Cuenta ID:{cuenta_id} pre-registrada. Procediendo a Stripe.")

    try:
        checkout_session = await crear_sesion_checkout_para_registro(
            nombre_completo=data.nombre_completo,
            correo=data.correo,
            id_terminal=data.id_terminal,
            aplica_prueba=True
        )
        return {"url_checkout": checkout_session.url}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al contactar con el servicio de pago: {e}")


# --- 2. INICIO DE SESIÓN ---
async def login_para_access_token(form_data: LoginData):
    """
    Autentica a un usuario con su correo y contraseña y, si es exitoso,
    devuelve un token de acceso JWT.
    """
    cuenta = buscar_cuenta_addsy_por_correo(form_data.correo)
    if not cuenta or not verificar_contrasena(form_data.contrasena, cuenta["contrasena_hash"]):
        raise HTTPException(status_code=401, detail="Correo o contraseña incorrectos")
        
    if cuenta["estatus_cuenta"] != "verificada":
        raise HTTPException(status_code=400, detail=f"La cuenta no ha sido verificada. Estatus: {cuenta['estatus_cuenta']}")
    
    access_token_data = {"sub": cuenta["correo"], "id_cuenta": cuenta["id"]}
    access_token = crear_access_token(data=access_token_data)
    return {"access_token": access_token, "token_type": "bearer"}


# --- 3. VERIFICACIÓN DE CUENTA ---
async def verificar_cuenta(request: Request):
    """
    Paso final del flujo: Se activa al hacer clic en el enlace del correo.
    Verifica el token, activa la cuenta, la suscripción, la terminal y la nube.
    """
    token = request.query_params.get("token")
    id_terminal = request.query_params.get("id_terminal")
    id_stripe_session = request.query_params.get("session_id")

    if not all([token, id_terminal, id_stripe_session]):
        return HTMLResponse("<h3>❌ Faltan parámetros en el enlace de verificación.</h3>", status_code=400)

    resultado = verificar_token_y_activar_cuenta(token)
    if isinstance(resultado, str):
        return HTMLResponse(f"<h3>❌ Error: {resultado.replace('_', ' ').capitalize()}.</h3>", status_code=400)
    if resultado is None:
        return HTMLResponse("<h3>❌ Ocurrió un error en el servidor al verificar tu cuenta.</h3>", status_code=500)

    cuenta_activada = resultado
    print(f"✅ Cuenta verificada para: {cuenta_activada['correo']}")
    
    exito_servicios = activar_suscripcion_y_terminal(
        id_cuenta=cuenta_activada['id'],
        id_terminal=id_terminal,
        id_stripe=id_stripe_session
    )
    if not exito_servicios:
        return HTMLResponse("<h3>✅ Cuenta verificada, pero falló la activación de servicios. Contacta a soporte.</h3>", status_code=500)

    exito_cloud = inicializar_empresa_nueva(cuenta_activada['id_empresa_addsy'])
    if not exito_cloud:
        return HTMLResponse("<h3>✅ Servicios activados, pero falló la creación en la nube. Contacta a soporte.</h3>", status_code=500)

    return HTMLResponse("<h2>✅ ¡Todo listo! Ya puedes volver al software e iniciar sesión.</h2>")

def verificar_terminal_activa_controller(
    request_data: models.TerminalVerificationRequest, client_ip: str
) -> models.TerminalVerificationResponse:
    """
    Controlador principal del arranque: verifica terminal, actualiza estados y contadores,
    y devuelve una sesión si todo es correcto.
    """
    # 1. Buscar la terminal (como antes)
    terminal_info = buscar_terminal_activa_por_id(request_data.id_terminal)
    if not terminal_info:
        raise HTTPException(status_code=404, detail="Terminal no registrada o inactiva.")

    id_cuenta = terminal_info['id_cuenta_addsy']

    # --- INICIO DE LA LÓGICA DE AUTOMATIZACIÓN ---

    # 2. Actualizar y Verificar la Suscripción
    suscripcion = actualizar_y_verificar_suscripcion(id_cuenta)
    if not suscripcion or suscripcion['estado_suscripcion'] not in ['activa', 'prueba_gratis']:
        estado = suscripcion['estado_suscripcion'] if suscripcion else 'desconocido'
        raise HTTPException(status_code=403, detail=f"Suscripción no válida. Estado: {estado}")

    # 3. Actualizar la IP y la última sincronización de la terminal
    actualizar_ip_terminal(request_data.id_terminal, client_ip)
    
    # 4. Actualizar los contadores de sucursales y terminales
    actualizar_contadores_suscripcion(id_cuenta)

    # --- FIN DE LA LÓGICA DE AUTOMATIZACIÓN ---
    
    # 5. Si todo está bien, generar y devolver la sesión
    access_token = security.crear_access_token(data={"sub": str(id_cuenta)})
    
    return models.TerminalVerificationResponse(
        access_token=access_token,
        id_empresa=terminal_info["id_cuenta_addsy"],
        nombre_empresa=terminal_info["nombre_empresa"],
        id_sucursal=terminal_info["id_sucursal"],
        nombre_sucursal=terminal_info["nombre_sucursal"],
        estado_suscripcion=suscripcion['estado_suscripcion']
    )