import os
import io
import json
from flask import Flask, request
import telegram
import google.cloud.vision_v1 as vision
from google.oauth2 import service_account
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

app = Flask(__name__)

# --- TELEGRAM ---
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
bot = telegram.Bot(token=TOKEN)

# --- GOOGLE VISION ---
google_creds_json = os.environ.get("GOOGLE_CREDS")
info = json.loads(google_creds_json)
credentials = service_account.Credentials.from_service_account_info(info)
vision_client = vision.ImageAnnotatorClient(credentials=credentials)

# --- GOOGLE SHEETS ---
SCOPES = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
gc = gspread.authorize(Credentials.from_service_account_info(info, scopes=SCOPES))
sheet = gc.open("Listado Mantenimiento Semanal").worksheet("Historial")


# --- FILTRADO INTELIGENTE DE TAREAS ---
def extraer_tareas(texto):
    tareas = []
    for linea in texto.split("\n"):
        linea_limpia = linea.strip().lower()
        if ("sí" in linea_limpia or "no" in linea_limpia) and any(char.isdigit() for char in linea_limpia):
            tareas.append(linea)
    return tareas


@app.route("/", methods=["GET"])
def home():
    return "OCR activo y esperando tareas."


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

            # OCR con hint en español
            image = vision.Image(content=content)
            response = vision_client.document_text_detection(
                image=image,
                image_context={"language_hints": ["es"]}
            )

            if response.error.message:
                bot.send_message(chat_id=update.message.chat.id, text="❌ Error OCR: " + response.error.message)
                return "Error OCR", 500

            texto = response.full_text_annotation.text
            tareas = extraer_tareas(texto)

            if not tareas:
                bot.send_message(chat_id=update.message.chat.id, text="🧐 No se detectaron tareas. Revisa la calidad de la imagen.")
                return "Sin tareas", 200

            tareas_registradas = 0
            for t in tareas:
                datos = t.split()
                if len(datos) >= 5:
                    try:
                        fecha = datetime.now().strftime('%d/%m/%Y')
                        equipo = datos[0]
                        tarea = " ".join(datos[1:-3])
                        frecuencia = datos[-3]
                        realizado = datos[-2]
                        puntuacion = datos[-1]
                        sheet.append_row([fecha, equipo, tarea, frecuencia, realizado, puntuacion])
                        tareas_registradas += 1
                    except Exception as e:
                        continue  # saltamos errores de fila mal formada

            bot.send_message(
                chat_id=update.message.chat.id,
                text=f"✅ Procesado con éxito.\nTareas registradas: {tareas_registradas}"
            )

        return "OK", 200

    except Exception as e:
        print("Error general:", e)
        bot.send_message(chat_id=update.message.chat.id, text="❌ Error general: " + str(e))
        return "Error", 500
