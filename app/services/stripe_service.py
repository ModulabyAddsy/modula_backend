# app/services/stripe_service.py
import stripe
import os
from fastapi import HTTPException
from dotenv import load_dotenv
from datetime import datetime, timezone

load_dotenv()

# Configura la clave secreta de Stripe desde .env
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

# ID de precio para el plan mensual de Modula
BASE_PLAN_PRICE_ID = os.getenv("STRIPE_BASE_PLAN_PRICE_ID")

async def crear_sesion_checkout_para_registro(nombre_completo: str, correo: str, id_terminal: str, aplica_prueba: bool):
    """
    Crea un cliente y una sesión de pago en Stripe para un nuevo registro.
    Adjunta metadatos clave para que el webhook pueda identificar al usuario.
    """
    try:
        # 1. Crear un nuevo cliente en Stripe para este usuario.
        cliente = stripe.Customer.create(
            name=nombre_completo,
            email=correo,
            metadata={
                "id_terminal": id_terminal
            }
        )

        # 2. Definir los argumentos para la sesión de pago.
        session_args = {
            "customer": cliente.id,
            # --- 👇 EL ÚNICO CAMBIO ESTÁ AQUÍ ---
            "payment_method_types": ["card"],
            # --- ----------------------------- ---
            "line_items": [
                {
                    "price": BASE_PLAN_PRICE_ID,
                    "quantity": 1,
                }
            ],
            "mode": "subscription",
            # URLs a las que Stripe redirigirá al usuario después del pago.
            "success_url": "https://addsy.mx/pago-exitoso?session_id={CHECKOUT_SESSION_ID}",
            "cancel_url": "https://addsy.mx/pago-cancelado",
            
            # --- METADATOS CRÍTICOS ---
            "metadata": {
                "correo_usuario": correo,
                "id_terminal": id_terminal
            }
        }

        # 3. Si aplica la prueba, añadir los días de prueba a la suscripción.
        if aplica_prueba:
            session_args["subscription_data"] = {
                "trial_period_days": 7
            }

        # 4. Crear y devolver el objeto de la sesión de Checkout.
        checkout_session = stripe.checkout.Session.create(**session_args)
        return checkout_session

    except Exception as e:
        # Si algo sale mal con Stripe, lanzamos un error que el controlador atrapará.
        raise HTTPException(status_code=500, detail=f"Error al crear la sesión de pago: {e}")

def crear_sesion_portal_cliente(stripe_customer_id: str, return_url: str):
    """
    Crea una sesión del Portal del Cliente de Stripe para un cliente existente.
    """
    try:
        print(f"DEBUG: Creando sesión de portal para customer: {stripe_customer_id}")
        portal_session = stripe.billing_portal.Session.create(
            customer=stripe_customer_id,
            return_url=return_url,
        )
        print(f"DEBUG: Sesión de portal creada exitosamente. URL: {portal_session.url}")
        return portal_session.url
    except Exception as e:
        print(f"🔥🔥 CRITICAL ERROR al crear la sesión del portal de Stripe: {e}")
        return None

def get_subscription_status_from_stripe(stripe_sub_id: str):
    """
    Se conecta a Stripe para obtener el estado real y la fecha de vencimiento
    de una suscripción específica.
    """
    if not stripe_sub_id:
        return None
    try:
        # Hacemos la llamada directa a la API de Stripe
        subscription = stripe.Subscription.retrieve(stripe_sub_id)
        
        # Extraemos los datos que nos interesan
        status = subscription.status  # ej. "active", "past_due", "canceled"
        period_end_ts = subscription.current_period_end # Timestamp
        
        print(f"DEBUG Stripe: Estado real de {stripe_sub_id} es '{status}'.")
        
        return {
            "status": status,
            "period_end_ts": period_end_ts
        }
    except stripe.error.StripeError as e:
        print(f"🔥🔥 ERROR al verificar suscripción en Stripe: {e}")
        return None