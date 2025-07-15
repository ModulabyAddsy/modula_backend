from fastapi import FastAPI
from cloud.setup_empresa_cloud import inicializar_estructura_sucursal

app = FastAPI()

@app.on_event("startup")
async def startup_event():
    empresa_id = "PRUEBA_A005"
    sucursal_id = "SUC01"
    ruta = f"{empresa_id}/{sucursal_id}/bases/.keep"
    inicializar_estructura_sucursal(empresa_id, sucursal_id)

@app.get("/test-inicializacion")
async def test_inicializacion():
    print("🔧 Ejecutando test-inicializacion desde Render")
    empresa_id = "PRUEBA_A005"
    sucursal_id = "SUC01"
    inicializar_estructura_sucursal(empresa_id, sucursal_id)
    return {"mensaje": "Inicialización ejecutada manualmente"}

@app.get("/")
def read_root():
    return {"message": "Modula backend activo 🚀"}