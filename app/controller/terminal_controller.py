# app/controller/terminal_controller.py
from fastapi import HTTPException
from app.services.db import (get_terminales_por_cuenta, crear_terminal, 
                             actualizar_sucursal_de_terminal, actualizar_contadores_suscripcion)
from app.controller import sucursal_controller # Necesario para llamar al controlador de sucursales
from app.services import security # Para crear el nuevo token
from app.services.models import TerminalCreate, AsignarTerminalRequest, CrearSucursalYAsignarRequest, Token


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

def migrar_terminal_a_sucursal(request_data: AsignarTerminalRequest, current_user: dict):
    """Mueve una terminal a otra sucursal y actualiza contadores."""
    exito = actualizar_sucursal_de_terminal(
        id_terminal=request_data.id_terminal_origen,
        id_sucursal_nueva=request_data.id_sucursal_destino
    )
    if not exito:
        raise HTTPException(status_code=500, detail="No se pudo actualizar la sucursal de la terminal en la BD.")
    
    # Actualizamos los contadores para reflejar el cambio
    actualizar_contadores_suscripcion(current_user['id'])
    return {"status": "ok", "message": "Terminal migrada exitosamente."}

def crear_sucursal_y_asignar_terminal(request_data: CrearSucursalYAsignarRequest, current_user: dict):
    """Orquesta la creación de una sucursal y la asignación de una terminal."""
    # 1. Crear la nueva sucursal (reutilizando la lógica existente)
    sucursal_modelo_creacion = sucursal_controller.SucursalCreate(nombre=request_data.nombre_nueva_sucursal)
    nueva_sucursal = sucursal_controller.registrar_nueva_sucursal(sucursal_modelo_creacion, current_user)
    
    # 2. Asignar la terminal a la sucursal recién creada
    exito_asignacion = actualizar_sucursal_de_terminal(
        id_terminal=request_data.id_terminal_origen,
        id_sucursal_nueva=nueva_sucursal['id']
    )
    if not exito_asignacion:
        raise HTTPException(status_code=500, detail="La sucursal se creó pero no se pudo asignar la terminal.")
        
    # 3. Actualizar contadores
    actualizar_contadores_suscripcion(current_user['id'])
    
    # 4. Crear un nuevo token para que el cliente inicie sesión inmediatamente
    access_token = security.crear_access_token(data=current_user)
    
    return Token(access_token=access_token, token_type="bearer", id_terminal=request_data.id_terminal_origen)