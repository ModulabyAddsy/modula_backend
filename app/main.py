# app/main.py
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# 👉 Importamos los nuevos enrutadores
from app.routes import auth, terminal, stripe_routes, suscripcion_routes

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
app.include_router(stripe_routes.router, prefix="/stripe", tags=["Stripe Webhooks"])
# 👉 Añadimos el nuevo grupo de rutas para suscripciones
app.include_router(suscripcion_routes.router, prefix="/suscripciones", tags=["Suscripciones"])


@app.get("/")
def root():
    return {"message": "Modula backend v2 activo 🚀"}