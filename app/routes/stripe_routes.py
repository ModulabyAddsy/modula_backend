# app/routes/stripe_routes.py
from fastapi import APIRouter, Request, Header, HTTPException
import stripe
import os
from dotenv import load_dotenv

# 👉 Importamos las funciones correctas
from app.services.db import buscar_cuenta_addsy_por_correo, actualizar_cuenta_para_verificacion, guardar_stripe_subscription_id
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

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        metadata = session.get("metadata")
        stripe_subscription_id = session.get("subscription")
        session_id = session.get("id") # ✅ CORRECCIÓN 1: Volver a añadir esta línea

        if not metadata or "correo_usuario" not in metadata:
            print("❌ Error: Webhook recibido sin correo_usuario en los metadatos.")
            return {"status": "error", "detail": "Missing metadata"}

        correo = metadata["correo_usuario"]
        id_terminal = metadata.get("id_terminal")

        cuenta = buscar_cuenta_addsy_por_correo(correo)
        if not cuenta:
            print(f"❌ Error: Cuenta con correo {correo} no encontrada en la BD.")
            return {"status": "error", "detail": "User not found"}

        # La lógica principal solo se ejecuta si la cuenta está pendiente de pago
        if cuenta["estatus_cuenta"] == "pendiente_pago":
            token, token_expira = generar_token_verificacion()
            actualizar_cuenta_para_verificacion(correo, token, token_expira)
            
            # El id_stripe_session ahora está definido y no causará error
            enviar_correo_verificacion(
                destinatario=correo,
                nombre_usuario=cuenta["nombre_completo"],
                token=token,
                id_terminal=id_terminal,
                id_stripe_session=session_id
            )

            # ✅ CORRECCIÓN 2: Mover el guardado del ID aquí adentro
            guardar_stripe_subscription_id(cuenta["id"], stripe_subscription_id)

            # ✅ CORRECCIÓN 3: Dejar solo una línea de log de éxito
            print(f"✅ Pago completado para {correo}. Correo de verificación enviado y sub ID guardado.")
        else:
            print(f"ℹ️ Webhook recibido para {correo}, pero su estatus no es 'pendiente_pago' (es {cuenta['estatus_cuenta']}). Se ignora.")

    return {"status": "ok"}