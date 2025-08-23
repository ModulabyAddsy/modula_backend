# app/services/mail.py
import smtplib
import os
from dotenv import load_dotenv
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import ssl

load_dotenv()

EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASS = os.getenv("EMAIL_PASS")

# --- Configuración leída desde .env ---
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))


def enviar_correo_verificacion(destinatario, nombre_usuario, token, id_terminal, id_stripe_session):
    """
    Envía un correo con un enlace de verificación que ahora incluye todos los IDs necesarios.
    """

    # La URL correcta debe incluir el prefijo /auth/
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
    
    mensaje = MIMEMultipart("alternative")
    mensaje["Subject"] = asunto
    mensaje["From"] = EMAIL_USER
    mensaje["To"] = destinatario
    mensaje.attach(MIMEText(cuerpo_html, "html"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(EMAIL_USER, EMAIL_PASS)
            server.sendmail(EMAIL_USER, destinatario, mensaje.as_string())
            print(f"📧 Correo enviado a {destinatario}")
    except Exception as e:
        print(f"❌ Error al enviar correo: {e}")
        
def enviar_correo_credenciales(destinatario: str, nombre_usuario: str, username_empleado: str, contrasena_temporal: str):
    """
    Envía las credenciales de acceso iniciales al propietario de la cuenta.
    """
    if not all([SMTP_SERVER, SMTP_PORT, EMAIL_USER, EMAIL_PASS]):
        print("⚠️  Faltan variables de entorno para el envío de correo. Se omitirá el envío real.")
        return

    # --- Creación del Mensaje ---
    mensaje = MIMEMultipart("alternative")
    mensaje["Subject"] = "¡Bienvenido a Modula! Tus Credenciales de Acceso"
    mensaje["From"] = f"Addsy <{EMAIL_USER}>"
    mensaje["To"] = destinatario

    # --- Contenido del Correo en formato HTML ---
    html = f"""
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

    # Adjuntar el contenido HTML al mensaje
    parte_html = MIMEText(html, "html")
    mensaje.attach(parte_html)

    # --- Envío del Correo ---
    contexto_ssl = ssl.create_default_context()
    try:
        # Usamos smtplib.SMTP para TLS, que es más común que SMTPS_SSL directo
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls(context=contexto_ssl)
            server.login(EMAIL_USER, EMAIL_PASS)
            server.sendmail(EMAIL_USER, destinatario, mensaje.as_string())
        print(f"✅ Correo de credenciales enviado exitosamente a {destinatario}.")
    except Exception as e:
        print(f"🔥🔥 ERROR al enviar correo de credenciales: {e}")
        
def enviar_correo_reseteo(destinatario: str, nombre_usuario: str, token: str):
    """
    Envía un correo con el enlace para restablecer la contraseña de la cuenta Addsy.
    """
    if not all([SMTP_SERVER, SMTP_PORT, EMAIL_USER, EMAIL_PASS]):
        print("⚠️  Faltan variables de entorno para el envío de correo. Se omitirá el envío real.")
        return

    # --- Creación del Mensaje ---
    enlace = f"https://modula-backend.onrender.com/api/v1/auth/pagina-reseteo?token={token}"
    mensaje = MIMEMultipart("alternative")
    mensaje["Subject"] = "Restablece tu contraseña de Modula"
    mensaje["From"] = f"Addsy Soporte <{EMAIL_USER}>"
    mensaje["To"] = destinatario

    # --- Contenido del Correo en formato HTML ---
    html = f"""
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
    
    parte_html = MIMEText(html, "html")
    mensaje.attach(parte_html)

    # --- Envío del Correo ---
    contexto_ssl = ssl.create_default_context()
    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls(context=contexto_ssl)
            server.login(EMAIL_USER, EMAIL_PASS)
            server.sendmail(EMAIL_USER, destinatario, mensaje.as_string())
        print(f"✅ Correo de reseteo de contraseña enviado exitosamente a {destinatario}.")
    except Exception as e:
        print(f"🔥🔥 ERROR al enviar correo de reseteo: {e}")