# app/routes/stripe_routes.py
from fastapi import APIRouter, Request, Header, HTTPException
import stripe
import os
from dotenv import load_dotenv

# 👉 Importamos las funciones correctas
from app.services.db import buscar_cuenta_addsy_por_correo, actualizar_cuenta_para_verificacion, guardar_stripe_subscription_id,actualizar_suscripcion_tras_pago, guardar_stripe_customer_id
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

    # --- MANEJADOR PARA EL ALTA DE NUEVOS CLIENTES ---
    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        metadata = session.get("metadata")
        stripe_subscription_id = session.get("subscription")
        stripe_customer_id = session.get("customer") # <--- 1. OBTENEMOS EL ID DEL CLIENTE
        session_id = session.get("id")

        if not metadata or "correo_usuario" not in metadata:
            print("❌ Error: Webhook 'checkout.session.completed' sin correo_usuario.")
            return {"status": "error", "detail": "Missing metadata"}

        correo = metadata["correo_usuario"]
        cuenta = buscar_cuenta_addsy_por_correo(correo)
        
        if cuenta and cuenta["estatus_cuenta"] == "pendiente_pago":
            token, token_expira = generar_token_verificacion()
            actualizar_cuenta_para_verificacion(correo, token, token_expira)
            enviar_correo_verificacion(
                destinatario=correo, nombre_usuario=cuenta["nombre_completo"],
                token=token, id_terminal=metadata.get("id_terminal"),
                id_stripe_session=session_id
            )
            # --- GUARDAMOS AMBOS IDs ---
            guardar_stripe_subscription_id(cuenta["id"], stripe_subscription_id)
            guardar_stripe_customer_id(cuenta["id"], stripe_customer_id) # <--- 2. GUARDAMOS EL ID DEL CLIENTE

            print(f"✅ Alta de {correo} procesada. Correo de verificación enviado. Sub ID y Customer ID guardados.")
        else:
            print(f"ℹ️ Webhook 'checkout.session.completed' para {correo} ignorado (estado no es 'pendiente_pago').")

    # --- MANEJADOR PARA PAGOS RECURRENTES EXITOSOS ---
    elif event["type"] == "invoice.paid":
        # La línea clave: nos aseguramos de trabajar con el objeto anidado.
        invoice = event["data"]["object"]

        # LOG DE DEPURACIÓN (ahora mostrará los valores correctos)
        print("--- DEBUG WEBHOOK 'invoice.paid' ---")
        print(f"Paid: {invoice.get('paid')}")
        print(f"Subscription ID: {invoice.get('subscription')}")
        print("------------------------------------")

        # Esta condición ahora debería ser verdadera
        if invoice.get("paid") and invoice.get("subscription"):
            stripe_sub_id = invoice.get("subscription")
            nuevo_periodo_fin_ts = invoice.get("period_end")

            # Llamamos a la función de la base de datos para actualizar el estado
            actualizar_suscripcion_tras_pago(stripe_sub_id, nuevo_periodo_fin_ts)
        else:
            print("ℹ️ Webhook 'invoice.paid' ignorado (no está pagado o no es de una suscripción).")

    return {"status": "ok"}