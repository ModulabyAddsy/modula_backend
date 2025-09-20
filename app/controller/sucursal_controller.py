# app/controller/sucursal_controller.py
from fastapi import HTTPException
from app.services.db import crear_nueva_sucursal, get_sucursales_por_cuenta, guardar_red_autorizada
from app.services.cloud.setup_empresa_cloud import crear_estructura_sucursal
from app.services.models import SucursalCreate

def registrar_nueva_sucursal(sucursal_data: SucursalCreate, current_user: dict):
    """
    Orquesta la creación de una nueva sucursal:
    1. Llama a la BD para crear el registro y obtener la ruta_cloud.
    2. Llama al servicio de la nube para crear la carpeta.
    """
    # Extraer datos del token de usuario
    id_cuenta = current_user.get('id')
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
        # En un escenario más avanzado, aquí podrías revertir la creación en la BD.
        # Por ahora, lanzamos un error informando del estado inconsistente.
        raise HTTPException(status_code=500, detail="La sucursal se creó en la BD, pero falló la creación de su carpeta en la nube.")

    return nueva_sucursal

def get_mis_sucursales(current_user: dict):
    """Obtiene las sucursales del usuario actualmente autenticado."""
    id_cuenta = current_user.get('id')
    return get_sucursales_por_cuenta(id_cuenta)

def anclar_red_a_sucursal(id_sucursal: int, data, current_user: dict):
    # Aquí llamarías a una función en tu capa de base de datos
    # que inserte los datos de la red en la nueva tabla 'redes_autorizadas'
    guardar_red_autorizada(id_sucursal, data.gateway_mac, data.ssid)
    return {"status": "ok", "message": "Red anclada a la sucursal exitosamente."}