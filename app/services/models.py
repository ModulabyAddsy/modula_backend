# app/services/models.py
from __future__ import annotations
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from datetime import date, datetime
from uuid import UUID
from typing import List, Dict, Any
# --- Modelos de Autenticación (Existentes) ---

class RegistroCuenta(BaseModel):
    nombre_completo: str = Field(..., example="Juan Pérez")
    telefono: str = Field(..., example="8112345678")
    fecha_nacimiento: date = Field(..., example="1995-08-15")
    correo: EmailStr = Field(..., example="correo@ejemplo.com")
    contrasena: str = Field(..., min_length=6, example="unaContraseñaSegura123")
    nombre_empresa: str = Field(..., example="Tienda Don Pepe")
    rfc: Optional[str] = Field(None, example="XAXX010101000")
    id_terminal: str = Field(..., example="UUID_DE_LA_TERMINAL_GENERADO_EN_CLIENTE")
    claim_token: str # <-- Añadir este campo

class LoginData(BaseModel):
    correo: EmailStr
    contrasena: str

class Token(BaseModel):
    access_token: str
    token_type: str
    id_terminal: Optional[str] = None # o también 'str | None'
    
class TokenData(BaseModel):
    id_cuenta: Optional[int] = None

# --- 👉 Nuevos Modelos para Suscripciones ---

class Suscripcion(BaseModel):
    """Modelo para representar los datos de una suscripción."""
    id: int
    software_nombre: str
    estado_suscripcion: str
    fecha_vencimiento: Optional[datetime]
    espacio_total_gb: float
    espacio_usado_bytes: int

    class Config:
        orm_mode = True

# --- 👉 Nuevos Modelos para Terminales ---

class TerminalBase(BaseModel):
    """Modelo base con los campos comunes de una terminal."""
    nombre_terminal: str = Field(..., example="Caja Principal")
    id_sucursal: int = Field(..., example=1)

class TerminalCreate(TerminalBase):
    """Modelo para crear una nueva terminal."""
    id_terminal: UUID # El UUID se genera en el cliente (software Modula)

class Terminal(TerminalBase):
    """Modelo para representar los datos de una terminal ya creada."""
    id_terminal: UUID
    activa: bool
    ultima_sincronizacion: Optional[datetime]

    class Config:
        orm_mode = True
        
class SucursalInfo(BaseModel):
    """Modelo simple para listas de sucursales."""
    id: int
    nombre: str

class TerminalVerificationRequest(BaseModel):
    """Schema para la petición de verificación de terminal."""
    id_terminal: str


class TerminalVerificationResponse(BaseModel):
    """
    Schema para la respuesta de verificación.
    Ahora los campos de éxito son opcionales.
    """
    # --- Campos para respuesta exitosa (AHORA OPCIONALES) ---
    access_token: Optional[str] = None
    id_empresa: Optional[str] = None
    nombre_empresa: Optional[str] = None
    id_sucursal: Optional[int] = None
    nombre_sucursal: Optional[str] = None
    estado_suscripcion: Optional[str] = None

    # --- Campos siempre presentes o con default ---
    token_type: str = "bearer"
    status: str = Field(default="ok", example="location_mismatch")
    
    # --- Campos para manejar conflictos (opcionales por naturaleza) ---
    sugerencia_migracion: Optional[SucursalInfo] = None
    sucursales_existentes: Optional[List[SucursalInfo]] = None

    class Config:
        orm_mode = True
    
class SucursalCreate(BaseModel):
    """Modelo para la creación de una sucursal. Solo necesitamos el nombre."""
    nombre: str
    
class Sucursal(BaseModel):
    """Modelo completo de una sucursal, tal como está en la BD."""
    id: int
    id_cuenta_addsy: int
    id_suscripcion: int
    nombre: str
    fecha_creacion: datetime
    ruta_cloud: Optional[str] = None

    class Config:
        orm_mode = True # Permite que el modelo se cree desde un objeto de BD

class AsignarTerminalRequest(BaseModel):
    """Modelo para la petición de migrar o asignar una terminal."""
    id_terminal_origen: str
    id_sucursal_destino: int

class CrearSucursalYAsignarRequest(BaseModel):
    """Modelo para crear sucursal y asignarle una terminal."""
    id_terminal_origen: str
    nombre_nueva_sucursal: str
    
# Añade este nuevo modelo al final del archivo
class ActivationStatusResponse(BaseModel):
    status: str # "pending" o "complete"
    id_terminal: Optional[str] = None
    access_token: Optional[str] = None
    # Puedes añadir más info del empleado si la necesitas en el frontend
    empleado_info: Optional[dict] = None
    
class SolicitudReseteo(BaseModel):
    email: EmailStr

class EjecutarReseteo(BaseModel):
    token: str
    nueva_contrasena: str = Field(..., min_length=6)
    
class FileInfo(BaseModel):
    """Representa un archivo con su ruta y fecha de modificación."""
    key: str
    last_modified: datetime
    hash: str
    
class SyncCheckRequest(BaseModel):
    """Lo que el software cliente enviará al backend."""
    id_sucursal_actual: int
    archivos_locales: List[FileInfo]

class SyncSchemaAction(BaseModel):
    """Una acción a realizar sobre el esquema (crear un archivo nuevo)."""
    accion: str = "descargar_nuevo"
    key_origen: str # Ruta del archivo en la carpeta _modelo
    key_destino: str # Ruta donde se debe guardar en la carpeta del cliente

class SyncDataAction(BaseModel):
    """Una acción a realizar sobre los datos (subir o bajar un archivo)."""
    accion: str # "descargar_actualizacion" o "subir_actualizacion"
    key: str # Ruta del archivo a mover
    
class PlanSincronizacionResponse(BaseModel):
    """
    Define la estructura de la respuesta para el plan de sincronización inteligente.
    """
    status: str                 # ej: "plan_generado"
    id_empresa: str             # ej: "MOD_EMP_1001"
    id_sucursal_activa: int     # ej: 25
    acciones: List[Dict[str, Any]] # La lista unificada de acciones a ejecutar