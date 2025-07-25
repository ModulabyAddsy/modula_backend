# app/controller/auth_controller.py
from fastapi import HTTPException, Request, status
from fastapi.responses import HTMLResponse

# Importaciones de modelos y servicios
from app.services.models import RegistroCuenta, LoginData, Token
from app.services import models
from app.services.stripe_service import crear_sesion_checkout_para_registro
from app.services.security import hash_contrasena, verificar_contrasena, crear_access_token
# --- CAMBIO 1: Importar las nuevas funciones de la nube ---
from app.services.cloud.setup_empresa_cloud import (
    crear_estructura_base_empresa, 
    crear_estructura_sucursal
)

# Importaciones para el endpoint de verificar la terminal
from app.services.db import (
    buscar_cuenta_addsy_por_correo,
    crear_cuenta_addsy,
    verificar_token_y_activar_cuenta,
    activar_suscripcion_y_terminal,
    actualizar_ip_terminal,
    buscar_terminal_activa_por_id,
    actualizar_y_verificar_suscripcion,
    actualizar_contadores_suscripcion,
    get_terminales_por_cuenta # <-- ESTA ES LA FUNCIÓN QUE FALTABA IMPORTAR
)
from app.services import security

#COMENTARIO PARA SUBIR A GITHUB

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
async def login_para_access_token(form_data: LoginData, client_ip: str):
    """
    Autentica, actualiza la IP de la primera terminal encontrada y devuelve un token.
    """
    cuenta = buscar_cuenta_addsy_por_correo(form_data.correo)
    if not cuenta or not verificar_contrasena(form_data.contrasena, cuenta["contrasena_hash"]):
        raise HTTPException(status_code=401, detail="Correo o contraseña incorrectos")
        
    if cuenta["estatus_cuenta"] != "verificada":
        raise HTTPException(status_code=400, detail=f"La cuenta no ha sido verificada. Estatus: {cuenta['estatus_cuenta']}")
    
    # NOTA: Esta lógica asume que se quiere actualizar la IP de la primera terminal
    # de la cuenta. Funciona para el caso de un solo terminal.
    terminales = get_terminales_por_cuenta(cuenta["id"])
    id_terminal_respuesta = None
    if terminales:
        id_terminal_a_actualizar = terminales[0]['id_terminal']
        id_terminal_respuesta = id_terminal_a_actualizar
        actualizar_ip_terminal(id_terminal_a_actualizar, client_ip)
        print(f"IP actualizada para la terminal {id_terminal_a_actualizar} durante el login.")
    
    access_token_data = {
        "sub": cuenta["correo"], 
        "id": cuenta["id"],
        "id_empresa_addsy": cuenta["id_empresa_addsy"]
    }
    access_token = crear_access_token(data=access_token_data)
    
    # Se añade el id_terminal al response del login, para que el cliente lo guarde
    # en su primer inicio de sesión.
    return {
        "access_token": access_token, 
        "token_type": "bearer", 
        "id_terminal": id_terminal_respuesta
    }


# --- 3. VERIFICACIÓN DE CUENTA (LÓGICA ACTUALIZADA) ---
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
    id_empresa_addsy = cuenta_activada['id_empresa_addsy']
    print(f"✅ Cuenta verificada para: {cuenta_activada['correo']} ({id_empresa_addsy})")
    
    # --- CAMBIO 2: Actualizar la llamada a la función de DB para pasar el id_empresa_addsy ---
    exito_servicios, ruta_cloud_creada = activar_suscripcion_y_terminal(
        id_cuenta=cuenta_activada['id'],
        id_empresa_addsy=id_empresa_addsy, # Nuevo argumento
        id_terminal_uuid=id_terminal,
        id_stripe=id_stripe_session
    )
    # --- CAMBIO 3: Capturar los dos valores de retorno y verificar ---
    if not exito_servicios:
        return HTMLResponse("<h3>✅ Cuenta verificada, pero falló la activación de servicios en la BD. Contacta a soporte.</h3>", status_code=500)

    # --- CAMBIO 4: Reemplazar la antigua llamada a la nube por las dos nuevas funciones ---
    # Paso 4.1: Crear la estructura base de la empresa
    if not crear_estructura_base_empresa(id_empresa_addsy):
        return HTMLResponse("<h3>✅ Servicios activados, pero falló la creación de la carpeta principal en la nube. Contacta a soporte.</h3>", status_code=500)

    # Paso 4.2: Crear la estructura específica de la primera sucursal
    if not crear_estructura_sucursal(ruta_cloud_creada):
        return HTMLResponse("<h3>✅ Carpeta principal creada, pero falló la creación de la carpeta de sucursal. Contacta a soporte.</h3>", status_code=500)

    actualizar_contadores_suscripcion(cuenta_activada['id'])
    print(f"Contadores actualizados para la cuenta ID: {cuenta_activada['id']}")

    return HTMLResponse("<h2>✅ ¡Todo listo! Tu cuenta, sucursal y espacio en la nube han sido configurados. Ya puedes volver al software e iniciar sesión.</h2>")

def verificar_terminal_activa_controller(
    request_data: models.TerminalVerificationRequest, client_ip: str
) -> models.TerminalVerificationResponse:
    
    terminal_info = buscar_terminal_activa_por_id(request_data.id_terminal)
    if not terminal_info:
        raise HTTPException(status_code=404, detail="Terminal no registrada o inactiva.")

    id_cuenta = terminal_info['id_cuenta_addsy']

    suscripcion = actualizar_y_verificar_suscripcion(id_cuenta)
    if not suscripcion or suscripcion['estado_suscripcion'] not in ['activa', 'prueba_gratis']:
        estado = suscripcion['estado_suscripcion'] if suscripcion else 'desconocido'
        raise HTTPException(status_code=403, detail=f"Suscripción no válida. Estado: {estado}")

    actualizar_ip_terminal(request_data.id_terminal, client_ip)
    
    actualizar_contadores_suscripcion(id_cuenta)
    
    # --- CORRECCIÓN CRÍTICA: Añadir id_empresa_addsy al token ---
    access_token_data = {
        "sub": terminal_info["correo"], # Usar el correo como 'sub', igual que en el login
        "id": id_cuenta,
        "id_empresa_addsy": terminal_info["id_empresa_addsy"]
    }
    access_token = security.crear_access_token(data=access_token_data)
    
    return models.TerminalVerificationResponse(
        access_token=access_token,
        id_empresa=terminal_info["id_empresa_addsy"],
        nombre_empresa=terminal_info["nombre_empresa"],
        id_sucursal=terminal_info["id_sucursal"],
        nombre_sucursal=terminal_info["nombre_sucursal"],
        estado_suscripcion=suscripcion['estado_suscripcion']
    )
