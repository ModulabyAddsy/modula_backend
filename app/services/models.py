# app/services/models.py
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from datetime import date, datetime
from uuid import UUID

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
        

class TerminalVerificationRequest(BaseModel):
    """Schema para la petición de verificación de terminal."""
    id_terminal: str


class TerminalVerificationResponse(BaseModel):
    """Schema para la respuesta exitosa de verificación."""
    access_token: str
    token_type: str = "bearer"
    id_empresa: str
    nombre_empresa: str
    id_sucursal: int
    nombre_sucursal: str
    estado_suscripcion: str # <-- AÑADIR ESTA LÍNEA
    
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