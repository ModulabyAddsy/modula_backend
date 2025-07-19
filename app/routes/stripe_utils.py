# app/routes/stripe_utils.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr
import stripe
import os
from dotenv import load_dotenv

load_dotenv()

router = APIRouter()

# Configura la clave secreta de Stripe desde .env
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

# ID de precio para el plan mensual de Modula
MODULA_PRICE_ID = os.getenv("STRIPE_MODULA_PRICE_ID")  # Ej: "price_1Rm7MLPJk1pnp1WZnstS3BEZ"

# === Modelo para recibir datos del cliente ===
class DatosSuscripcion(BaseModel):
    nombre_completo: str
    correo: EmailStr
    id_terminal: str
    aplica_prueba: bool  # Esto lo defines según lógica de terminal existente o no

@router.post("/crear-intento-suscripcion")
async def crear_intento_suscripcion(data: DatosSuscripcion):
    try:
        # 1. Crear cliente en Stripe
        cliente = stripe.Customer.create(
            name=data.nombre_completo,
            email=data.correo,
            metadata={
                "id_terminal": data.id_terminal,
                "aplica_prueba": str(data.aplica_prueba).lower(),
                "nombre_completo": data.nombre_completo,
            }
        )

        # 2. Construir argumentos para crear sesión
        session_args = {
            "customer": cliente.id,
            "payment_method_types": ["card"],
            "line_items": [
                {
                    "price": MODULA_PRICE_ID,
                    "quantity": 1,
                }
            ],
            "mode": "subscription",
            "success_url": "https://modula-backend.onrender.com/exito",
            "cancel_url": "https://modula-backend.onrender.com/cancelado",
            "metadata": {
                "id_terminal": data.id_terminal,
                "aplica_prueba": str(data.aplica_prueba).lower(),
                "correo": data.correo,
                "nombre_completo": data.nombre_completo
            }
        }

        # Agregar periodo de prueba solo si aplica
        if data.aplica_prueba:
            session_args["subscription_data"] = {
                "trial_period_days": 14
            }

        # 3. Crear sesión de pago (Checkout)
        checkout_session = stripe.checkout.Session.create(**session_args)

        return {"url_checkout": checkout_session.url}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al crear intento de suscripción: {e}")