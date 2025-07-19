# models.py
# Modelos de entrada y validación de datos para los endpoints de FastAPI

from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import date

class RegistroCuenta(BaseModel):
    """
    Modelo para registrar una nueva cuenta en Addsy.
    Contiene datos personales del usuario y datos básicos del negocio.
    """
    nombre_completo: str = Field(..., example="Juan Pérez")
    telefono: str = Field(..., example="8112345678")
    fecha_nacimiento: date = Field(..., example="1995-08-15")
    correo: EmailStr = Field(..., example="correo@ejemplo.com")
    correo_recuperacion: Optional[EmailStr] = Field(None, example="recuperacion@ejemplo.com")
    contrasena: str = Field(..., min_length=6, example="unaContraseñaSegura123")

    nombre_empresa: str = Field(..., example="Tienda Don Pepe")
    rfc: Optional[str] = Field(None, example="XAXX010101000")
    
    # 👉 NUEVO CAMPO PARA VINCULAR TERMINAL
    id_terminal: str = Field(..., example="TERMINAL_XYZ123")

class LoginData(BaseModel):
    """Modelo para recibir las credenciales de inicio de sesión."""
    correo: EmailStr
    contrasena: str

class Token(BaseModel):
    """Modelo para la respuesta del token de acceso."""
    access_token: str
    token_type: str

class TokenData(BaseModel):
    """Modelo para los datos contenidos dentro de un JWT."""
    correo: Optional[str] = None