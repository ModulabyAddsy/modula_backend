# app/main.py (Versión Corregida y Limpia)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Importamos los módulos de rutas de la aplicación.
from app.routes import auth, terminal, suscripcion_routes, sucursales, sync, stripe_routes, update

app = FastAPI(
    title="Modula Backend v2",
    version="2.0.0",
    description="API para el sistema de punto de venta Modula de Addsy."
)

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
app.include_router(auth.router, prefix="/api/v1/auth", tags=["Autenticación"])

# ✅ RUTAS CORREGIDAS PARA EL PREFIJO '/api/v1'
app.include_router(terminal.router, prefix="/api/v1/terminales", tags=["Terminales"])
app.include_router(suscripcion_routes.router, prefix="/api/v1/suscripciones", tags=["Suscripciones"])
app.include_router(sucursales.router, prefix="/api/v1/sucursales", tags=["Sucursales"])

# Las webhooks de Stripe se quedan sin prefijo de API
app.include_router(stripe_routes.router, tags=["Stripe Webhooks"])

# El resto de tus rutas se queda igual
app.include_router(sync.router, prefix="/api/v1/sync", tags=["Sincronización"])
app.include_router(update.router, prefix="/api/v1/update", tags=["Update"])

@app.get("/")
def root():
    """Endpoint principal para verificar que el backend está activo."""
    return {"message": "Modula backend v2 activo 🚀"}