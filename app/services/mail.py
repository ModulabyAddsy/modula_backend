# mail.py
# Envío de correos de verificación por SMTP usando Gmail

import smtplib
import os
from dotenv import load_dotenv
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

load_dotenv()

EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASS = os.getenv("EMAIL_PASS")

def enviar_correo_verificacion(destinatario, nombre_usuario, token):
    """
    Envía un correo con botón de verificación usando SMTP de Gmail.
    """
    asunto = "Verifica tu cuenta Addsy 🚀"
    enlace = f"https://modula.com/verificar-cuenta?token={token}"

    # HTML personalizado con botón
    cuerpo_html = f"""
    <html>
    <body style="font-family: Arial, sans-serif;">
        <h2>👋 ¡Hola {nombre_usuario}!</h2>
        <p>Gracias por registrarte en <strong>Addsy</strong>.</p>
        <p>Para continuar, verifica tu cuenta haciendo clic en el botón:</p>
        <a href="{enlace}" style="
            background-color: #007acc;
            color: white;
            padding: 12px 20px;
            text-decoration: none;
            border-radius: 5px;
            display: inline-block;
            margin-top: 10px;
        ">Verificar cuenta</a>
        <p style="margin-top: 30px; font-size: 12px; color: gray;">
            Este enlace expirará en 20 minutos. Si no fuiste tú, puedes ignorar este mensaje.
        </p>
    </body>
    </html>
    """

    # Configurar mensaje
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