# app/routes/webhook_controller.py

from fastapi import APIRouter, Request, Header, HTTPException
import stripe
import os

router = APIRouter()

# Configura la clave secreta del webhook
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")  # clave secreta de API
endpoint_secret = os.getenv("STRIPE_WEBHOOK_SECRET")  # clave del webhook

@router.post("/webhook-stripe")
async def stripe_webhook(request: Request, stripe_signature: str = Header(None)):
    try:
        payload = await request.body()
        event = stripe.Webhook.construct_event(
            payload, stripe_signature, endpoint_secret
        )
    except ValueError as e:
        # Payload inválido
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError as e:
        # Firma inválida
        raise HTTPException(status_code=400, detail="Invalid signature")

    # === MANEJO DE EVENTOS ===
    event_type = event['type']
    data = event['data']['object']

    if event_type == "checkout.session.completed":
        print("✅ Pago completado. Cliente:", data.get("customer_email"))
        # Aquí puedes registrar que el cliente pagó y permitir verificación de cuenta

    elif event_type == "invoice.paid":
        print("💸 Factura pagada para:", data.get("customer_email"))
        # Opcionalmente puedes renovar acceso

    elif event_type == "invoice.payment_failed":
        print("❌ Falló el pago de:", data.get("customer_email"))
        # Aquí puedes suspender la cuenta si es necesario

    else:
        print(f"ℹ️ Evento no manejado: {event_type}")

    return {"status": "ok"}