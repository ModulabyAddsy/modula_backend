from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from datetime import datetime
from app.services.models import RegistroCuenta
from app.services.db import (
    crear_tabla_usuarios,
    obtener_usuario_por_correo,
    obtener_o_crear_id_empresa,
    registrar_usuario,
    get_connection,
)
from app.services.utils import hash_contrasena, generar_token_verificacion
from app.services.mail import enviar_correo_verificacion
from cloud.setup_empresa_cloud import inicializar_empresa_nueva

app = FastAPI()

# Habilitar CORS para poder hacer peticiones desde HTML local o dominios públicos
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Puedes reemplazar con el dominio exacto en producción
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Crear tabla usuarios si no existe al iniciar el servidor
@app.on_event("startup")
def startup():
    crear_tabla_usuarios()

@app.get("/")
def read_root():
    return {"message": "Modula backend activo 🚀"}

@app.post("/registrar-cuenta")
async def registrar_cuenta(data: RegistroCuenta):
    """
    Endpoint para registrar una nueva cuenta en Addsy.
    - Verifica si el correo ya está registrado.
    - Si no, genera ID empresa y token.
    - Guarda el usuario.
    - Envía correo de verificación.
    """
    try:
        # 1. Validar si el correo ya existe
        usuario = obtener_usuario_por_correo(data.correo)

        if usuario:
            if usuario["estatus"] == "verificada":
                raise HTTPException(status_code=400, detail="Este correo ya está verificado y registrado.")
            elif usuario["estatus"] == "pendiente":
                raise HTTPException(status_code=400, detail="Este correo ya fue registrado pero no verificado.")

        # 2. Generar ID de empresa
        id_empresa = obtener_o_crear_id_empresa(data.nombre_empresa)

        # 3. Generar token y expiración
        token, token_expira = generar_token_verificacion()

        # 4. Encriptar contraseña
        contrasena_segura = hash_contrasena(data.contrasena)

        # 5. Preparar datos a guardar
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

        # 6. Guardar usuario
        registrar_usuario(nuevo_usuario)

        # 7. Enviar correo de verificación
        enviar_correo_verificacion(data.correo, data.nombre_completo, token)

        return {
            "mensaje": "Cuenta registrada correctamente. Revisa tu correo para verificar.",
            "id_empresa": id_empresa
        }

    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error interno: {e}")


@app.get("/verificar-cuenta", response_class=HTMLResponse)
async def verificar_cuenta(request: Request):
    """
    Endpoint que recibe el token por URL y activa la cuenta si es válido.
    También inicializa la estructura de empresa en la nube (R2).
    """
    token = request.query_params.get("token")
    if not token:
        return HTMLResponse("<h3>❌ Token inválido</h3>", status_code=400)

    try:
        # Buscar al usuario con ese token
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM usuarios WHERE token = %s;", (token,))
        usuario = cur.fetchone()

        if not usuario:
            return HTMLResponse("<h3>❌ Token no válido</h3>", status_code=404)

        # Verificar si expiró
        if usuario["token_expira"] < datetime.utcnow():
            return HTMLResponse("<h3>⚠️ Token expirado. Solicita uno nuevo.</h3>", status_code=403)

        # Marcar como verificado
        cur.execute("""
            UPDATE usuarios
            SET estatus = 'verificada',
                token = NULL,
                token_expira = NULL
            WHERE id = %s;
        """, (usuario["id"],))
        conn.commit()
        conn.close()

        # Crear estructura en la nube para la empresa
        id_empresa = usuario["id_empresa"]
        exito = inicializar_empresa_nueva(id_empresa)

        if not exito:
            return HTMLResponse("<h3>✅ Cuenta verificada, pero falló la creación en la nube.</h3>", status_code=500)

        return HTMLResponse("<h2>✅ Cuenta verificada con éxito. ¡Ya puedes iniciar sesión en Modula!</h2>")

    except Exception as e:
        return HTMLResponse(f"<h3>❌ Error al verificar cuenta: {e}</h3>", status_code=500)