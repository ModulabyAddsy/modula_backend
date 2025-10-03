# app/controller/sucursal_controller.py
from fastapi import HTTPException
from app.services.db import crear_nueva_sucursal, get_sucursales_por_cuenta, guardar_red_autorizada
from app.services.cloud.setup_empresa_cloud import crear_estructura_sucursal
from app.services.models import SucursalCreate
# 👇 1. IMPORTAMOS EL SERVICIO DE SINCRONIZACIÓN
from app.services.subscription_sync_service import sincronizar_suscripcion_con_db

def registrar_nueva_sucursal(sucursal_data: SucursalCreate, current_user: dict):
    """
    Orquesta la creación de una nueva sucursal y sincroniza con Stripe.
    """
    id_cuenta = current_user.get('id') # Es más seguro usar 'id_cuenta_addsy' del token
    id_empresa_addsy = current_user.get('id_empresa_addsy')
    
    # 1. Crear en la base de datos
    nueva_sucursal = crear_nueva_sucursal(
        id_cuenta=id_cuenta,
        id_empresa_addsy=id_empresa_addsy,
        nombre_sucursal=sucursal_data.nombre
    )
    if not nueva_sucursal:
        raise HTTPException(status_code=500, detail="Error al crear la sucursal en la base de datos.")

    # 2. Crear en la nube
    exito_cloud = crear_estructura_sucursal(nueva_sucursal['ruta_cloud'])
    if not exito_cloud:
        raise HTTPException(status_code=500, detail="La sucursal se creó en la BD, pero falló la creación de su carpeta en la nube.")

    # --- 👇 3. SINCRONIZAR CON STRIPE ---
    print(f"Sucursal '{sucursal_data.nombre}' creada. Sincronizando suscripción para cuenta {id_cuenta}.")
    sincronizar_suscripcion_con_db(id_cuenta)
    
    return nueva_sucursal

def get_mis_sucursales(current_user: dict):
    """Obtiene las sucursales del usuario actualmente autenticado."""
    id_cuenta = current_user.get('id')
    return get_sucursales_por_cuenta(id_cuenta)

def anclar_red_a_sucursal(id_sucursal: int, data, current_user: dict):
    guardar_red_autorizada(id_sucursal, data.gateway_mac, data.ssid)
    return {"status": "ok", "message": "Red anclada a la sucursal exitosamente."}