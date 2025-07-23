# app/controller/auth_controller.py
from fastapi import HTTPException, Request
from fastapi.responses import HTMLResponse
from app.services.models import RegistroCuenta, LoginData, Token
from app.services.stripe_service import crear_sesion_checkout_para_registro
from app.services.security import hash_contrasena, verificar_contrasena, crear_access_token
from app.services.cloud.setup_empresa_cloud import inicializar_empresa_nueva
from app.services.db import (
    buscar_cuenta_addsy_por_correo,
    crear_cuenta_addsy, # 👉 Nueva función simplificada
    verificar_token_y_activar_cuenta,
    activar_suscripcion_y_terminal
)

async def registrar_cuenta_y_crear_pago(data: RegistroCuenta):
    cuenta_existente = buscar_cuenta_addsy_por_correo(data.correo)
    if cuenta_existente and cuenta_existente["estatus_cuenta"] == "verificada":
        raise HTTPException(status_code=400, detail="Este correo ya está en uso.")

    nuevo_usuario_data = data.dict()
    nuevo_usuario_data['contrasena_hash'] = hash_contrasena(data.contrasena)
    
    # 👉 Lógica de creación simplificada
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

async def login_para_access_token(form_data: LoginData):
    cuenta = buscar_cuenta_addsy_por_correo(form_data.correo)
    if not cuenta or not verificar_contrasena(form_data.contrasena, cuenta["contrasena_hash"]):
        raise HTTPException(status_code=401, detail="Correo o contraseña incorrectos")
    if cuenta["estatus_cuenta"] != "verificada":
        raise HTTPException(status_code=400, detail=f"La cuenta no ha sido verificada. Estatus: {cuenta['estatus_cuenta']}")
    
    # 👉 El payload del token ya no necesita id_empresa
    access_token_data = {"sub": cuenta["correo"], "id_cuenta": cuenta["id"]}
    access_token = crear_access_token(data=access_token_data)
    return {"access_token": access_token, "token_type": "bearer"}

async def verificar_cuenta(request: Request):
    token = request.query_params.get("token")
    id_terminal = request.query_params.get("id_terminal")
    id_stripe_session = request.query_params.get("session_id")

    if not all([token, id_terminal, id_stripe_session]):
        return HTMLResponse("<h3>❌ Faltan parámetros.</h3>", status_code=400)

    resultado = verificar_token_y_activar_cuenta(token)
    if isinstance(resultado, str):
        return HTMLResponse(f"<h3>❌ Error: {resultado.replace('_', ' ').capitalize()}.</h3>", status_code=400)
    if resultado is None:
        return HTMLResponse("<h3>❌ Error en el servidor.</h3>", status_code=500)

    cuenta_activada = resultado
    print(f"✅ Cuenta verificada para: {cuenta_activada['correo']}")
    
    # 👉 Se pasa el id de la cuenta (que ahora es el id de la empresa)
    exito_servicios = activar_suscripcion_y_terminal(
        id_cuenta=cuenta_activada['id'],
        id_terminal=id_terminal,
        id_stripe=id_stripe_session
    )
    if not exito_servicios:
        return HTMLResponse("<h3>✅ Cuenta verificada, pero falló la activación de servicios.</h3>", status_code=500)

    # 👉 Se usa el id_empresa_addsy de la cuenta para la carpeta
    exito_cloud = inicializar_empresa_nueva(cuenta_activada['id_empresa_addsy'])
    if not exito_cloud:
        return HTMLResponse("<h3>✅ Servicios activados, pero falló la creación en la nube.</h3>", status_code=500)

    return HTMLResponse("<h2>✅ ¡Todo listo! Ya puedes iniciar sesión.</h2>")