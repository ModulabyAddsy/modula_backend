# app/services/stripe_service.py
import stripe
import os
from fastapi import HTTPException
from dotenv import load_dotenv

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
            "payment_method_types": ["card"],
            "line_items": [
                {
                    "price": BASE_PLAN_PRICE_ID,
                    "quantity": 1,
                }
            ],
            "mode": "subscription",
            # URLs a las que Stripe redirigirá al usuario después del pago.
            # Es buena práctica que sean páginas de tu sitio web, no del backend.
            "success_url": "https://addsy.mx/pago-exitoso?session_id={CHECKOUT_SESSION_ID}",
            "cancel_url": "https://addsy.mx/pago-cancelado",
            
            # --- METADATOS CRÍTICOS ---
            # Esta es la información que Stripe nos devolverá en el webhook.
            # Con el 'correo_usuario', podremos encontrarlo en nuestra base de datos.
            "metadata": {
                "correo_usuario": correo,
                "id_terminal": id_terminal
            }
        }

        # 3. Si aplica la prueba, añadir los días de prueba a la suscripción.
        if aplica_prueba:
            session_args["subscription_data"] = {
                "trial_period_days": 14
            }

        # 4. Crear y devolver el objeto de la sesión de Checkout.
        checkout_session = stripe.checkout.Session.create(**session_args)
        return checkout_session

    except Exception as e:
        # Si algo sale mal con Stripe, lanzamos un error que el controlador atrapará.
        raise HTTPException(status_code=500, detail=f"Error al crear la sesión de pago: {e}")
