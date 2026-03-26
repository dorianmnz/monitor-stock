import os
import json
import requests
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime
import re
from concurrent.futures import ThreadPoolExecutor

# --- CONFIGURACIÓN FIREBASE ---
if 'FIREBASE_KEY' in os.environ:
    cred = credentials.Certificate(json.loads(os.environ['FIREBASE_KEY']))
else:
    cred = credentials.Certificate('serviceAccountKey.json')

if not firebase_admin._apps:
    firebase_admin.initialize_app(cred)

db = firestore.client()
doc_ref = db.collection('config').document('shared')

TOKEN = os.environ.get('TG_TOKEN')
CHAT_ID = os.environ.get('TG_CHAT_ID')

def send_telegram(mensaje):
    if not TOKEN or not CHAT_ID: return
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": CHAT_ID, "text": mensaje, "parse_mode": "HTML"}, timeout=10)

PRODUCTS = [
    {"id":"parka", "name":"Parka Corriente", "url":"https://mercadoamericano.cl/parka-corriente-invierno"},
    {"id":"jeans", "name":"Blue Jeans Corriente", "url":"https://mercadoamericano.cl/blue-jeans-corriente-toda-temporada"},
    {"id":"casaca", "name":"Casaca Corriente", "url":"https://mercadoamericano.cl/casaca-corriente-invierno"},
    {"id":"polera", "name":"Polera Manga Larga", "url":"https://mercadoamericano.cl/polera-manga-larga-corriente-invierno"},
    {"id":"buzo", "name":"Buzo Corriente", "url":"https://mercadoamericano.cl/buzo-hombre-mujer-corriente-toda-temporada"},
    {"id":"franela", "name":"Camisa Franela", "url":"https://mercadoamericano.cl/camisa-lana-franela-corriente-invierno"},
    {"id":"polpolar", "name":"Polar Corriente", "url":"https://mercadoamericano.cl/poleron-polar-corriente-invierno"},
    {"id":"poleron", "name":"Polerón Canguro", "url":"https://mercadoamericano.cl/poleron-canguro-corriente-toda-temporada"},
    {"id":"paso", "name":"Paso Invierno", "url":"https://mercadoamericano.cl/paso-corriente-invierno"},
    {"id":"sweater", "name":"Sweater Algodón", "url":"https://mercadoamericano.cl/sweater-algodon-corriente-toda-temporada"},
    {"id":"camisa", "name":"Camisa Manga Larga", "url":"https://mercadoamericano.cl/camisa-manga-larga-corriente-toda-temporada"},
    {"id":"blusa", "name":"Blusa Manga Larga", "url":"https://mercadoamericano.cl/blusa-manga-larga-extra-especial-toda-temporada"},
    {"id":"polcorta", "name":"Polera Manga Corta", "url":"https://mercadoamericano.cl/polera-manga-corta-corriente-verano"},
    {"id":"ski", "name":"Ropa Ski Corriente", "url":"https://mercadoamericano.cl/ropa-ski-corriente-invierno"},
    {"id":"paso_v", "name":"Paso Verano", "url":"https://mercadoamericano.cl/paso-corriente-verano"},
    {"id":"short", "name":"Short Corriente", "url":"https://mercadoamericano.cl/pantalon-corto-deportivo-corriente-verano"},
    {"id":"vestido", "name":"Vestido Especial", "url":"https://mercadoamericano.cl/vestido-especial-verano"},
    {"id":"bebe", "name":"Ropa Cama Bebé", "url":"https://mercadoamericano.cl/ropa-cama-bebe-corriente-toda-temporada"}
]

def fetch_status(p, old_stocks):
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        res = requests.get(p['url'], headers=headers, timeout=15)
        html = res.text
        status = "unavailable"
        if "schema.org/InStock" in html and "Agotado" not in html: status = "available"
        return p['id'], status, p['name'], p['url']
    except:
        return p['id'], old_stocks.get(p['id'], "unavailable"), p['name'], p['url']

def check_stock():
    doc = doc_ref.get()
    data = doc.to_dict() if doc.exists else {}
    
    # Lógica del botón de prueba
    if data.get('test_trigger') is True:
        send_telegram("🧪 <b>PRUEBA DE CONEXIÓN</b>\nHas presionado el botón desde la web con éxito.")
        doc_ref.update({'test_trigger': False})

    alerts = data.get('alerts', {})
    old_stocks = data.get('estados_stock', {})
    new_stocks = {}

    with ThreadPoolExecutor(max_workers=15) as ex:
        results = list(ex.map(lambda p: fetch_status(p, old_stocks), PRODUCTS))

    for p_id, status, p_name, p_url in results:
        new_stocks[p_id] = status
        if status == "available" and old_stocks.get(p_id) != "available" and alerts.get(p_id) is True:
            send_telegram(f"🛍️ <b>STOCK DETECTADO</b>\n📦 {p_name}\n🔗 <a href='{p_url}'>COMPRAR</a>")

    doc_ref.set({'estados_stock': new_stocks, 'last_run': datetime.now().isoformat()}, merge=True)

if __name__ == "__main__":
    check_stock()
