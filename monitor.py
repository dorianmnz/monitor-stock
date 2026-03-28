import os
import json
import requests
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime
import re
from concurrent.futures import ThreadPoolExecutor

# --- CONFIGURACIÓN DE SEGURIDAD (FIREBASE) ---
# Intentamos usar la variable de entorno primero, si no, buscamos el archivo local
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

# --- CONFIGURACIÓN TELEGRAM (MEMORIA ACTUALIZADA) ---
TOKEN = "8287364225:AAHcJQh1Ms3fK13jrTwgjbJE1u35SpLQFeo"
CHAT_ID = "5461350867"

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
        print(f"❌ Error Telegram: {e}")

# --- LISTA DE PRODUCTOS (18 ÍTEMS) ---
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

def fetch_product_status(product, old_stocks):
    p_id = product['id']
    p_url = product['url']
    p_name = product['name']
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    try:
        resp = requests.get(p_url, headers=headers, timeout=15)
        html = resp.text
        
        # Lógica de detección de stock basada en la estructura del sitio
        is_unavailable = "Agotado" in html or "unavailable" in html.lower() or "out of stock" in html.lower()
        
        # Si no encontramos rastro de "Agotado", asumimos que hay stock
        status = "unavailable" if is_unavailable else "available"
        return p_id, status, p_name, p_url
        
    except Exception as e:
        print(f"⚠️ Error al conectar con {p_name}: {e}")
        # En caso de error de conexión, mantenemos el estado anterior para evitar falsas alarmas
        return p_id, old_stocks.get(p_id, "unavailable"), p_name, p_url

def check_stock():
    print(f"--- Escaneo Paralelo: {datetime.now().strftime('%H:%M:%S')} ---")
    try:
        doc = doc_ref.get()
        data = doc.to_dict() if doc.exists else {}
        alerts = data.get('alerts', {})
        old_stocks = data.get('estados_stock', {})
        new_stocks = {}

        # Ejecución en paralelo para máxima velocidad (15 hilos)
        with ThreadPoolExecutor(max_workers=15) as executor:
            results = list(executor.map(lambda p: fetch_product_status(p, old_stocks), PRODUCTS))

        for p_id, status, p_name, p_url in results:
            new_stocks[p_id] = status
            
            # Solo notificamos si el producto PASA de Agotado a Disponible
            if status == "available" and old_stocks.get(p_id) != "available":
                # Y solo si el usuario tiene la campana encendida en la web
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

        # Guardamos los resultados finales en Firebase
        doc_ref.set({
            'estados_stock': new_stocks,
            'last_run': datetime.now().isoformat()
        }, merge=True)
        
        print("✅ Firebase actualizado correctamente.")

    except Exception as e:
        print(f"❌ Error crítico en check_stock: {e}")

if __name__ == "__main__":
    check_stock()
