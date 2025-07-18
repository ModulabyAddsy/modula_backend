from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes import auth  # Importas módulo de rutas
from app.services.estructura_db import verificar_y_actualizar_estructura
from app.routes import auth, terminal

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(terminal.router)

@app.on_event("startup")
async def startup_event():
    verificar_y_actualizar_estructura()

app.include_router(auth.router)  # Usamos el router definido en auth.py

@app.get("/")
def root():
    return {"message": "Modula backend activo 🚀"}