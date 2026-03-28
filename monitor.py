import os
import json
import requests
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime
import re
from concurrent.futures import ThreadPoolExecutor

# --- CONFIGURACIÓN DE SEGURIDAD (FIREBASE) ---
if 'FIREBASE_KEY' in os.environ:
    try:
        key_dict = json.loads(os.environ['FIREBASE_KEY'])
        cred = credentials.Certificate(key_dict)
    except Exception as e:
        print(f"❌ Error en Secret FIREBASE_KEY: {e}")
        exit(1)
else:
    if os.path.exists('serviceAccountKey.json'):
        cred = credentials.Certificate('serviceAccountKey.json')
    else:
        print("❌ No se encontró llave de Firebase.")
        exit(1)

if not firebase_admin._apps:
    firebase_admin.initialize_app(cred)

db = firestore.client()
doc_ref = db.collection('config').document('shared')

# --- CONFIGURACIÓN TELEGRAM ---
TOKEN = os.environ.get('TG_TOKEN')
CHAT_ID = os.environ.get('TG_CHAT_ID')

def send_telegram(mensaje):
    if not TOKEN or not CHAT_ID or len(mensaje.strip()) < 2:
        return
        
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID, 
        "text": mensaje, 
        "parse_mode": "HTML",
        "disable_web_page_preview": False 
    }
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"❌ Error enviando a Telegram: {e}")

# --- LISTA COMPLETA DE 18 PRODUCTOS ---
PRODUCTS = [
    {"id":"parka", "name":"Parka Corriente", "url":"https://mercadoamericano.cl/parka-corriente-invierno"},
    {"id":"jeans", "name":"Blue Jeans", "url":"https://mercadoamericano.cl/blue-jeans-corriente-toda-temporada"},
    {"id":"casaca", "name":"Casaca Corriente", "url":"https://mercadoamericano.cl/casaca-corriente-invierno"},
    {"id":"buzo", "name":"Buzo Corriente", "url":"https://mercadoamericano.cl/buzo-hombre-mujer-corriente-toda-temporada"},
    {"id":"poleron", "name":"Polerón Canguro", "url":"https://mercadoamericano.cl/poleron-canguro-corriente-toda-temporada"},
    {"id":"paso", "name":"Paso Corriente", "url":"https://mercadoamericano.cl/paso-corriente-invierno"},
    {"id":"polera", "name":"Polera Manga Larga", "url":"https://mercadoamericano.cl/polera-manga-larga-corriente-invierno"},
    {"id":"sweater", "name":"Sweater Algodón", "url":"https://mercadoamericano.cl/sweater-algodon-corriente-toda-temporada"},
    {"id":"camisa", "name":"Camisa Manga Larga", "url":"https://mercadoamericano.cl/camisa-manga-larga-corriente-toda-temporada"},
    {"id":"franela", "name":"Camisa Franela", "url":"https://mercadoamericano.cl/camisa-lana-franela-corriente-invierno"},
    {"id":"blusa", "name":"Blusa Manga Larga", "url":"https://mercadoamericano.cl/blusa-manga-larga-extra-especial-toda-temporada"},
    {"id":"polcorta", "name":"Polera Manga Corta", "url":"https://mercadoamericano.cl/polera-manga-corta-corriente-verano"},
    {"id":"polpolar", "name":"Polerón Polar", "url":"https://mercadoamericano.cl/poleron-polar-corriente-invierno"},
    {"id":"ski", "name":"Ropa Ski Corriente", "url":"https://mercadoamericano.cl/ropa-ski-corriente-invierno"},
    {"id":"paso_v", "name":"Paso Verano", "url":"https://mercadoamericano.cl/paso-corriente-verano"},
    {"id":"short", "name":"Short Corriente", "url":"https://mercadoamericano.cl/pantalon-corto-deportivo-corriente-verano"},
    {"id":"vestido", "name":"Vestido Especial", "url":"https://mercadoamericano.cl/vestido-especial-verano"},
    {"id":"bebe", "name":"Ropa Cama Bebé", "url":"https://mercadoamericano.cl/ropa-cama-bebe-corriente-toda-temporada"}
]

def fetch_product_status(p, old_stocks):
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
    try:
        res = requests.get(p['url'], headers=headers, timeout=15)
        html = res.text
        status = "unavailable"
        
        stock_match = re.search(r'product-stock__text-exact">(\d+)\s*unidades', html)
        if stock_match:
            cantidad = int(stock_match.group(1))
            status = "available" if cantidad > 0 else "unavailable"
        elif "product-message__title" in html and "Agotado" in html:
            status = "unavailable"
        else:
            status = "available" if "schema.org/InStock" in html else "unavailable"
            
        return p['id'], status, p['name'], p['url']
    except Exception:
        return p['id'], old_stocks.get(p['id'], "unavailable"), p['name'], p['url']

def check_stock():
    print(f"--- Escaneo Paralelo: {datetime.now().strftime('%H:%M:%S')} ---")
    try:
        doc = doc_ref.get()
        data = doc.to_dict() if doc.exists else {}
        alerts = data.get('alerts', {})
        old_stocks = data.get('estados_stock', {})
        new_stocks = {}

        with ThreadPoolExecutor(max_workers=15) as executor:
            results = list(executor.map(lambda p: fetch_product_status(p, old_stocks), PRODUCTS))

        for p_id, status, p_name, p_url in results:
            new_stocks[p_id] = status
            if status == "available" and old_stocks.get(p_id) != "available":
                if alerts.get(p_id) is True:
                    msg = (
                        f"🛍️ <b>¡STOCK DETECTADO!</b>\n"
                        f"──────────────────\n"
                        f"📦 <b>Producto:</b> {p_name}\n"
                        f"✅ <b>Estado:</b> Disponible ahora\n\n"
                        f"🔗 <a href='{p_url}'>COMPRAR AHORA</a>\n"
                        f"──────────────────"
                    )
                    send_telegram(msg)
                    print(f"🚀 Notificación enviada: {p_name}")

        doc_ref.set({
            'estados_stock': new_stocks,
            'last_run': datetime.now().isoformat()
        }, merge=True)
        print("✅ Proceso completado.")

    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    check_stock()
