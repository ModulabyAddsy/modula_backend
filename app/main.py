# main.py
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# --- Importaciones Corregidas ---
# Importamos los enrutadores (endpoints) de la aplicación.
# 'stripe_routes' ahora contiene el webhook.
from app.routes import auth, terminal, stripe_routes

# Importamos las funciones que se ejecutarán al iniciar el servidor.
from app.services.db import crear_tabla_usuarios
from app.services.estructura_db import verificar_y_actualizar_estructura

# --- Inicialización de la Aplicación ---
app = FastAPI(title="Modula Backend", version="1.1.0")

# --- Middleware de CORS ---
# Permite que tu frontend (el software Modula o la página de prueba) se comunique con el backend.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En producción, es más seguro limitar esto a dominios específicos.
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Evento de Arranque (Startup) ---
# Estas funciones se ejecutarán una sola vez cuando Render inicie el servidor.
@app.on_event("startup")
def on_startup():
    print("🚀 Servidor iniciando... Configurando base de datos.")
    # 1. Asegura que la tabla de usuarios exista.
    crear_tabla_usuarios()
    # 2. Verifica y aplica cualquier actualización a la estructura de las tablas.
    verificar_y_actualizar_estructura()
    print("✅ Base de datos lista.")

# --- Registro de Rutas (Endpoints) ---
# Aquí se conectan todos los endpoints a la aplicación principal.
app.include_router(auth.router, tags=["Autenticación"])
app.include_router(terminal.router, tags=["Terminales"])
app.include_router(stripe_routes.router, tags=["Stripe Webhooks"])


# --- Endpoints de Prueba y Verificación ---

@app.get("/")
def root():
    """Endpoint principal para verificar que el backend está activo."""
    return {"message": "Modula backend activo 🚀"}

@app.get("/verificar-stripe-keys")
def verificar_stripe_keys():
    """Endpoint de depuración para verificar que las claves de Stripe están cargadas."""
    stripe_key = os.getenv("STRIPE_SECRET_KEY")
    webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET")
    return {
        "stripe_key_cargada": bool(stripe_key),
        "webhook_secret_cargado": bool(webhook_secret),
        "stripe_key_preview": f"{stripe_key[:11]}..." if stripe_key else None,
    }