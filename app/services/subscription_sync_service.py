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
    Ahora maneja la adición y actualización de ítems correctamente.
    """
    conn = get_connection()
    if not conn: return
    try:
        with conn.cursor() as cur:
            # 1. Obtener datos de la BD
            cur.execute(
                "SELECT c.id_suscripcion_stripe, s.terminales_activas, s.numero_sucursales FROM cuentas_addsy c JOIN suscripciones_software s ON c.id = s.id_cuenta_addsy WHERE c.id = %s;",
                (id_cuenta,)
            )
            data = cur.fetchone()
            if not data or not data['id_suscripcion_stripe']:
                return

            stripe_sub_id = data['id_suscripcion_stripe']
            
            # 2. Calcular cantidades adicionales
            terminales_adicionales = max(0, data['terminales_activas'] - BASE_PLAN_TERMINALS)
            sucursales_adicionales = max(0, data['numero_sucursales'] - BASE_PLAN_BRANCHES)

            # 3. Obtener los ítems actuales de la suscripción
            subscription_items = stripe.SubscriptionItem.list(subscription=stripe_sub_id)
            
            items_a_actualizar = []
            terminal_item_existente_id = None
            sucursal_item_existente_id = None

            # Buscamos si ya existen ítems para terminales o sucursales
            for item in subscription_items.data:
                if item.price.id == TERMINAL_PRICE_ID:
                    terminal_item_existente_id = item.id
                elif item.price.id == BRANCH_PRICE_ID:
                    sucursal_item_existente_id = item.id

            # 4. ✅ LÓGICA CORREGIDA: Construir la lista de cambios
            # Para Terminales:
            if terminal_item_existente_id:
                # Si ya existe, solo actualizamos la cantidad
                items_a_actualizar.append({'id': terminal_item_existente_id, 'quantity': terminales_adicionales})
            elif terminales_adicionales > 0:
                # Si no existe y debe haber, lo añadimos
                items_a_actualizar.append({'price': TERMINAL_PRICE_ID, 'quantity': terminales_adicionales})

            # Para Sucursales:
            if sucursal_item_existente_id:
                # Si ya existe, solo actualizamos la cantidad
                items_a_actualizar.append({'id': sucursal_item_existente_id, 'quantity': sucursales_adicionales})
            elif sucursales_adicionales > 0:
                # Si no existe y debe haber, lo añadimos
                items_a_actualizar.append({'price': BRANCH_PRICE_ID, 'quantity': sucursales_adicionales})
            
            # 5. Ejecutar la actualización en Stripe (si hay cambios)
            if items_a_actualizar:
                stripe.Subscription.modify(
                    stripe_sub_id,
                    items=items_a_actualizar,
                    proration_behavior='create_prorations'
                )
                print(f"✅ Suscripción {stripe_sub_id} sincronizada.")

    except Exception as e:
        print(f"🔥🔥 ERROR sincronizando suscripción para cuenta {id_cuenta}: {e}")
    finally:
        if conn: conn.close()