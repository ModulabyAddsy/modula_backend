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
    resetear_contrasena_con_token, get_ubicaciones_autorizadas, 
    autorizar_nueva_ubicacion
)
from app.services import security
from app.services import employee_service
from app.services.employee_service import anadir_primer_administrador
from app.services.cloud.setup_empresa_cloud import subir_archivo_db
from app.services.utils import generar_contrasena_temporal, generar_token_verificacion, get_ip_geolocation
from app.services.mail import enviar_correo_credenciales, enviar_correo_reseteo

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

    nuevo_usuario_data = data.dict() # Ahora esto ya incluye el claim_token
    nuevo_usuario_data['contrasena_hash'] = hash_contrasena(data.contrasena)
    
    cuenta_id = crear_cuenta_addsy(nuevo_usuario_data) # La función de DB ya está lista para recibirlo
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
    Autentica al usuario y devuelve un token. Su única responsabilidad es la identidad.
    """
    cuenta = buscar_cuenta_addsy_por_correo(form_data.correo)
    if not cuenta or not verificar_contrasena(form_data.contrasena, cuenta["contrasena_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="Correo o contraseña incorrectos",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    if cuenta["estatus_cuenta"] != "verificada":
        raise HTTPException(status_code=400, detail=f"La cuenta no ha sido verificada. Estatus: {cuenta['estatus_cuenta']}")
    
    access_token_data = {
        "sub": cuenta["correo"], 
        "id": cuenta["id"],
        "id_empresa_addsy": cuenta["id_empresa_addsy"]
    }
    access_token = crear_access_token(data=access_token_data)
    
    # ✅ CORRECCIÓN: Ya no devolvemos el id_terminal aquí.
    return {
        "access_token": access_token, 
        "token_type": "bearer"
    }

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
        username_empleado = "11001" 
        contrasena_temporal = generar_contrasena_temporal()
        
        # D. Añadir el primer admin al archivo descargado
        db_bytes_modificado = anadir_primer_administrador(
            db_bytes_original, datos_propietario, username_empleado, contrasena_temporal
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
        return HTMLResponse(f"<h3>✅ Tu cuenta está activa, pero hubo un error al generar tus credenciales: {e}.</h3>", status_code=500)
    
    actualizar_contadores_suscripcion(cuenta_activada['id'])
    
    return HTMLResponse("<h2>✅ ¡Todo listo! Tu cuenta ha sido configurada. Revisa tu correo para obtener tus credenciales de acceso.</h2>")

def verificar_terminal_activa_controller(
    request_data: models.TerminalVerificationRequest, client_ip: str
) -> models.TerminalVerificationResponse:
    
    terminal_info = buscar_terminal_activa_por_id(request_data.id_terminal)
    if not terminal_info:
        raise HTTPException(status_code=404, detail="Terminal no registrada o inactiva.")

    id_cuenta = terminal_info['id_cuenta_addsy']
    id_sucursal = terminal_info['id_sucursal']

    suscripcion = actualizar_y_verificar_suscripcion(id_cuenta)
    if not suscripcion or suscripcion['estado_suscripcion'] not in ['activa', 'prueba_gratis']:
        estado = suscripcion['estado_suscripcion'] if suscripcion else 'desconocido'
        raise HTTPException(status_code=403, detail=f"Suscripción no válida. Estado: {estado}")
    
    #CORRECCIÓN: Guardar la IP si es la primera vez que se verifica
    ip_registrada = terminal_info.get('direccion_ip')
    if not ip_registrada:
        print(f"✅ Primera conexión desde la terminal {request_data.id_terminal}. Registrando IP.")
        actualizar_ip_terminal(request_data.id_terminal, client_ip)

    # --- LÓGICA DE VERIFICACIÓN DE UBICACIÓN INTELIGENTE ---
    ubicaciones_autorizadas = get_ubicaciones_autorizadas(id_sucursal)
    
    # Si es la primera vez que se usa la terminal en cualquier lugar, autorizamos esta ubicación.
    if not ubicaciones_autorizadas:
        print(f"📍 Primera ubicación para sucursal {id_sucursal}. Autorizando automáticamente.")
        geo_data = get_ip_geolocation(client_ip)
        autorizar_nueva_ubicacion(id_sucursal, client_ip, geo_data)
        # Si la autorización es exitosa, procedemos al acceso normal.
    else:
        # Si ya hay ubicaciones, verificamos si la actual coincide con alguna.
        geo_actual = get_ip_geolocation(client_ip)
        coincidencia_encontrada = False
        for ubicacion in ubicaciones_autorizadas:
            # Comparamos el proveedor de internet (ISP) y la ciudad.
            # Esta es una comparación mucho más estable que la IP exacta.
            if ubicacion['isp'] and ubicacion['isp'] == geo_actual.get('isp') and \
               ubicacion['ciudad'] and ubicacion['ciudad'] == geo_actual.get('ciudad'):
                coincidencia_encontrada = True
                break
        
        if not coincidencia_encontrada:
            # Si no coincide con ninguna ubicación autorizada, AHORA SÍ es un conflicto.
            print(f"⚠️ Conflicto de ubicación para terminal {request_data.id_terminal}. La ubicación actual no está autorizada.")
            
            sugerencia_dict = buscar_sucursal_por_ip_en_otra_terminal(
                id_terminal_actual=request_data.id_terminal, ip=client_ip, id_cuenta=id_cuenta
            )
            sugerencia = models.SucursalInfo(**sugerencia_dict) if sugerencia_dict else None

            lista_sucursales_dict = get_sucursales_por_cuenta(id_cuenta)
            lista_sucursales = [models.SucursalInfo(**s) for s in lista_sucursales_dict]

            return models.TerminalVerificationResponse(
                status="location_mismatch",
                sugerencia_migracion=sugerencia,
                sucursales_existentes=lista_sucursales
            )

    # Si la verificación fue exitosa, actualizamos la IP y damos acceso
    actualizar_ip_terminal(request_data.id_terminal, client_ip)
    actualizar_contadores_suscripcion(id_cuenta)
    
    access_token_data = {
        "sub": terminal_info["correo"], "id": id_cuenta,
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

async def check_activation_status(claim_token: str):
    """
    Endpoint de polling para que el cliente verifique si la cuenta ya fue activada.
    """
    cuenta = buscar_cuenta_por_claim_token(claim_token)
    if not cuenta:
        raise HTTPException(status_code=404, detail="Claim token no válido.")

    if cuenta['estatus_cuenta'] != 'verificada':
        return {"status": "pending"}

    # ¡La cuenta está verificada! Procedemos a generar el token de auto-login
    try:
        # 1. Encontrar la primera terminal de esta cuenta
        terminales = get_terminales_por_cuenta(cuenta['id'])
        if not terminales:
            raise Exception("No se encontró la terminal principal de la cuenta.")
        id_terminal = terminales[0]['id_terminal']

        # 2. Descargar la DB de empleados
        ruta_db_usuarios = f"{cuenta['id_empresa_addsy']}/databases_generales/usuarios.sqlite"
        db_bytes = descargar_archivo_db(ruta_db_usuarios)
        if not db_bytes:
            raise Exception("No se pudo descargar la DB de empleados.")
        
        # 3. Obtener info del primer empleado para crear el token
        empleado_info = employee_service.obtener_info_empleado(db_bytes, "11001")
        if not empleado_info:
            raise Exception("No se encontró al empleado administrador inicial.")

        # 4. Crear un token de acceso para ese empleado
        token_data = {
            "sub": empleado_info['nombre_usuario'], "id_empleado": empleado_info['id_empleado'],
            "puesto": empleado_info['puesto'], "id_cuenta_addsy": cuenta['id']
        }
        access_token = crear_access_token(data=token_data)

        return {
            "status": "complete",
            "id_terminal": id_terminal,
            "access_token": access_token,
            "empleado_info": empleado_info
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
            <form action="/auth/ejecutar-reseteo" method="post" onsubmit="return validateForm()">
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
    form_data = await request.form()
    token = form_data.get("token")
    nueva_contrasena = form_data.get("nueva_contrasena")

    if not all([token, nueva_contrasena]):
         return HTMLResponse("Faltan datos.", status_code=400)

    nueva_contrasena_hash = hash_contrasena(nueva_contrasena)
    resultado = resetear_contrasena_con_token(token, nueva_contrasena_hash)

    if resultado == "success":
        return HTMLResponse("<h3>✅ Contraseña actualizada exitosamente. Ya puedes cerrar esta ventana.</h3>")
    else:
        return HTMLResponse(f"<h3>❌ Error: {resultado.replace('_', ' ')}.</h3>", status_code=400)