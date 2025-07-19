from fastapi import APIRouter, Request, Header, HTTPException
import stripe
import os

router = APIRouter()

@router.on_event("startup")
def configurar_stripe():
    stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
    if not stripe.api_key:
        raise RuntimeError("❌ No se encontró STRIPE_SECRET_KEY")
    print("✅ Clave secreta de Stripe cargada correctamente.")

@router.post("/webhook-stripe")
async def stripe_webhook(request: Request, stripe_signature: str = Header(None)):
    endpoint_secret = os.getenv("STRIPE_WEBHOOK_SECRET")
    if not endpoint_secret:
        raise HTTPException(status_code=500, detail="Webhook secret no configurado")

    try:
        payload = await request.body()
        event = stripe.Webhook.construct_event(payload, stripe_signature, endpoint_secret)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    # === MANEJO DE EVENTOS ===
    event_type = event['type']
    data = event['data']['object']

    if event_type == "checkout.session.completed":
        print("✅ Pago completado. Cliente:", data.get("customer_email"))
    elif event_type == "invoice.paid":
        print("💸 Factura pagada para:", data.get("customer_email"))
    elif event_type == "invoice.payment_failed":
        print("❌ Falló el pago de:", data.get("customer_email"))
    else:
        print(f"ℹ️ Evento no manejado: {event_type}")

    return {"status": "ok"}