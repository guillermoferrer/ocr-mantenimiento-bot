import os
import io
from flask import Flask, request
import telegram
from google.cloud import vision
from google.oauth2 import service_account
import gspread
from oauth2client.service_account import ServiceAccountCredentials

app = Flask(__name__)

# Telegram
TOKEN = '7351770793:AAGGoRdDZWEiqgB0-jMJPFrL7YVYdAXJ1bE'
bot = telegram.Bot(token=TOKEN)

# Google Vision
import json
import os

google_creds_json = os.environ.get("GOOGLE_CREDS")
info = json.loads(google_creds_json)
credentials = service_account.Credentials.from_service_account_info(info)
vision_client = vision.ImageAnnotatorClient(credentials=credentials)

# Google Sheets
scope = ['https://spreadsheets.google.com/feeds','https://www.googleapis.com/auth/drive']
sheet_creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
gc = gspread.authorize(sheet_creds)
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

            # Enviar a Google Vision
            image = vision.Image(content=content)
            response = vision_client.document_text_detection(image=image, image_context={"language_hints": ["es"]})

            if response.error.message:
                bot.send_message(chat_id=update.message.chat_id, text="❌ Error OCR: " + response.error.message)
                return "Error", 500

            texto = response.full_text_annotation.text

            # Procesar líneas de texto que contengan tareas
            tareas = []
            for linea in texto.split("\n"):
                if any(palabra in linea.lower() for palabra in ["sí", "no"]):
                    tareas.append(linea)

            # Registrar en hoja
            for t in tareas:
                datos = t.split()
                if len(datos) >= 6:
                    fecha = update.message.date.strftime('%d/%m/%Y')
                    equipo = datos[1]
                    tarea = " ".join(datos[2:-3])
                    frecuencia = datos[-3]
                    realizado = datos[-2]
                    puntuacion = datos[-1]
                    sheet.append_row([fecha, equipo, tarea, frecuencia, realizado, puntuacion])

            bot.send_message(chat_id=update.message.chat_id,
                             text=f"✅ Procesado con éxito.\nTareas registradas: {len(tareas)}")
        return "OK"
    except Exception as e:
        bot.send_message(chat_id=update.message.chat_id,
                         text="❌ Error procesando: " + str(e))
        return "Error", 500
