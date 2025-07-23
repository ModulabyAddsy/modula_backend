# app/services/security.py
import os
from datetime import datetime, timedelta, timezone
from typing import Optional
from passlib.context import CryptContext
from jose import JWTError, jwt
from dotenv import load_dotenv
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

# 👉 Se importa la función para buscar en la BD
from .db import buscar_cuenta_addsy_por_correo 

load_dotenv()

SECRET_KEY = os.getenv("JWT_SECRET_KEY", "una-clave-secreta-muy-dificil-de-adivinar")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 8 
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# 👉 Se crea el esquema de autenticación
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

def verificar_contrasena(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def hash_contrasena(password: str) -> str:
    return pwd_context.hash(password)

def crear_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

# 👉 NUEVA FUNCIÓN DE DEPENDENCIA PROTEGIDA
def get_current_active_user(token: str = Depends(oauth2_scheme)):
    """
    Decodifica el token, obtiene el ID del usuario y busca sus datos en la BD.
    Esta función se inyecta en los endpoints que requieren autenticación.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No se pudieron validar las credenciales",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        correo: str = payload.get("sub")
        if correo is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    # Busca al usuario en la base de datos
    usuario = buscar_cuenta_addsy_por_correo(correo)
    if usuario is None:
        raise credentials_exception
        
    # Verifica si la cuenta está activa
    if usuario['estatus_cuenta'] != 'verificada':
        raise HTTPException(status_code=403, detail="La cuenta no está activa")

    return usuario