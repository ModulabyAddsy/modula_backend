# Importación de librerías y dependencias necesarias
from fastapi import HTTPException, Request
from fastapi.responses import HTMLResponse
from datetime import datetime
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
async def registrar_cuenta(data):
    # Buscar si el correo ya está registrado
    usuario = obtener_usuario_por_correo(data.correo)
    if usuario:
        # Si el correo ya está verificado, no se permite otro registro
        if usuario["estatus"] == "verificada":
            raise HTTPException(400, "Este correo ya está verificado.")
        # Si el correo ya fue registrado pero no verificado
        raise HTTPException(400, "Este correo ya fue registrado pero no verificado.")

    # Obtener o generar el ID único para la empresa
    id_empresa = obtener_o_crear_id_empresa(data.nombre_empresa)
    # Generar el token de verificación y su fecha de expiración
    token, token_expira = generar_token_verificacion()
    # Encriptar la contraseña del usuario
    contrasena_segura = hash_contrasena(data.contrasena)

    # Armar el diccionario con los datos del nuevo usuario
    nuevo_usuario = {
        "nombre_completo": data.nombre_completo,
        "telefono": data.telefono,
        "fecha_nacimiento": data.fecha_nacimiento,
        "correo": data.correo,
        "correo_recuperacion": data.correo_recuperacion,
        "contrasena": contrasena_segura,
        "nombre_empresa": data.nombre_empresa,
        "id_empresa": id_empresa,
        "rfc": data.rfc,
        "token": token,
        "token_expira": token_expira,
    }
    # Guardar el usuario en la base de datos
    registrar_usuario(nuevo_usuario)
    # Enviar el correo de verificación con el token
    enviar_correo_verificacion(data.correo, data.nombre_completo, token)
    # Devolver respuesta exitosa
    return {
        "mensaje": "Cuenta registrada correctamente. Revisa tu correo.",
        "id_empresa": id_empresa
    }

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

        # Crear la estructura en la nube para la empresa asociada
        exito = inicializar_empresa_nueva(usuario["id_empresa"])
        if not exito:   # Verificar si la creación en la nube falló
            return HTMLResponse("<h3>✅ Cuenta verificada, pero falló la creación en la nube.</h3>", status_code=500)
        # Si todo fue exitoso, notificar al usuario
        return HTMLResponse("<h2>✅ Cuenta verificada. ¡Ya puedes iniciar sesión!</h2>")
    
    except Exception as e:
        return HTMLResponse(f"<h3>❌ Error al verificar cuenta: {e}</h3>", status_code=500) # Capturar errores inesperados y mostrar mensaje