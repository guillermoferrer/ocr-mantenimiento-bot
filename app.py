import os
import io
from flask import Flask, request
import telegram
import pytesseract
from PIL import Image
import gspread
from google.oauth2.service_account import Credentials
import json
import re
from datetime import datetime

app = Flask(__name__)
TOKEN = os.environ['TELEGRAM_TOKEN']
bot = telegram.Bot(token=TOKEN)

# Configurar credenciales Google
google_creds_json = os.environ.get("GOOGLE_CREDS")
info = json.loads(google_creds_json)
creds = Credentials.from_service_account_info(info, scopes=[
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
])
gc = gspread.authorize(creds)
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
            photo = bot.get_file(file_id)
            file_bytes = io.BytesIO()
            photo.download(out=file_bytes)
            file_bytes.seek(0)
            image = Image.open(file_bytes)

            # OCR con pytesseract (español)
            texto = pytesseract.image_to_string(image, lang='spa')

            tareas_detectadas = []
            for linea in texto.split("\n"):
                if re.search(r'\b(SI|NO)\b', linea.upper()) and re.search(r'\b\d{1,2}\b', linea):
                    tareas_detectadas.append(linea)

            for t in tareas_detectadas:
                datos = t.split()
                if len(datos) >= 6:
                    fecha = update.message.date.strftime('%d/%m/%Y')
                    equipo = " ".join(datos[1:3])
                    tarea = " ".join(datos[3:-3])
                    frecuencia = datos[-3]
                    realizado = datos[-2].upper()
                    puntuacion = datos[-1]
                    sheet.append_row([fecha, equipo, tarea, frecuencia, realizado, puntuacion])

            bot.send_message(chat_id=update.message.chat.id,
                             text=f"✅ Procesado con éxito.\nTareas registradas: {len(tareas_detectadas)}")
        return "OK"
    except Exception as e:
        bot.send_message(chat_id=update.message.chat.id, text="❌ Error: " + str(e))
        return "Error", 500

