#auth_controller.py
# Importación de librerías y dependencias necesarias
from fastapi import HTTPException, Request
from fastapi.responses import HTMLResponse
from datetime import datetime
from app.services.terminal_service import crear_terminal_si_no_existe
from app.services.models import RegistroCuenta
from app.services.stripe_service import crear_sesion_checkout_para_registro # Crearemos esta función

# Importación de funciones de base de datos relacionadas a usuarios y empresas
from app.services.db import (
    get_connection,
    obtener_usuario_por_correo,
    obtener_o_crear_id_empresa,
    registrar_usuario,
)
# Importación de funciones auxiliares (hash y generación de tokens)
from app.services.utils import hash_contrasena, generar_token_verificacion
# Servicio para envío de correos
from app.services.mail import enviar_correo_verificacion
# Función que inicializa la estructura en la nube
from app.services.cloud.setup_empresa_cloud import inicializar_empresa_nueva

# ✅ Endpoint para registrar una cuenta nueva en Modula
async def registrar_cuenta_y_crear_pago(data: RegistroCuenta):
    # 1. Buscar si el correo ya está registrado y activo
    usuario = obtener_usuario_por_correo(data.correo)
    if usuario and usuario["estatus"] == "verificada":
        raise HTTPException(status_code=400, detail="Este correo ya está en uso.")
    
    # Si el usuario existe pero con otro estado (ej. pendiente_pago), se podría borrar y crear de nuevo
    # o manejar la lógica para reintentar el pago. Por ahora, lo mantenemos simple.

    # 2. Hashear la contraseña
    contrasena_segura = hash_contrasena(data.contrasena)
    id_empresa = obtener_o_crear_id_empresa(data.nombre_empresa)

    # 3. Guardar usuario con estado 'pendiente_pago'
    # Nota: No generamos token de verificación aquí todavía.
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
        "token": None, # Se generará después del pago
        "token_expira": None,
        "estatus": "pendiente_pago" # Nuevo estatus
    }
    
    # Aquí necesitaríamos una función en db.py que inserte y devuelva el usuario,
    # o que maneje la actualización si ya existía como pendiente_pago.
    registrar_usuario(nuevo_usuario_data) # Asumimos que esta función es adecuada por ahora

    # 4. Crear la sesión de pago en Stripe
    # Debemos determinar si aplica la prueba gratuita aquí
    # Por ejemplo, verificando si el id_terminal ya existe en la tabla `terminales`
    # (necesitaríamos una función para eso)
    aplica_prueba = True # Lógica para determinar esto va aquí

    # Pasamos los datos necesarios para el checkout y los metadatos
    try:
        checkout_session = await crear_sesion_checkout_para_registro(
            nombre_completo=data.nombre_completo,
            correo=data.correo,
            id_terminal=data.id_terminal,
            aplica_prueba=aplica_prueba
        )
        return {"url_checkout": checkout_session.url}
    except Exception as e:
        # Si Stripe falla, podríamos querer borrar al usuario 'pendiente_pago' o marcarlo como fallido.
        raise HTTPException(status_code=500, detail=f"Error al contactar con el servicio de pago: {e}")


#  Endpoint para verificar la cuenta a través del token recibido por correo
async def verificar_cuenta(request: Request):
    # Obtener el token desde los parámetros de la URL
    token = request.query_params.get("token")
    
    # Si no se proporcionó un token, retornar error
    if not token:
        return HTMLResponse("<h3>❌ Token inválido</h3>", status_code=400)

    try:
        # Conectarse a la base de datos
        conn = get_connection()
        cur = conn.cursor()
        # Buscar en la tabla de usuarios si existe un registro con ese token
        cur.execute("SELECT * FROM usuarios WHERE token = %s;", (token,))
        usuario = cur.fetchone()
        # Si no se encuentra ningún usuario con ese token, retornar error
        if not usuario:
            return HTMLResponse("<h3>❌ Token no válido</h3>", status_code=404)
        # Verificar si el token ya expiró
        if usuario["token_expira"] < datetime.utcnow():
            return HTMLResponse("<h3>⚠️ Token expirado.</h3>", status_code=403)

        # Actualizar el estado del usuario a "verificada" y eliminar el token y su expiración
        cur.execute("""
            UPDATE usuarios
            SET estatus = 'verificada',
                token = NULL,
                token_expira = NULL
            WHERE id = %s;
        """, (usuario["id"],))
        conn.commit()
        conn.close()
        
          # === CREAR TERMINAL RELACIONADA ===
        # Obtener IP del request
        ip_terminal = request.client.host
        # Obtener id_terminal desde parámetros (ej. enviado desde frontend)
        id_terminal = request.query_params.get("id_terminal")

        if id_terminal:
            try:
                terminal_nueva = crear_terminal_si_no_existe(id_terminal, usuario["id_empresa"], ip_terminal)

                # Si la terminal ya existía => desactivar prueba gratis
                if not terminal_nueva:
                    print("⚠️ Terminal ya registrada. Desactivando prueba gratis.")
                    conn = get_connection()
                    cur = conn.cursor()
                    cur.execute("UPDATE usuarios SET prueba_gratis = FALSE WHERE id = %s;", (usuario["id"],))
                    conn.commit()
                    conn.close()
            except Exception as err:
                print(f"⚠️ Error al registrar terminal automáticamente: {err}")
        else:
            print("ℹ️ id_terminal no proporcionado. No se creó terminal.")

        # === CREAR ESTRUCTURA EN LA NUBE ===
        exito = inicializar_empresa_nueva(usuario["id_empresa"])
        if not exito:
            return HTMLResponse("<h3>✅ Cuenta verificada, pero falló la creación en la nube.</h3>", status_code=500)

        return HTMLResponse("<h2>✅ Cuenta verificada. ¡Ya puedes iniciar sesión!</h2>")
    
    except Exception as e:
        return HTMLResponse(f"<h3>❌ Error al verificar cuenta: {e}</h3>", status_code=500) # Capturar errores inesperados y mostrar mensaje