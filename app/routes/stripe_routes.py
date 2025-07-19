# app/routes/stripe_routes.py
from fastapi import APIRouter, Request, Header, HTTPException
import stripe
import os
from dotenv import load_dotenv

# Importar las funciones que necesitaremos de otros servicios
from app.services.db import obtener_usuario_por_correo, actualizar_usuario_para_verificacion
from app.services.utils import generar_token_verificacion
from app.services.mail import enviar_correo_verificacion

load_dotenv()

router = APIRouter()
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")

@router.post("/webhook-stripe")
async def stripe_webhook(request: Request, stripe_signature: str = Header(None)):
    payload = await request.body()
    
    try:
        event = stripe.Webhook.construct_event(
            payload=payload, sig_header=stripe_signature, secret=STRIPE_WEBHOOK_SECRET
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid payload: {e}")
    except stripe.error.SignatureVerificationError as e:
        raise HTTPException(status_code=400, detail=f"Invalid signature: {e}")

    # --- Manejo del evento de pago exitoso ---
    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        metadata = session.get("metadata")

        if not metadata or "correo_usuario" not in metadata:
            print("❌ Error: Webhook recibido sin correo_usuario en los metadatos.")
            return {"status": "error", "detail": "Missing metadata"}

        correo = metadata["correo_usuario"]
        id_terminal = metadata.get("id_terminal", "") # Obtenemos el id_terminal

        # 1. Buscar al usuario en la base de datos
        usuario = obtener_usuario_por_correo(correo)
        if not usuario:
            print(f"❌ Error: Usuario con correo {correo} no encontrado en la BD.")
            return {"status": "error", "detail": "User not found"}

        # 2. Verificar que el usuario esté esperando el pago
        if usuario["estatus"] == "pendiente_pago":
            # 3. Generar token de verificación y actualizar usuario
            token, token_expira = generar_token_verificacion()
            actualizar_usuario_para_verificacion(correo, token, token_expira)
            
            # 4. Enviar el correo de verificación
            enviar_correo_verificacion(
                destinatario=correo,
                nombre_usuario=usuario["nombre_completo"],
                token=token,
                id_terminal=id_terminal # Pasamos el id_terminal al correo
            )
            print(f"✅ Pago completado para {correo}. Correo de verificación enviado.")
        else:
            print(f"ℹ️ Webhook recibido para {correo}, pero su estatus no es 'pendiente_pago' (es {usuario['estatus']}). Se ignora.")

    return {"status": "ok"}