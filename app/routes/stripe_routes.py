# app/routes/stripe_routes.py
from fastapi import APIRouter, Request, Header, HTTPException
import stripe
import os
from dotenv import load_dotenv

# 👇 IMPORTS UNIFICADOS: Incluimos las funciones para ambos flujos
from app.services.db import (
    buscar_cuenta_addsy_por_correo,
    actualizar_cuenta_para_verificacion,
    guardar_stripe_subscription_id,
    guardar_stripe_customer_id,
    actualizar_suscripcion_tras_pago,
    registrar_pago_fallido,
    resolver_pago_fallido,
    actualizar_estado_suscripcion
)
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

    # --- ========================================================== ---
    # --- FLUXO 1: ALTA DE NUEVOS USUARIOS (LÓGICA RECUPERADA) ---
    # --- ========================================================== ---
    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        metadata = session.get("metadata")
        stripe_subscription_id = session.get("subscription")
        stripe_customer_id = session.get("customer")
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
            guardar_stripe_subscription_id(cuenta["id"], stripe_subscription_id)
            guardar_stripe_customer_id(cuenta["id"], stripe_customer_id)
            print(f"✅ Alta de {correo} procesada. Correo de verificación enviado.")
        else:
            print(f"ℹ️ Webhook 'checkout.session.completed' para {correo} ignorado (estado no es 'pendiente_pago' o no se encontró cuenta).")

    # --- ========================================================== ---
    # --- FLUXO 2: GESTIÓN DE SUSCRIPCIONES EXISTENTES (NUEVA LÓGICA) ---
    # --- ========================================================== ---
    elif event["type"] == "invoice.paid":
        invoice = event["data"]["object"]
        id_suscripcion_stripe = invoice.get("subscription")
        
        if invoice.get("status") == "paid" and id_suscripcion_stripe:
            nuevo_periodo_fin_ts = invoice.get("period_end")
            id_cuenta = actualizar_suscripcion_tras_pago(id_suscripcion_stripe, nuevo_periodo_fin_ts, 'activa')
            
            if id_cuenta:
                resolver_pago_fallido(id_suscripcion_stripe)
                print(f"✅ Pago recurrente para {id_suscripcion_stripe} exitoso. Deudor resuelto.")
        else:
            print("ℹ️ Webhook 'invoice.paid' ignorado (no es de una suscripción o estado no es 'paid').")

    elif event["type"] == "invoice.payment_failed":
        invoice = event["data"]["object"]
        id_suscripcion_stripe = invoice.get("subscription")

        if id_suscripcion_stripe:
            id_cuenta = actualizar_estado_suscripcion(id_suscripcion_stripe, 'vencida')
            if id_cuenta:
                datos_fallo = {
                    "id_cuenta_addsy": id_cuenta,
                    "id_suscripcion_stripe": id_suscripcion_stripe,
                    "monto_debido": invoice.get("amount_due"),
                    "moneda": invoice.get("currency"),
                    "motivo_fallo": invoice.get("last_payment_error", {}).get("message", "Sin detalles"),
                    "url_factura_stripe": invoice.get("hosted_invoice_url")
                }
                registrar_pago_fallido(datos_fallo)
                print(f"🚨 PAGO FALLIDO registrado para {id_suscripcion_stripe}.")

    elif event["type"] == "customer.subscription.updated":
        subscription = event['data']['object']
        id_suscripcion_stripe = subscription.get('id')
        nuevo_estado_stripe = subscription.get('status')
        
        estado_modula = None
        if nuevo_estado_stripe in ['past_due', 'unpaid']: estado_modula = 'vencida'
        elif nuevo_estado_stripe == 'canceled': estado_modula = 'cancelada'
        elif nuevo_estado_stripe == 'active': estado_modula = 'activa'
        
        if id_suscripcion_stripe and estado_modula:
            actualizar_estado_suscripcion(id_suscripcion_stripe, estado_modula)
            print(f"ℹ️ Estado de suscripción {id_suscripcion_stripe} actualizado a '{estado_modula}' via webhook.")

    return {"status": "ok"}