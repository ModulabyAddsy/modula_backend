# app/services/subscription_sync_service.py
import stripe
import os
from app.services.db import get_connection

# Cargar IDs de precios desde .env
TERMINAL_PRICE_ID = os.getenv("STRIPE_TERMINAL_PRICE_ID")
BRANCH_PRICE_ID = os.getenv("STRIPE_BRANCH_PRICE_ID")
BASE_PLAN_PRICE_ID = os.getenv("STRIPE_BASE_PLAN_PRICE_ID")


# Límites del plan base
BASE_PLAN_TERMINALS = 1
BASE_PLAN_BRANCHES = 1

def sincronizar_suscripcion_con_db(id_cuenta: int):
    """
    Lee el estado actual de una cuenta en la BD y actualiza la suscripción de Stripe
    para que refleje las cantidades correctas de terminales y sucursales.
    """
    conn = get_connection()
    if not conn: return

    try:
        with conn.cursor() as cur:
            # 1. Obtener datos de la BD
            cur.execute(
                """
                SELECT c.id_suscripcion_stripe, s.terminales_activas, s.numero_sucursales
                FROM cuentas_addsy c
                JOIN suscripciones_software s ON c.id = s.id_cuenta_addsy
                WHERE c.id = %s;
                """,
                (id_cuenta,)
            )
            data = cur.fetchone()
            if not data or not data['id_suscripcion_stripe']:
                print(f"ℹ️ Sincronización omitida: La cuenta {id_cuenta} no tiene ID de suscripción de Stripe.")
                return

            stripe_sub_id = data['id_suscripcion_stripe']
            
            # 2. Calcular cantidades adicionales
            terminales_adicionales = max(0, data['terminales_activas'] - BASE_PLAN_TERMINALS)
            sucursales_adicionales = max(0, data['numero_sucursales'] - BASE_PLAN_BRANCHES)

            # 3. Obtener los ítems actuales de la suscripción en Stripe
            subscription_items = stripe.SubscriptionItem.list(subscription=stripe_sub_id)
            
            # Buscamos el ID del ítem del plan base para no modificarlo
            base_plan_item_id = None
            for item in subscription_items.data:
                if item.price.id == BASE_PLAN_PRICE_ID:
                    base_plan_item_id = item.id
                    break
            
            if not base_plan_item_id:
                raise Exception(f"No se encontró el ítem del plan base en la suscripción {stripe_sub_id}")

            # 4. ✅ LÓGICA CORREGIDA: Definir el estado final de los ítems
            # Le pasamos a Stripe la lista completa de ítems que la suscripción DEBERÍA tener.
            items_para_stripe = [
                # Mantenemos el plan base sin cambios
                {'id': base_plan_item_id},
                # Le decimos a Stripe que el producto "Terminal Adicional" debe tener esta cantidad
                {'price': TERMINAL_PRICE_ID, 'quantity': terminales_adicionales},
                # Y que el producto "Sucursal Adicional" debe tener esta otra cantidad
                {'price': BRANCH_PRICE_ID, 'quantity': sucursales_adicionales},
            ]

            # 5. Ejecutar la actualización en Stripe
            stripe.Subscription.modify(
                stripe_sub_id,
                items=items_para_stripe,
                proration_behavior='create_prorations'
            )
            print(f"✅ Suscripción {stripe_sub_id} sincronizada: {terminales_adicionales} terminales, {sucursales_adicionales} sucursales.")

    except Exception as e:
        print(f"🔥🔥 ERROR sincronizando suscripción para cuenta {id_cuenta}: {e}")
    finally:
        if conn: conn.close()