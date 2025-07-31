# app/services/subscription_sync_service.py
import stripe
import os
from app.services.db import get_connection

# Cargar IDs de precios desde .env
TERMINAL_PRICE_ID = os.getenv("STRIPE_TERMINAL_PRICE_ID")
BRANCH_PRICE_ID = os.getenv("STRIPE_BRANCH_PRICE_ID")

# Límites del plan base
BASE_PLAN_TERMINALS = 1
BASE_PLAN_BRANCHES = 1

def sincronizar_suscripcion_con_db(id_cuenta: int):
    """
    Lee el estado actual de una cuenta en la BD y actualiza las cantidades
    en la suscripción de Stripe correspondiente.
    """
    conn = get_connection()
    if not conn: return

    try:
        with conn.cursor() as cur:
            # 1. Obtener datos de la BD: ID de Stripe y contadores actuales
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

            # 3. Obtener la suscripción de Stripe para ver sus ítems actuales
            subscription = stripe.Subscription.retrieve(stripe_sub_id)
            items_actuales = subscription['items']['data']
            
            items_a_actualizar = []
            
            # 4. Preparar la actualización de ítems
            for item in items_actuales:
                # Si es el ítem de terminales, actualizamos su cantidad
                if item['price']['id'] == TERMINAL_PRICE_ID:
                    items_a_actualizar.append({'id': item.id, 'quantity': terminales_adicionales})
                # Si es el ítem de sucursales, actualizamos su cantidad
                elif item['price']['id'] == BRANCH_PRICE_ID:
                    items_a_actualizar.append({'id': item.id, 'quantity': sucursales_adicionales})
            
            # 5. Ejecutar la actualización en Stripe (si hay cambios)
            if items_a_actualizar:
                stripe.Subscription.modify(
                    stripe_sub_id,
                    items=items_a_actualizar,
                    proration_behavior='create_prorations' # Para cobrar/acreditar la diferencia al instante
                )
                print(f"✅ Suscripción {stripe_sub_id} sincronizada: {terminales_adicionales} terminales, {sucursales_adicionales} sucursales.")

    except Exception as e:
        print(f"🔥🔥 ERROR sincronizando suscripción para cuenta {id_cuenta}: {e}")
    finally:
        if conn: conn.close()