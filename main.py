from fastapi import FastAPI
from cloud.setup_empresa_cloud import inicializar_estructura_sucursal

app = FastAPI()

@app.on_event("startup")
def startup_event():
    empresa_id = "PRUEBA_A004"
    sucursal_id = "SUC01"
    ruta = f"{empresa_id}/{sucursal_id}/bases/.keep"
    inicializar_estructura_sucursal(empresa_id, sucursal_id)

@app.get("/")
def home():
    return {"mensaje": "Backend Modula activo en Render"}

# Este bloque es útil para desarrollo local
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=10000)