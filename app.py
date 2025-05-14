import os
import io
import json
from flask import Flask, request
import telegram
from google.cloud import vision
from google.oauth2 import service_account
import gspread
from datetime import datetime

# Iniciar Flask
app = Flask(__name__)

# Configurar token de Telegram
TOKEN = os.environ.get("TELEGRAM_TOKEN")
bot = telegram.Bot(token=TOKEN)

# Leer credenciales desde variable de entorno
google_creds_json = os.environ.get("GOOGLE_CREDS")
info = json.loads(google_creds_json)

# Configurar cliente Vision
credentials = service_account.Credentials.from_service_account_info(info, scopes=[
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
])
vision_client = vision.ImageAnnotatorClient(credentials=credentials)

# Configurar cliente Sheets
gc = gspread.authorize(credentials)
sheet = gc.open("Listado Mantenimiento Semanal").worksheet("Historial")

# Ruta de prueba
@app.route('/', methods=['GET'])
def index():
    return '✅ OCR activo y funcionando.'

# Ruta Webhook
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

            # OCR con Google Vision
            image = vision.Image(content=content)
            response = vision_client.document_text_detection(
                image=image,
                image_context={"language_hints": ["es"]}
            )

            if response.error.message:
                bot.send_message(chat_id=update.message.chat_id,
                                 text="❌ Error OCR: " + response.error.message)
                return "Error", 500

            texto = response.full_text_annotation.text
            tareas = []

            # Detectar líneas con SÍ / NO
            for linea in texto.split("\n"):
                if any(palabra in linea.lower() for palabra in ["sí", "si", "no"]):
                    tareas.append(linea)

            # Registrar tareas
            tareas_registradas = 0
            fecha = update.message.date.strftime('%d/%m/%Y')

            for linea in tareas:
                datos = linea.split()
                if len(datos) >= 6:
                    equipo = datos[1]
                    tarea = " ".join(datos[2:-3])
                    frecuencia = datos[-3]
                    realizado = datos[-2].upper()
                    puntuacion = datos[-1]

                    if realizado in ["SÍ", "SI", "NO"]:
                        sheet.append_row([
                            fecha, equipo, tarea, frecuencia,
                            realizado.replace("Í", "I"), puntuacion
                        ])
                        tareas_registradas += 1

            bot.send_message(chat_id=update.message.chat_id,
                             text=f"✅ Procesado con éxito.\nTareas registradas: {tareas_registradas}")
        return "OK", 200

    except Exception as e:
        bot.send_message(chat_id=update.message.chat_id,
                         text=f"❌ Error procesando: {str(e)}")
        return "Error", 500
