import os
import io
import json
from flask import Flask, request
import telegram
from google.cloud import vision
from google.oauth2 import service_account
import gspread
from datetime import datetime

app = Flask(__name__)

# Telegram token desde variables de entorno
TOKEN = os.environ.get("TOKEN")
if not TOKEN:
    raise ValueError("❌ TOKEN no está definido en las variables de entorno")
bot = telegram.Bot(token=TOKEN)

# Credenciales de Google desde GOOGLE_CREDS
google_creds_json = os.environ.get("GOOGLE_CREDS")
if not google_creds_json:
    raise ValueError("❌ GOOGLE_CREDS no está definido en las variables de entorno")
info = json.loads(google_creds_json)
credentials = service_account.Credentials.from_service_account_info(info)

# Cliente Vision
vision_client = vision.ImageAnnotatorClient(credentials=credentials)

# Cliente Sheets
gc = gspread.authorize(credentials)
sheet = gc.open("Listado Mantenimiento Semanal").worksheet("Historial")

@app.route("/", methods=["GET"])
def index():
    return "✅ OCR activo y esperando imágenes"

@app.route("/", methods=["POST"])
def webhook():
    try:
        update = telegram.Update.de_json(request.get_json(force=True), bot)

        if update.message and update.message.photo:
            file_id = update.message.photo[-1].file_id
            new_file = bot.get_file(file_id)
            file_bytes = io.BytesIO()
            new_file.download(out=file_bytes)
            content = file_bytes.getvalue()

            image = vision.Image(content=content)
            response = vision_client.document_text_detection(image=image)

            if response.error.message:
                bot.send_message(chat_id=update.message.chat_id,
                                 text="❌ Error OCR: " + response.error.message)
                return "Error", 500

            texto = response.full_text_annotation.text
            tareas = []

            for linea in texto.split("\n"):
                if any(palabra in linea.lower() for palabra in ["sí", "si", "no"]):
                    tareas.append(linea)

            fecha = update.message.date.strftime('%d/%m/%Y')
            tareas_registradas = 0

            for t in tareas:
                datos = t.split()
                if len(datos) >= 6:
                    equipo = datos[1]
                    tarea = " ".join(datos[2:-3])
                    frecuencia = datos[-3]
                    realizado = datos[-2].upper()
                    puntuacion = datos[-1]
                    sheet.append_row([fecha, equipo, tarea, frecuencia, realizado, puntuacion])
                    tareas_registradas += 1

            bot.send_message(chat_id=update.message.chat_id,
                             text=f"✅ Procesado con éxito.\nTareas registradas: {tareas_registradas}")

        return "OK", 200

    except Exception as e:
        try:
            chat_id = update.message.chat_id if update.message else None
            if chat_id:
                bot.send_message(chat_id=chat_id, text=f"❌ Error procesando: {str(e)}")
        except:
            pass
        return "Error", 500
