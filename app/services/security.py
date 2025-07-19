# app/services/security.py
import os
from datetime import datetime, timedelta, timezone
from typing import Optional
from passlib.context import CryptContext
from jose import JWTError, jwt
from dotenv import load_dotenv

load_dotenv()

# --- CONFIGURACIÓN DE SEGURIDAD ---
# Clave secreta para firmar los tokens. ¡Debe ser secreta y compleja!
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "una-clave-secreta-muy-dificil-de-adivinar")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 8  # El token durará 8 horas

# Contexto para el hasheo de contraseñas
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# --- FUNCIONES DE CONTRASEÑA ---
def verificar_contrasena(plain_password: str, hashed_password: str) -> bool:
    """Verifica una contraseña plana contra su versión hasheada."""
    return pwd_context.verify(plain_password, hashed_password)

def hash_contrasena(password: str) -> str:
    """Hashea una contraseña para guardarla de forma segura."""
    return pwd_context.hash(password)


# --- FUNCIONES DE JWT ---
def crear_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Crea un nuevo JSON Web Token (JWT)."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def decodificar_access_token(token: str):
    """Decodifica un token para obtener los datos (payload)."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None