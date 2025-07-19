from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes import auth, terminal, webhook_controller
from app.services.estructura_db import verificar_y_actualizar_estructura

app = FastAPI(title="Modula Backend", version="1.0.0")

# Middleware para permitir solicitudes desde cualquier origen
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En producción puedes limitar esto a tu frontend
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/verificar-stripe")
def verificar_stripe():
    import os
    return {
        "stripe_key_corta": os.getenv("STRIPE_SECRET_KEY")[:10] + "...",
        "webhook_corta": os.getenv("STRIPE_WEBHOOK_SECRET")[:10] + "..."
    }

# Cargar rutas principales
app.include_router(auth.router)
app.include_router(terminal.router)
app.include_router(webhook_controller.router)  # 👈 Webhook de Stripe

# Verificar estructura de base de datos al arrancar
@app.on_event("startup")
async def startup_event():
    print("🔄 Verificando estructura de base de datos...")
    verificar_y_actualizar_estructura()

# Ruta de prueba
@app.get("/")
def root():
    return {"message": "Modula backend activo 🚀"}