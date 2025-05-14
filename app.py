import os
import io
import json
import re
from flask import Flask, request
import telegram
from google.cloud import vision
from google.oauth2 import service_account
import gspread

app = Flask(__name__)

# Configuración del bot de Telegram desde variable de entorno
TOKEN = os.environ.get("TELEGRAM_TOKEN")
bot = telegram.Bot(token=TOKEN)

# Configuración de credenciales desde variable de entorno
google_creds_json = os.environ.get("GOOGLE_CREDS")
info = json.loads(google_creds_json)

# Crear credenciales y clientes
credentials = service_account.Credentials.from_service_account_info(info)
vision_client = vision.ImageAnnotatorClient(credentials=credentials)
scoped_credentials = credentials.with_scopes([
    'https://spreadsheets.google.com/feeds',
    'https://www.googleapis.com/auth/drive'
])
gc = gspread.authorize(scoped_credentials)
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

            # Enviar imagen a Google Vision
            image = vision.Image(content=content)
            response = vision_client.document_text_detection(image=image, image_context={"language_hints": ["es"]})

            if response.error.message:
                bot.send_message(chat_id=update.message.chat_id, text="❌ Error OCR: " + response.error.message)
                return "Error", 500

            texto = response.full_text_annotation.text
            lineas = texto.split("\n")
            tareas_registradas = 0

            for linea in lineas:
                # Buscar líneas que contengan SI/NO y puntuación al final
                if re.search(r'\b(SI|NO|Sí|si|no|sí)\b', linea, re.IGNORECASE) and re.search(r'\b\d{1,2}\b', linea):
                    partes = linea.split()
                    if len(partes) >= 6:
                        try:
                            fecha = update.message.date.strftime('%d/%m/%Y')
                            equipo = " ".join(partes[1:4])
                            tarea = " ".join(partes[4:-3])
                            frecuencia = partes[-3]
                            realizado = partes[-2].upper()
                            puntuacion = partes[-1]
                            sheet.append_row([fecha, equipo, tarea, frecuencia, realizado, puntuacion])
                            tareas_registradas += 1
                        except Exception as err:
                            print("❌ Error al registrar tarea:", err)

            bot.send_message(
                chat_id=update.message.chat_id,
                text=f"✅ Procesado con éxito.\nTareas registradas: {tareas_registradas}"
            )
        return "OK"

    except Exception as e:
        bot.send_message(
            chat_id=update.message.chat_id,
            text="❌ Error procesando: " + str(e)
        )
        return "Error", 500
