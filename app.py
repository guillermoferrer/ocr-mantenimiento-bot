import os
import io
import json
from flask import Flask, request
import telegram
from google.cloud import vision
from google.oauth2 import service_account
import gspread
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

app = Flask(__name__)

# Telegram
TOKEN = os.environ.get("TELEGRAM_TOKEN")
bot = telegram.Bot(token=TOKEN)

# Google Vision API
google_creds_json = os.environ.get("GOOGLE_CREDS")
info = json.loads(google_creds_json)
credentials = service_account.Credentials.from_service_account_info(info)
vision_client = vision.ImageAnnotatorClient(credentials=credentials)

# Google Sheets
scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
gc = gspread.authorize(credentials.with_scopes(scope))
sheet = gc.open("Listado Mantenimiento Semanal").worksheet("Historial")

@app.route('/', methods=['GET'])
def home():
    return "OCR activo."

@app.route('/', methods=['POST'])
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
            response = vision_client.document_text_detection(
                image=image,
                image_context={"language_hints": ["es"]}
            )

            if response.error.message:
                bot.send_message(chat_id=update.message.chat.id,
                                 text="❌ Error OCR: " + response.error.message)
                return "Error", 500

            texto = response.full_text_annotation.text
            lineas = texto.split('\n')

            tareas = []
            for linea in lineas:
                if any(s in linea.lower() for s in ['sí', 'si', 'no']):
                    partes = linea.split()
                    if len(partes) >= 3 and partes[-2].lower() in ['sí', 'si', 'no']:
                        puntuacion = partes[-1]
                        realizado = partes[-2]
                        frecuencia = partes[-3] if len(partes) > 3 else "No identificada"
                        tarea = " ".join(partes[2:-3]) if len(partes) > 5 else "Tarea no clara"
                        equipo = partes[1] if len(partes) > 1 else "Equipo desconocido"
                        fecha = update.message.date.strftime('%d/%m/%Y')
                        tareas.append([fecha, equipo, tarea, frecuencia, realizado.upper(), puntuacion])

            for tarea in tareas:
                sheet.append_row(tarea)

            bot.send_message(chat_id=update.message.chat.id,
                             text=f"✅ Procesado con éxito.\nTareas registradas: {len(tareas)}")
        return "OK"
    except Exception as e:
        bot.send_message(chat_id=update.message.chat.id,
                         text="❌ Error procesando: " + str(e))
        return "Error", 500
