from fastapi import FastAPI
from contextlib import asynccontextmanager
from cloud.setup_empresa_cloud import inicializar_estructura_sucursal

empresa_id = "PRUEBA_A005"
sucursal_id = "SUC01"

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🔁 Ejecutando inicialización en lifespan de FastAPI")
    inicializar_estructura_sucursal(empresa_id, sucursal_id)
    yield

app = FastAPI(lifespan=lifespan)

@app.get("/test-inicializacion")
async def test_inicializacion():
    print("🔧 Ejecutando test-inicializacion desde Render")
    inicializar_estructura_sucursal(empresa_id, sucursal_id)
    return {"mensaje": "Inicialización ejecutada manualmente de forma correcta"}

@app.get("/")
def read_root():
    return {"message": "Modula backend activo 🚀"}