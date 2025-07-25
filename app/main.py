# app/main.py
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Importamos los enrutadores (endpoints) de la aplicación.
# <-- 1. Importar el nuevo enrutador de sucursales
from app.routes import auth, terminal, stripe_routes, suscripcion_routes, sucursales

app = FastAPI(title="Modula Backend v2", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def on_startup():
    print("🚀 Servidor iniciando...")
    print("✅ ¡Backend listo para recibir peticiones!")

# --- Registro de Rutas (Endpoints) ---
app.include_router(auth.router, prefix="/auth", tags=["Autenticación"])
app.include_router(terminal.router, prefix="/terminales", tags=["Terminales"])
app.include_router(suscripcion_routes.router, prefix="/suscripciones", tags=["Suscripciones"])

# <-- 2. Registrar el nuevo enrutador en la aplicación
# El prefijo y la etiqueta ya se definieron en el archivo 'app/routes/sucursales.py'
app.include_router(sucursales.router) 

app.include_router(stripe_routes.router, tags=["Stripe Webhooks"])


@app.get("/")
def root():
    """Endpoint principal para verificar que el backend está activo."""
    return {"message": "Modula backend v2 activo 🚀"}