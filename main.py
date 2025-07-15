#Main.py
from cloud.setup_empresa_cloud import inicializar_estructura_sucursal

if __name__ == "__main__":
    empresa_id = "PRUEBA_A004"
    sucursal_id = "SUC01"
    ruta = f"{empresa_id}/{sucursal_id}/bases/.keep"
    inicializar_estructura_sucursal(empresa_id, sucursal_id)