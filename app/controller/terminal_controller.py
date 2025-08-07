# app/controller/terminal_controller.py
from fastapi import HTTPException, Request
from app.services.db import (get_terminales_por_cuenta, crear_terminal, 
                             actualizar_sucursal_de_terminal, actualizar_contadores_suscripcion,
                             actualizar_ip_terminal, buscar_terminal_por_hardware_id, autorizar_nueva_ubicacion)
from app.controller import sucursal_controller
from app.services import security
from app.services.models import TerminalCreate, AsignarTerminalRequest, CrearSucursalYAsignarRequest, Token
from app.services import models
# ✅ 1. Importar la nueva función de sincronización
from app.services.subscription_sync_service import sincronizar_suscripcion_con_db
from app.services.utils import get_ip_geolocation

def get_mis_terminales(current_user: dict):
    """Obtiene las terminales del usuario actualmente autenticado."""
    id_cuenta = current_user.get('id')
    return get_terminales_por_cuenta(id_cuenta)

def registrar_nueva_terminal(terminal_data: TerminalCreate, current_user: dict, request: Request):
    """Registra una nueva terminal para la cuenta del usuario."""
    id_cuenta = current_user.get('id')
    client_ip = request.client.host
    
    # ✅ CORRECCIÓN: Pasar el 'client_ip' como tercer argumento
    nueva_terminal = crear_terminal(id_cuenta, terminal_data.dict(), client_ip)
    
    if not nueva_terminal:
        raise HTTPException(status_code=500, detail="Error al registrar la nueva terminal en la base de datos.")

    actualizar_contadores_suscripcion(id_cuenta)
    sincronizar_suscripcion_con_db(id_cuenta)
    
    return nueva_terminal

def migrar_terminal_a_sucursal(request_data: AsignarTerminalRequest, current_user: dict, request: Request):
    """Mueve una terminal a otra sucursal y actualiza contadores."""
    client_ip = request.client.host
    
    exito = actualizar_sucursal_de_terminal(
        id_terminal=request_data.id_terminal_origen,
        id_sucursal_nueva=request_data.id_sucursal_destino
    )
    if not exito:
        raise HTTPException(status_code=500, detail="No se pudo actualizar la sucursal de la terminal en la BD.")
    
    actualizar_ip_terminal(id_terminal=request_data.id_terminal_origen, ip=client_ip)
    actualizar_contadores_suscripcion(current_user['id'])
    
    # No se necesita sincronizar aquí porque el número de terminales/sucursales no cambió.
    
    # ✅ AÑADIDO: Autorizar esta nueva ubicación para la sucursal de destino
    geo_data = get_ip_geolocation(client_ip)
    autorizar_nueva_ubicacion(request_data.id_sucursal_destino, client_ip, geo_data)
    
    actualizar_contadores_suscripcion(current_user['id'])
    return {"status": "ok", "message": "Terminal migrada exitosamente."}

def crear_sucursal_y_asignar_terminal(request_data: CrearSucursalYAsignarRequest, current_user: dict, request: Request):
    """Orquesta la creación de una sucursal y la asignación de una terminal."""
    client_ip = request.client.host
    id_cuenta = current_user.get('id')

    # 1. Crear la nueva sucursal
    sucursal_modelo_creacion = sucursal_controller.SucursalCreate(nombre=request_data.nombre_nueva_sucursal)
    nueva_sucursal = sucursal_controller.registrar_nueva_sucursal(sucursal_modelo_creacion, current_user)
    
    # 2. Asignar la terminal a la sucursal recién creada
    exito_asignacion = actualizar_sucursal_de_terminal(
        id_terminal=request_data.id_terminal_origen,
        id_sucursal_nueva=nueva_sucursal['id']
    )
    if not exito_asignacion:
        raise HTTPException(status_code=500, detail="La sucursal se creó pero no se pudo asignar la terminal.")
        
    actualizar_ip_terminal(id_terminal=request_data.id_terminal_origen, ip=client_ip)

    # ✅ 3. Actualizar contadores y sincronizar con Stripe
    actualizar_contadores_suscripcion(id_cuenta)
    sincronizar_suscripcion_con_db(id_cuenta)
    
    # ✅ AÑADIDO: Autorizar esta nueva ubicación para la sucursal recién creada
    id_sucursal_nueva = nueva_sucursal['id']
    geo_data = get_ip_geolocation(client_ip)
    autorizar_nueva_ubicacion(id_sucursal_nueva, client_ip, geo_data)
    
    sincronizar_suscripcion_con_db(id_cuenta)
    
    # 4. Crear un nuevo token
    access_token_data = {
        "sub": current_user.get("sub"),
        "id": id_cuenta,
        "id_empresa_addsy": current_user.get("id_empresa_addsy")
    }
    access_token = security.crear_access_token(data=access_token_data)
    
    return Token(access_token=access_token, token_type="bearer", id_terminal=request_data.id_terminal_origen)

def buscar_terminal_por_hardware(request_data: models.TerminalVerificationRequest):
    """Busca si una terminal con un ID de hardware ya está registrada."""
    terminal = buscar_terminal_por_hardware_id(request_data.id_terminal)
    if not terminal:
        raise HTTPException(status_code=404, detail="Terminal con este ID de hardware no encontrada.")
    return terminal