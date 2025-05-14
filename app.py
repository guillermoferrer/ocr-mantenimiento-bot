from flask import Flask, request
import requests
import os
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
from google.oauth2 import service_account
from google.cloud import vision

app = Flask(__name__)

# Autenticación con Google Sheets
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds_dict = json.loads(os.environ["GOOGLE_CREDS"])
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
client = gspread.authorize(creds)
sheet = client.open_by_key("14yj5AFl6gdUs7bL2OKc6GLIhho-XDoJrHZ-eNCgAevs").worksheet("Historial")

# Cliente Vision API
vision_creds = service_account.Credentials.from_service_account_info(creds_dict)
vision_client = vision.ImageAnnotatorClient(credentials=vision_creds)

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")

@app.route("/", methods=["GET"])
def home():
    return "Bot activo y escuchando ✅", 200

def descargar_imagen(file_id):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getFile?file_id={file_id}"
    file_path = requests.get(url).json()["result"]["file_path"]
    file_url = f"https://api.telegram.org/file/bot{TELEGRAM_TOKEN}/{file_path}"
    return requests.get(file_url).content

@app.route("/", methods=["POST"])
def webhook():
    data = request.get_json()
    if "message" in data and "photo" in data["message"]:
        chat_id = data["message"]["chat"]["id"]
        photo = data["message"]["photo"][-1]
        file_id = photo["file_id"]
        imagen_bytes = descargar_imagen(file_id)

        image = vision.Image(content=imagen_bytes)
        response = vision_client.text_detection(image=image)
        texto = response.text_annotations[0].description if response.text_annotations else ""

        hoy = datetime.today().strftime('%Y-%m-%d')
        tareas_registradas = 0

        for linea in texto.splitlines():
            partes = linea.lower().split()
            if any(palabra in partes for palabra in ["sí", "no"]):
                if len(partes) >= 5:
                    equipo = partes[1] if len(partes) > 1 else "Desconocido"
                    tarea = partes[2] if len(partes) > 2 else "Sin nombre"
                    realizado = "Sí" if "sí" in partes else "No"
                    sheet.append_row([hoy, equipo.capitalize(), tarea.capitalize(), "OCR", realizado])
                    tareas_registradas += 1

        mensaje = f"✅ Procesado con éxito.\nTareas registradas: {tareas_registradas}"
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                      data={"chat_id": chat_id, "text": mensaje})
    return "OK", 200
