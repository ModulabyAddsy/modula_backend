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
    get_sucursales_por_cuenta
)
from app.services import security

from app.services.employee_service import anadir_primer_administrador
from app.services.cloud.setup_empresa_cloud import subir_archivo_db
from app.services.utils import generar_contrasena_temporal
from app.services.mail import enviar_correo_credenciales

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

    suscripcion = actualizar_y_verificar_suscripcion(id_cuenta)
    if not suscripcion or suscripcion['estado_suscripcion'] not in ['activa', 'prueba_gratis']:
        estado = suscripcion['estado_suscripcion'] if suscripcion else 'desconocido'
        raise HTTPException(status_code=403, detail=f"Suscripción no válida. Estado: {estado}")

    # --- LÓGICA DE VERIFICACIÓN CORREGIDA Y FINAL ---
    ip_registrada = terminal_info.get('direccion_ip')
    
    # Escenario 1: La IP registrada es nula (primer arranque de la terminal).
    # Se considera un caso válido, se actualiza la IP y se da acceso.
    if not ip_registrada:
        print(f"✅ Primera vez que se registra IP para la terminal {request_data.id_terminal}.")
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

    # Escenario 2: La IP registrada coincide con la IP actual. Acceso normal.
    elif str(ip_registrada).strip() == client_ip.strip():
        # No es necesario actualizar la IP si es la misma, pero sí el contador y la última sincronización.
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
    
    # Escenario 3: La IP existe PERO es diferente. ESTE ES EL CONFLICTO.
    else:
        print(f"⚠️ Conflicto de ubicación para terminal {request_data.id_terminal}. IP registrada: {ip_registrada}, IP actual: {client_ip}")
        
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
