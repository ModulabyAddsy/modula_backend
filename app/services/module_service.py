# app/services/module_service.py

from .db import get_connection
# --- 1. IMPORTAMOS EL NUEVO SERVICIO DE R2 ---
from .cloud import r2_service 

def get_active_modules():
    """
    Consulta la base de datos y enriquece cada módulo con una URL de 
    descarga segura y pre-firmada desde Cloudflare R2.
    """
    conn = get_connection()
    if not conn:
        return []
    
    query = "SELECT * FROM modulos WHERE activo = TRUE ORDER BY nombre ASC;"
    
    try:
        with conn.cursor() as cur:
            cur.execute(query)
            modules = cur.fetchall()
        
        # --- 2. ENRIQUECEMOS LOS DATOS ---
        # Iteramos sobre la lista de módulos obtenida de la base de datos
        for module in modules:
            # Por cada módulo, le pedimos al servicio de R2 que genere su URL de descarga
            download_url = r2_service.generate_download_url(module['ruta_cloudflare'])
            
            # Añadimos la URL al diccionario del módulo
            module['download_url'] = download_url

        return modules
    except Exception as e:
        print(f"🔥🔥 ERROR obteniendo los módulos activos: {e}")
        return []
    finally:
        if conn:
            conn.close()