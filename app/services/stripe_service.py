# app/services/stripe_service.py

import stripe
import os
from dotenv import load_dotenv

load_dotenv()

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

def crear_suscripcion(email, payment_method_id, aplica_prueba: bool):
    """
    Crea un cliente, lo asocia a un método de pago y genera una suscripción.
    """
    # Crear cliente
    cliente = stripe.Customer.create(
        email=email,
        payment_method=payment_method_id,
        invoice_settings={"default_payment_method": payment_method_id},
    )

    # Crear suscripción
    suscripcion = stripe.Subscription.create(
        customer=cliente.id,
        items=[{"price": os.getenv("STRIPE_PRICE_ID")}],
        trial_period_days=14 if aplica_prueba else None,
        expand=["latest_invoice.payment_intent"]
    )

    return suscripcion