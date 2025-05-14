from flask import Flask, request
import requests
import os
import pytesseract
from PIL import Image
from io import BytesIO
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

app = Flask(__name__)

# Configuración de Google Sheets
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
import json
from io import StringIO

creds_dict = json.loads(os.environ["GOOGLE_CREDS"])
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
client = gspread.authorize(creds)
sheet = client.open_by_key("14yj5AFl6gdUs7bL2OKc6GLIhho-XDoJrHZ-eNCgAevs").worksheet("Historial")

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")

def descargar_imagen(file_id):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getFile?file_id={file_id}"
    file_path = requests.get(url).json()["result"]["file_path"]
    file_url = f"https://api.telegram.org/file/bot{TELEGRAM_TOKEN}/{file_path}"
    img_data = requests.get(file_url).content
    return Image.open(BytesIO(img_data))

@app.route("/", methods=["POST"])
def webhook():
    data = request.get_json()
    if "message" in data and "photo" in data["message"]:
        chat_id = data["message"]["chat"]["id"]
        photo = data["message"]["photo"][-1]
        file_id = photo["file_id"]

        # Descargar imagen y aplicar OCR
        imagen = descargar_imagen(file_id)
        texto = pytesseract.image_to_string(imagen)

        # Registrar en hoja
        hoy = datetime.today().strftime('%Y-%m-%d')
        for linea in texto.splitlines():
            if "-" in linea and ("sí" in linea.lower() or "no" in linea.lower()):
                partes = linea.split("-")
                tarea = partes[0].strip()
                realizado = "Sí" if "sí" in linea.lower() else "No"
                sheet.append_row([hoy, "OCR", tarea, "OCR", realizado])

        requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                      data={"chat_id": chat_id, "text": "✅ Tareas procesadas y registradas en el historial."})
    return "OK", 200
