from app.services import db

def check_for_updates_logic(client_version: str):
    """
    Orquesta la lógica para verificar si existe una actualización.
    """
    # 1. Llama a la función del servicio para obtener los datos de la BD
    latest_version_info = db.get_latest_active_version()

    # 2. Si no hay una versión activa en la BD, es un problema
    if not latest_version_info:
        # Devolvemos un código de error y un mensaje
        return {"status": "error", "message": "No active version configured on server."}

    # 3. Comparamos la versión del cliente con la de la BD
    if client_version == latest_version_info["version"]:
        # Si son iguales, no hay actualización
        return {"status": "up-to-date"}
    else:
        # Si son diferentes, hay una actualización y devolvemos la información
        return {"status": "update-available", "data": latest_version_info}