# app/services/mail.py
import smtplib
import os
from dotenv import load_dotenv
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

load_dotenv()

EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASS = os.getenv("EMAIL_PASS")

def enviar_correo_verificacion(destinatario, nombre_usuario, token, id_terminal, id_stripe_session):
    """
    Envía un correo con un enlace de verificación que ahora incluye todos los IDs necesarios.
    """

    # La URL correcta debe incluir el prefijo /auth/
    enlace = f"https://modula-backend.onrender.com/auth/verificar-cuenta?token={token}&id_terminal={id_terminal}&session_id={id_stripe_session}"

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