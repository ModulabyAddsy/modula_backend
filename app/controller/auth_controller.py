    # app/controller/auth_controller.py
from fastapi import HTTPException, Request, status
from fastapi.responses import HTMLResponse

# Importaciones de modelos y servicios
from app.services.models import RegistroCuenta, LoginData, Token
from app.services import models
from app.services.stripe_service import crear_sesion_checkout_para_registro, crear_sesion_portal_cliente, get_subscription_status_from_stripe
from app.services.security import hash_contrasena, verificar_contrasena, crear_access_token
from app.services.employee_service import anadir_primer_administrador_general,obtener_info_empleado
# --- CAMBIO 1: Importar las nuevas funciones de la nube ---
from app.services.cloud.setup_empresa_cloud import (
    crear_estructura_base_empresa, 
    crear_estructura_sucursal,
    descargar_archivo_db
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
    get_terminales_por_cuenta, # <-- ESTA ES LA FUNCIÓN QUE FALTABA IMPORTA
    buscar_sucursal_por_ip_en_otra_terminal, # <--- NUEVA
    get_sucursales_por_cuenta, get_sucursales_por_cuenta,
    buscar_cuenta_por_claim_token,guardar_token_reseteo,
    resetear_contrasena_con_token, buscar_cuenta_addsy_por_id   ,
    actualizar_suscripcion_tras_pago    ,
    get_redes_autorizadas_por_sucursal
)
from app.services import security
from app.services import employee_service
from app.services.employee_service import anadir_primer_administrador
from app.services.cloud.setup_empresa_cloud import subir_archivo_db
from app.services.utils import generar_contrasena_temporal, generar_token_verificacion
from app.services.mail import enviar_correo_credenciales, enviar_correo_reseteo

#COMENTARIO PARA SUBIR A GITHUB

# --- 1. REGISTRO Y PAGO ---
async def registrar_cuenta_y_crear_pago(data: RegistroCuenta):
    """
    Paso 1 del flujo: Valida el correo, pre-registra la cuenta en la BD
    y crea una sesión de pago en Stripe.
    """

    # Estandarizamos el correo a minúsculas para buscar y guardar.
    correo_lower = data.correo.lower().strip()

    cuenta_existente = buscar_cuenta_addsy_por_correo(correo_lower)
    if cuenta_existente and cuenta_existente["estatus_cuenta"] == "verificada":
        raise HTTPException(status_code=400, detail="Este correo ya está en uso.")

    nuevo_usuario_data = data.dict()

    # ✨ CAMBIO 1: Sobrescribimos el correo en los datos a guardar
    # con su versión en minúsculas. Esto asegura que en la BD siempre esté estandarizado.
    nuevo_usuario_data['correo'] = correo_lower

    nuevo_usuario_data['contrasena_hash'] = hash_contrasena(data.contrasena)

    cuenta_id = crear_cuenta_addsy(nuevo_usuario_data)
    if not cuenta_id:
        raise HTTPException(status_code=500, detail="Error crítico al crear la cuenta en la base de datos.")

    print(f"➡️ Cuenta ID:{cuenta_id} pre-registrada. Procediendo a Stripe.")

    try:
        checkout_session = await crear_sesion_checkout_para_registro(
            nombre_completo=data.nombre_completo,
            # ✨ CAMBIO 2: Enviamos a Stripe el correo ya estandarizado en minúsculas.
            correo=correo_lower,
            id_terminal=data.id_terminal,
            aplica_prueba=True
        )
        return {"url_checkout": checkout_session.url}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al contactar con el servicio de pago: {e}")
# --- 2. INICIO DE SESIÓN ---
async def login_para_access_token(form_data: LoginData, client_ip: str) -> Token:
    """
    Verifica las credenciales de un usuario y, si son correctas,
    devuelve un token de acceso JWT.
    """
    correo_lower = form_data.correo.lower().strip()
    cuenta = buscar_cuenta_addsy_por_correo(correo_lower)

    # --- PASO 1: Validar si el usuario existe ---
    # Si la cuenta no se encuentra, lanzamos un error 401 de inmediato.
    # Es una buena práctica de seguridad no revelar si el correo existe o no.
    if not cuenta:
        print(f"INFO - Intento de login fallido (correo no encontrado): {correo_lower}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Correo o contraseña incorrectos",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # --- PASO 2: Validar la contraseña ---
    # El usuario existe, ahora comparamos el hash de la contraseña de la BD
    # con la contraseña que nos enviaron en el formulario.
    contrasena_limpia = form_data.contrasena.strip()
    es_valida = verificar_contrasena(contrasena_limpia, cuenta["contrasena_hash"])

    if not es_valida:
        print(f"INFO - Intento de login fallido (contraseña incorrecta): {correo_lower}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Correo o contraseña incorrectos",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # --- PASO 3: Generar y devolver el token (Caso de éxito) ---
    # Si llegamos a este punto, las credenciales son correctas.
    print(f"INFO - Login exitoso para el usuario: {correo_lower}")

    # Preparamos los datos que irán dentro del token (payload)
    access_token_data = {
        "sub": cuenta["correo"],
        "id_cuenta_addsy": cuenta["id"],
        "id_empresa_addsy": cuenta["id_empresa_addsy"]
        # Puedes añadir más datos útiles aquí si lo necesitas en el futuro
    }

    # Creamos el token JWT
    access_token = crear_access_token(data=access_token_data)

    # Devolvemos el token en el formato esperado por el cliente
    return Token(access_token=access_token, token_type="bearer")

# --- 3. VERIFICACIÓN DE CUENTA (LÓGICA ACTUALIZADA) ---

async def verificar_cuenta(request: Request):
    """
    Paso final del flujo: Activa todos los servicios y crea el primer usuario administrador.
    """
    token = request.query_params.get("token")
    id_terminal = request.query_params.get("id_terminal")
    id_stripe_session = request.query_params.get("session_id")

    if not all([token, id_terminal, id_stripe_session]):
        return HTMLResponse("<h3>❌ Faltan parámetros en el enlace de verificación.</h3>", status_code=400)

    cuenta_activada = verificar_token_y_activar_cuenta(token)
    if isinstance(cuenta_activada, str):
        return HTMLResponse(f"<h3>❌ Error: {cuenta_activada.replace('_', ' ').capitalize()}.</h3>", status_code=400)
    if cuenta_activada is None:
        return HTMLResponse("<h3>❌ Ocurrió un error en el servidor al verificar tu cuenta.</h3>", status_code=500)

    id_empresa_addsy = cuenta_activada['id_empresa_addsy']
    print(f"✅ Cuenta verificada para: {cuenta_activada['correo']} ({id_empresa_addsy})")
    
    # Activamos los servicios y obtenemos el ID de la primera sucursal
    resultado_activacion = activar_suscripcion_y_terminal(
        id_cuenta=cuenta_activada['id'], id_empresa_addsy=id_empresa_addsy,
        id_terminal_uuid=id_terminal, id_stripe=id_stripe_session
    )
    if not resultado_activacion.get('exito'):
        return HTMLResponse("<h3>✅ Cuenta verificada, pero falló la activación de servicios en la BD.</h3>", status_code=500)

    # Creamos las carpetas base en la nube
    if not crear_estructura_base_empresa(id_empresa_addsy):
        return HTMLResponse("<h3>✅ Falló la creación de la carpeta principal en la nube.</h3>", status_code=500)

    if not crear_estructura_sucursal(resultado_activacion['ruta_cloud']):
        return HTMLResponse("<h3>✅ Falló la creación de la carpeta de sucursal.</h3>", status_code=500)

    # ✅ --- INICIA LA NUEVA LÓGICA DE CREACIÓN DE EMPLEADO ---
    try:
        # A. Definir la ruta del archivo que 'crear_estructura_base_empresa' ya copió
        ruta_db_usuarios = f"{id_empresa_addsy}/databases_generales/usuarios.sqlite"
        
        # B. Descargar la plantilla recién copiada (y vacía)
        db_bytes_original = descargar_archivo_db(ruta_db_usuarios)
        if not db_bytes_original: raise Exception("No se encontró la DB de usuarios plantilla en la nube.")

        # C. Preparar datos y generar credenciales
        datos_propietario = {
            **cuenta_activada, 
            'id_primera_sucursal': resultado_activacion['id_sucursal']
        }
        # Aseguramos que el username del primer admin sea el numero de cuenta
        username_empleado = str(cuenta_activada['id'])
        contrasena_temporal = generar_contrasena_temporal()
        
        # D. Añadir el primer admin al archivo descargado
        # Usamos la nueva función del servicio
        db_bytes_modificado = anadir_primer_administrador_general(
            db_bytes_original, datos_propietario, username_empleado, contrasena_temporal,datos_propietario['nombre_completo']
        )
        if not db_bytes_modificado: raise Exception("No se pudo insertar el admin en el archivo DB.")
        
        # E. Volver a subir el archivo ya con los datos del admin, sobrescribiendo el anterior
        if not subir_archivo_db(ruta_db_usuarios, db_bytes_modificado):
            raise Exception("No se pudo re-subir la DB de empleados a la nube.")
        
        # F. Enviar correo con credenciales
        enviar_correo_credenciales(
            destinatario=cuenta_activada['correo'], nombre_usuario=cuenta_activada['nombre_completo'],
            username_empleado=username_empleado, contrasena_temporal=contrasena_temporal
        )
    except Exception as e:
        # Se captura cualquier error en el proceso y se notifica al usuario sin romper el flujo principal
        return HTMLResponse(f"<h3>✅ Tu cuenta está activa, pero hubo un error al generar tus credenciales: {e}.</h3>", status_code=500)
    
    actualizar_contadores_suscripcion(cuenta_activada['id'])
    
    return HTMLResponse("<h2>✅ ¡Todo listo! Tu cuenta ha sido configurada. Revisa tu correo para obtener tus credenciales de acceso.</h2>")

def verificar_y_autorizar_terminal(request_data: models.TerminalVerificationRequest, client_ip: str):
    """
    Función UNIFICADA que se encarga de todo el proceso de verificación:
    1. Valida la ubicación de la terminal usando la nueva lógica de Red Local (LAN).
    2. Si la red es válida, verifica el estado de la suscripción (activa, vencida, etc.).
    3. Devuelve la respuesta apropiada (token de acceso, error de ubicación o error de suscripción).
    """
    # --- ETAPA 1: VERIFICACIÓN DE RED LOCAL (EL NUEVO SISTEMA) ---
    id_terminal = request_data.id_terminal
    mac_gateway_actual = request_data.gateway_mac
    ssid_actual = request_data.ssid
    
    terminal = buscar_terminal_activa_por_id(id_terminal)
    if not terminal:
        raise HTTPException(status_code=404, detail="Terminal no encontrada o inactiva.")
    
    id_sucursal_asignada = terminal['id_sucursal']
    id_cuenta = terminal['id_cuenta_addsy']
    
    redes_ancladas = get_redes_autorizadas_por_sucursal(id_sucursal_asignada)
    
    coincidencia_encontrada = False
    if redes_ancladas:
        for red in redes_ancladas:
            if mac_gateway_actual and red['gateway_mac'] == mac_gateway_actual:
                coincidencia_encontrada = True
                break
            if ssid_actual and red['ssid'] == ssid_actual:
                coincidencia_encontrada = True
                break
    
    if not coincidencia_encontrada:
        # La red no es de confianza. Devolvemos el error de ubicación para que un admin la ancle.
        print(f"⚠️ Conflicto de ubicación para terminal {id_terminal}. La red local no coincide.")
        sucursales = get_sucursales_por_cuenta(id_cuenta)
        return {
            "status": "location_mismatch",
            "message": "La red actual no está autorizada para esta sucursal.",
            "sucursales_existentes": [models.SucursalInfo(**s) for s in sucursales]
        }

    # --- ETAPA 2: VERIFICACIÓN DE SUSCRIPCIÓN (SI LA RED ES VÁLIDA) ---
    print(f"✅ Red local verificada para terminal {id_terminal}. Procediendo a verificar suscripción.")
    suscripcion = actualizar_y_verificar_suscripcion(id_cuenta)
    
    if suscripcion and suscripcion['estado_suscripcion'] in ['activa', 'prueba_gratis']:
        # ¡ÉXITO TOTAL! La red es correcta y la suscripción está activa.
        print(f"✅ Suscripción activa para cuenta {id_cuenta}. Generando token.")
        
        # Actualizamos la IP como dato de referencia y generamos el token
        actualizar_ip_terminal(id_terminal, client_ip)
        actualizar_contadores_suscripcion(id_cuenta)

        token_data = {
            "sub": terminal["correo"],
            "id_cuenta_addsy": id_cuenta,
            "id_sucursal": id_sucursal_asignada,
            "id_empresa_addsy": terminal["id_empresa_addsy"]
        }
        access_token = security.crear_access_token(data=token_data)
        
        return models.TerminalVerificationResponse(
            status="ok",
            access_token=access_token,
            id_empresa=terminal["id_empresa_addsy"],
            nombre_empresa=terminal["nombre_empresa"],
            id_sucursal=terminal["id_sucursal"],
            nombre_sucursal=terminal["nombre_sucursal"],
            estado_suscripcion=suscripcion['estado_suscripcion']
        )
    else:
        # La red es correcta, pero la suscripción está vencida.
        print(f"🚨 Suscripción vencida para cuenta {id_cuenta}. Generando portal de pago.")
        cuenta_info = buscar_cuenta_addsy_por_id(id_cuenta)
        stripe_customer_id = cuenta_info.get("id_cliente_stripe")

        if not stripe_customer_id:
            raise HTTPException(status_code=403, detail="Suscripción vencida y no se encontró ID de cliente para el pago.")

        url_portal_pago = crear_sesion_portal_cliente(stripe_customer_id)

        return {
            "status": "subscription_expired",
            "message": "Tu suscripción ha vencido. Por favor, actualiza tu método de pago.",
            "payment_url": url_portal_pago
        }
            
async def check_activation_status(claim_token: str):
    """
    Endpoint de polling para que el cliente verifique si la cuenta ya fue activada.
    """
    cuenta = buscar_cuenta_por_claim_token(claim_token)
    if not cuenta:
        raise HTTPException(status_code=404, detail="Claim token no válido.")

    if cuenta['estatus_cuenta'] != 'verificada':
        return {"status": "pending"}

    # La cuenta está verificada, procederemos a generar el token de auto-login
    try:
        # 1. Encontrar la primera terminal de esta cuenta
        terminales = get_terminales_por_cuenta(cuenta['id'])
        if not terminales:
            raise Exception("No se encontró la terminal principal de la cuenta.")
        id_terminal = terminales[0]['id_terminal']

        # 2. Descargar la base de datos de usuarios desde R2
        ruta_db_usuarios = f"{cuenta['id_empresa_addsy']}/databases_generales/usuarios.sqlite"
        db_bytes = descargar_archivo_db(ruta_db_usuarios)
        if not db_bytes:
            raise Exception("No se pudo descargar la DB de usuarios.")
        
        # 3. Obtener información del primer usuario para crear el token
        # El nombre de usuario es ahora el ID de la cuenta, como se configuró en la verificación
        username_usuario = str(cuenta['nombre_completo'])
        usuario_info = obtener_info_empleado(db_bytes, username_usuario)
        
        if not usuario_info:
            raise Exception("No se encontró al usuario administrador inicial.")

        # 4. Crear un token de acceso para ese usuario
        # Los datos del token deben coincidir con la nueva tabla
        token_data = {
            "sub": usuario_info['nombre_usuario'],
            "id_usuario": usuario_info['id'], 
            "rol": usuario_info['rol'], 
            "id_cuenta_addsy": cuenta['id']
        }
        access_token = crear_access_token(data=token_data)

        return {
            "status": "complete",
            "id_terminal": id_terminal,
            "access_token": access_token,
            "usuario_info": usuario_info
        }
    except Exception as e:
        print(f"🔥🔥 ERROR durante el check_activation_status para claim {claim_token}: {e}")
        raise HTTPException(status_code=500, detail="Error al finalizar la activación.")

async def solicitar_reseteo_contrasena(data: models.SolicitudReseteo):
    """Genera un token de reseteo y envía el correo."""
    cuenta = buscar_cuenta_addsy_por_correo(data.email)
    # Importante: No revelamos si el correo existe o no por seguridad.
    if cuenta:
        token, token_expira = generar_token_verificacion()
        guardar_token_reseteo(data.email, token, token_expira)
        enviar_correo_reseteo(data.email, cuenta['nombre_completo'], token)
    
    return {"message": "Si tu correo está registrado, recibirás un enlace de recuperación."}

async def mostrar_pagina_reseteo(token: str):
    """Devuelve una página HTML simple para que el usuario ingrese la nueva contraseña."""
    # Este HTML es simple, en una app real podría ser una página de frontend.
    html_content = f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Restablecer Contraseña</title>
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
                background-color: #f0f2f5;
                display: flex;
                justify-content: center;
                align-items: center;
                height: 100vh;
                margin: 0;
            }}
            .container {{
                background-color: #ffffff;
                padding: 40px;
                border-radius: 8px;
                box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
                width: 100%;
                max-width: 400px;
                text-align: center;
            }}
            h3 {{
                color: #1c1e21;
                font-size: 24px;
                margin-bottom: 20px;
            }}
            input[type="password"] {{
                width: 100%;
                padding: 12px;
                margin-bottom: 15px;
                border: 1px solid #dddfe2;
                border-radius: 6px;
                box-sizing: border-box; /* Importante para el padding */
            }}
            input[type="submit"] {{
                width: 100%;
                padding: 12px;
                background-color: #2563EB;
                color: white;
                border: none;
                border-radius: 6px;
                font-size: 16px;
                font-weight: 600;
                cursor: pointer;
            }}
            input[type="submit"]:hover {{
                background-color: #1D4ED8;
            }}
            .show-password {{
                text-align: left;
                margin-bottom: 20px;
                font-size: 14px;
                color: #606770;
            }}
            #error_message {{
                color: #d93025;
                font-size: 12px;
                text-align: left;
                height: 15px;
                margin-bottom: 10px;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h3>Establece tu nueva contraseña</h3>
            <form action="/api/v1/auth/ejecutar-reseteo" method="post" onsubmit="return validateForm()">
                <input type="hidden" name="token" value="{token}" />
                
                <input type="password" id="nueva_contrasena" name="nueva_contrasena" placeholder="Nueva Contraseña" required minlength="6">
                <input type="password" id="confirmar_contrasena" name="confirmar_contrasena" placeholder="Confirmar Nueva Contraseña" required minlength="6">
                
                <div class="show-password">
                    <input type="checkbox" onclick="togglePasswordVisibility()"> Mostrar contraseñas
                </div>

                <div id="error_message"></div>

                <input type="submit" value="Restablecer Contraseña">
            </form>
        </div>

        <script>
            function togglePasswordVisibility() {{
                var pass1 = document.getElementById("nueva_contrasena");
                var pass2 = document.getElementById("confirmar_contrasena");
                if (pass1.type === "password") {{
                    pass1.type = "text";
                    pass2.type = "text";
                }} else {{
                    pass1.type = "password";
                    pass2.type = "password";
                }}
            }}

            function validateForm() {{
                var pass1 = document.getElementById("nueva_contrasena").value;
                var pass2 = document.getElementById("confirmar_contrasena").value;
                var errorMessage = document.getElementById("error_message");

                if (pass1 !== pass2) {{
                    errorMessage.textContent = "Las contraseñas no coinciden.";
                    return false; // Evita que el formulario se envíe
                }} else {{
                    errorMessage.textContent = "";
                    return true; // Permite que el formulario se envíe
                }}
            }}
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

async def ejecutar_reseteo_contrasena(request: Request):
    """Procesa el formulario de la página de reseteo."""
    try:  # <--- AÑADIR TRY
        form_data = await request.form()
        token = form_data.get("token")
        nueva_contrasena = form_data.get("nueva_contrasena")

        print(f"DEBUG - Contraseña recibida del formulario: '{nueva_contrasena}'")

        if not all([token, nueva_contrasena]):
            return HTMLResponse("Faltan datos.", status_code=400)

        # Esta es la línea que puede fallar
        nueva_contrasena_hash = hash_contrasena(nueva_contrasena)

        resultado = resetear_contrasena_con_token(token, nueva_contrasena_hash)

        if resultado == "success":
            return HTMLResponse("<h3>✅ Contraseña actualizada exitosamente. Ya puedes cerrar esta ventana.</h3>")
        else:
            return HTMLResponse(f"<h3>❌ Error: {resultado.replace('_', ' ')}.</h3>", status_code=400)

    except Exception as e: # <--- AÑADIR EXCEPT
        # Si algo falla (como el hashing), ahora sí lo registraremos y devolveremos un error real.
        print(f"🔥🔥 ERROR CRÍTICO en ejecutar_reseteo_contrasena: {e}")
        return HTMLResponse("<h3>❌ Ocurrió un error inesperado en el servidor al intentar actualizar tu contraseña.</h3>", status_code=500)
