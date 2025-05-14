from flask import Flask, request
import requests
import os
import base64
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
from io import BytesIO
from google.oauth2 import service_account
from google.cloud import vision

app = Flask(__name__)

# Configuración de Google Sheets
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds_dict = json.loads(os.environ["GOOGLE_CREDS"])
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
client = gspread.authorize(creds)
sheet = client.open_by_key("14yj5AFl6gdUs7bL2OKc6GLIhho-XDoJrHZ-eNCgAevs").worksheet("Historial")

# Configuración de Vision
vision_creds = service_account.Credentials.from_service_account_info(creds_dict)
vision_client = vision.ImageAnnotatorClient(credentials=vision_creds)

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")

@app.route("/", methods=["GET"])
def home():
    return "Bot activo ✅", 200

def descargar_imagen(file_id):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getFile?file_id={file_id}"
    file_path = requests.get(url).json()["result"]["file_path"]
    file_url = f"https://api.telegram.org/file/bot{TELEGRAM_TOKEN}/{file_path}"
    img_data = requests.get(file_url).content
    return img_data

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
        for linea in texto.splitlines():
            if "-" in linea and ("sí" in linea.lower() or "no" in linea.lower()):
                partes = linea.split("-")
                tarea = partes[0].strip()
                realizado = "Sí" if "sí" in linea.lower() else "No"
                sheet.append_row([hoy, "OCR", tarea, "OCR", realizado])

        requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                      data={"chat_id": chat_id, "text": "✅ Imagen procesada con Google OCR y registrada."})
    return "OK", 200
