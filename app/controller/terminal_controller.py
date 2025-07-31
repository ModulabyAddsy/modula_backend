# app/controller/terminal_controller.py
from fastapi import HTTPException
from app.services.db import (get_terminales_por_cuenta, crear_terminal, 
                             actualizar_sucursal_de_terminal, actualizar_contadores_suscripcion,actualizar_ip_terminal)
from app.controller import sucursal_controller # Necesario para llamar al controlador de sucursales
from app.services import security # Para crear el nuevo token
from app.services.models import TerminalCreate, AsignarTerminalRequest, CrearSucursalYAsignarRequest, Token
from fastapi import HTTPException, Request

def get_mis_terminales(current_user: dict):
    """Obtiene las terminales del usuario actualmente autenticado."""
    id_cuenta = current_user.get('id')
    return get_terminales_por_cuenta(id_cuenta)

def registrar_nueva_terminal(terminal_data: TerminalCreate, current_user: dict):
    """Registra una nueva terminal para la cuenta del usuario."""
    id_cuenta = current_user.get('id')
    nueva_terminal = crear_terminal(id_cuenta, terminal_data.dict())
    if not nueva_terminal:
        raise HTTPException(status_code=500, detail="Error al registrar la nueva terminal en la base de datos.")
    return nueva_terminal

def migrar_terminal_a_sucursal(request_data: AsignarTerminalRequest, current_user: dict, request: Request): # <-- Añadir request
    """Mueve una terminal a otra sucursal y actualiza contadores."""
    client_ip = request.client.host # <-- Obtener la IP real
    
    exito = actualizar_sucursal_de_terminal(
        id_terminal=request_data.id_terminal_origen,
        id_sucursal_nueva=request_data.id_sucursal_destino
    )
    if not exito:
        raise HTTPException(status_code=500, detail="No se pudo actualizar la sucursal de la terminal en la BD.")
    
    # ✅ PASO ADICIONAL: Actualizar la IP a la nueva ubicación válida
    actualizar_ip_terminal(id_terminal=request_data.id_terminal_origen, ip=client_ip)
    
    actualizar_contadores_suscripcion(current_user['id'])
    return {"status": "ok", "message": "Terminal migrada exitosamente."}

def crear_sucursal_y_asignar_terminal(request_data: CrearSucursalYAsignarRequest, current_user: dict, request: Request): # <-- Añadir request
    """Orquesta la creación de una sucursal y la asignación de una terminal."""
    client_ip = request.client.host # <-- Obtener la IP real

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
        
    # ✅ PASO ADICIONAL: Actualizar la IP a la nueva ubicación válida
    actualizar_ip_terminal(id_terminal=request_data.id_terminal_origen, ip=client_ip)

    # 3. Actualizar contadores
    actualizar_contadores_suscripcion(current_user['id'])
    
    # 4. Crear un nuevo token
    access_token_data = {
        "sub": current_user.get("sub"),
        "id": current_user.get("id"),
        "id_empresa_addsy": current_user.get("id_empresa_addsy")
    }
    access_token = security.crear_access_token(data=access_token_data)
    
    return Token(access_token=access_token, token_type="bearer", id_terminal=request_data.id_terminal_origen)