# app/main.py
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Importamos los enrutadores (endpoints) de la aplicación.
from app.routes import auth, terminal, stripe_routes 

app = FastAPI(title="Modula Backend v2", version="2.0.0")

# Middleware de CORS para permitir la comunicación desde el software cliente
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Evento de Arranque (Startup) ---
# Ya no creamos tablas aquí; eso se maneja con scripts de migración para
# tener un mayor control sobre la estructura de la base de datos.
@app.on_event("startup")
def on_startup():
    print("🚀 Servidor iniciando... Conexión a la base de datos gestionada por endpoints.")
    print("✅ ¡Backend listo para recibir peticiones!")

# --- Registro de Rutas (Endpoints) ---
# Incluimos los diferentes grupos de endpoints en la aplicación principal.
app.include_router(auth.router, tags=["Autenticación"])
app.include_router(terminal.router, tags=["Terminales"])
app.include_router(stripe_routes.router, tags=["Stripe Webhooks"])

# --- Endpoints de Verificación ---

@app.get("/")
def root():
    """Endpoint principal para verificar que el backend está activo."""
    return {"message": "Modula backend v2 activo 🚀"}

@app.get("/verificar-variables")
def verificar_variables():
    """Endpoint de depuración para verificar que las variables de entorno clave están cargadas."""
    db_url = os.getenv("DATABASE_URL")
    stripe_key = os.getenv("STRIPE_SECRET_KEY")
    return {
        "database_url_cargada": bool(db_url),
        "stripe_key_cargada": bool(stripe_key),
    }
