# app/services/mail.py
import os
from dotenv import load_dotenv
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

load_dotenv()

# --- Nuevas variables de entorno para SendGrid ---
SENDGRID_API_KEY = os.getenv('SENDGRID_API_KEY')
MAIL_FROM_EMAIL = os.getenv('MAIL_FROM_EMAIL')

# --- Función auxiliar interna ---
def _enviar_correo(destinatario: str, asunto: str, cuerpo_html: str) -> bool:
    """
    Función auxiliar que maneja la lógica de envío de correos usando SendGrid.
    """
    if not all([SENDGRID_API_KEY, MAIL_FROM_EMAIL]):
        print("⚠️ Faltan variables de entorno (SENDGRID_API_KEY o MAIL_FROM_EMAIL). Se omitirá el envío.")
        return False

    mensaje = Mail(
        from_email=MAIL_FROM_EMAIL,
        to_emails=destinatario,
        subject=asunto,
        html_content=cuerpo_html
    )
    try:
        sendgrid_client = SendGridAPIClient(SENDGRID_API_KEY)
        response = sendgrid_client.send(mensaje)
        
        # Un código de respuesta 2xx indica éxito en la API de SendGrid
        if 200 <= response.status_code < 300:
            print(f"✅ Correo enviado a {destinatario} a través de SendGrid. Estado: {response.status_code}")
            return True
        else:
            print(f"❌ Error de SendGrid. Estado: {response.status_code}. Cuerpo: {response.body}")
            return False
    except Exception as e:
        print(f"🔥🔥 ERROR CRÍTICO al enviar correo con SendGrid: {e}")
        return False

# --- Funciones públicas ---

def enviar_correo_verificacion(destinatario, nombre_usuario, token, id_terminal, id_stripe_session):
    """
    Envía el correo de verificación de cuenta usando SendGrid.
    """
    enlace = f"https://modula-backend.onrender.com/api/v1/auth/verificar-cuenta?token={token}&id_terminal={id_terminal}&session_id={id_stripe_session}"
    asunto = "Verifica tu cuenta Addsy 🚀"
    cuerpo_html = f"""
    <html>
    <body style="font-family: Arial, sans-serif;">
        <h2>👋 ¡Hola {nombre_usuario}!</h2>
        <p>Tu pago ha sido procesado. El último paso es verificar tu cuenta para activar tu servicio.</p>
        <p>Haz clic en el siguiente botón para completar el proceso:</p>
        <a href="{enlace}" style="background-color: #007acc; color: white; padding: 12px 20px; text-decoration: none; border-radius: 5px; display: inline-block; margin-top: 10px;">
            Activar mi cuenta
        </a>
        <p style="margin-top: 30px; font-size: 12px; color: gray;">
            Este enlace expirará en 20 minutos. Si no fuiste tú, puedes ignorar este mensaje.
        </p>
    </body>
    </html>
    """
    return _enviar_correo(destinatario, asunto, cuerpo_html)

def enviar_correo_credenciales(destinatario: str, nombre_usuario: str, username_empleado: str, contrasena_temporal: str):
    """
    Envía las credenciales de acceso iniciales usando SendGrid.
    """
    asunto = "¡Bienvenido a Modula! Tus Credenciales de Acceso"
    cuerpo_html = f"""
    <html>
      <body style="font-family: Arial, sans-serif; color: #333;">
        <h2>¡Hola {nombre_usuario}, bienvenido a Modula POS!</h2>
        <p>Tu cuenta ha sido creada y activada exitosamente. Ya puedes iniciar sesión en la aplicación con tus credenciales de administrador.</p>
        <p>Por favor, guárdalas en un lugar seguro:</p>
        <div style="background-color: #f2f2f2; padding: 15px; border-radius: 5px; margin: 20px 0;">
          <p style="margin: 5px 0;"><strong>Usuario:</strong> <code style="font-size: 1.1em;">{username_empleado}</code></p>
          <p style="margin: 5px 0;"><strong>Contraseña Temporal:</strong> <code style="font-size: 1.1em;">{contrasena_temporal}</code></p>
        </div>
        <p>Por tu seguridad, el sistema te pedirá que cambies esta contraseña la primera vez que inicies sesión.</p>
        <br>
        <p>Gracias por unirte a Addsy.</p>
      </body>
    </html>
    """
    return _enviar_correo(destinatario, asunto, cuerpo_html)

def enviar_correo_reseteo(destinatario: str, nombre_usuario: str, token: str):
    """
    Envía el correo para restablecer la contraseña usando SendGrid.
    """
    enlace = f"https://modula-backend.onrender.com/api/v1/auth/pagina-reseteo?token={token}"
    asunto = "Restablece tu contraseña de Modula"
    cuerpo_html = f"""
    <html>
      <body style="font-family: Arial, sans-serif; color: #333;">
        <h2>Hola {nombre_usuario},</h2>
        <p>Recibimos una solicitud para restablecer la contraseña de tu cuenta Addsy para Modula.</p>
        <p>Si no solicitaste esto, puedes ignorar este correo. De lo contrario, haz clic en el siguiente botón para elegir una nueva contraseña:</p>
        <a href="{enlace}" style="background-color: #007acc; color: white; padding: 12px 20px; text-decoration: none; border-radius: 5px; display: inline-block; margin-top: 10px;">
            Restablecer Contraseña
        </a>
        <p style="margin-top: 30px; font-size: 12px; color: gray;">
            Este enlace expirará en 20 minutos.
        </p>
      </body>
    </html>
    """
    return _enviar_correo(destinatario, asunto, cuerpo_html)