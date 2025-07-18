# utils.py
# Funciones auxiliares: bcrypt, token de verificación, generación de IDs

import bcrypt
import secrets
from datetime import datetime, timedelta

# Genera un token único para verificación con expiración de 20 minutos
def generar_token_verificacion():
    token = secrets.token_urlsafe(32)  # token aleatorio seguro
    expira = datetime.utcnow() + timedelta(minutes=20)
    return token, expira

# (Opcional) Genera un nuevo ID de empresa tipo MOD_EMP_1005 (si lo usas manualmente)
def generar_id_empresa_nuevo(numero: int) -> str:
    return f"MOD_EMP_{1000 + numero}"