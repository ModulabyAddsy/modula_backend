# app/routes/stripe_routes.py

from fastapi import APIRouter, Request, Header, HTTPException
import stripe
import os
from dotenv import load_dotenv
import json

load_dotenv()

router = APIRouter()
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")  # Lo defines en .env o Render

@router.post("/webhook-stripe")
async def stripe_webhook(request: Request, stripe_signature: str = Header(None)):
    payload = await request.body()
    sig_header = stripe_signature

    try:
        event = stripe.Webhook.construct_event(
            payload=payload,
            sig_header=sig_header,
            secret=STRIPE_WEBHOOK_SECRET
        )
    except stripe.error.SignatureVerificationError as e:
        raise HTTPException(status_code=400, detail="Firma inválida del webhook")

    # 🎯 Manejamos evento de sesión completada
    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]

        # Aquí podrías guardar en base de datos que el usuario ya pagó
        print("✅ Sesión completada con éxito:", session["id"])

        # (opcional) recuperar datos
        cliente = session.get("customer")
        email = session.get("customer_email")
        suscripcion_id = session.get("subscription")

        # Puedes almacenar en base de datos: cliente, email, suscripción_id
        # y enlazarlo con la creación de cuenta.

    elif event["type"] == "invoice.payment_failed":
        print("❌ Falló el pago de la suscripción")

    elif event["type"] == "invoice.paid":
        print("💸 Se cobró una suscripción")

    return {"status": "ok"}