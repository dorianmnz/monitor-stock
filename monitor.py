import os
import json
import requests
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime
import re
import random
import time
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
    # ANTI-CACHE: Agregamos un parámetro aleatorio para forzar la actualización del servidor
    cache_buster = f"{p['url']}?v={random.randint(1, 999999)}"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Cache-Control': 'no-cache, no-store, must-revalidate',
        'Pragma': 'no-cache',
        'Expires': '0'
    }
    
    try:
        res = requests.get(cache_buster, headers=headers, timeout=15)
        html = res.text
        
        # PRIORIDAD 1: El dato que encontraste en la inspección (data-label="out-of-stock")
        if 'data-label="out-of-stock"' in html:
            status = "unavailable"
        # PRIORIDAD 2: El span que dice Agotado dentro de la etiqueta product-stock
        elif re.search(r'product-stock.*?>\s*<span>Agotado</span>', html, re.IGNORECASE | re.DOTALL):
            status = "unavailable"
        # PRIORIDAD 3: Detección por conteo de unidades (si existe)
        else:
            stock_match = re.search(r'product-stock__text-exact">(\d+)\s*unidades', html)
            if stock_match:
                cantidad = int(stock_match.group(1))
                status = "available" if cantidad > 0 else "unavailable"
            else:
                # Si no hay rastro de "Agotado", verificamos si está InStock en el schema
                status = "available" if "schema.org/InStock" in html else "unavailable"
            
        return p['id'], status, p['name'], p['url']
    except Exception:
        # Si falla la conexión, mantenemos el estado previo para no alterar el monitor
        return p['id'], old_stocks.get(p['id'], "unavailable"), p['name'], p['url']

def check_stock():
    print(f"--- Escaneo Paralelo (Anti-Caché): {datetime.now().strftime('%H:%M:%S')} ---")
    try:
        doc = doc_ref.get()
        data = doc.to_dict() if doc.exists else {}
        alerts = data.get('alerts', {})
        old_stocks = data.get('estados_stock', {})
        new_stocks = {}

        # Aumentamos workers para procesar rápido las 18 peticiones
        with ThreadPoolExecutor(max_workers=18) as executor:
            results = list(executor.map(lambda p: fetch_product_status(p, old_stocks), PRODUCTS))

        for p_id, status, p_name, p_url in results:
            new_stocks[p_id] = status
            
            # Solo notifica si pasa de Agotado a Disponible
            if status == "available" and old_stocks.get(p_id) == "unavailable":
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

        # Guardar en Firebase (Esto actualiza tu monitor Liquid Glass al instante)
        doc_ref.set({
            'estados_stock': new_stocks,
            'last_run': datetime.now().isoformat()
        }, merge=True)
        print("✅ Monitor actualizado en Firebase.")

    except Exception as e:
        print(f"❌ Error General: {e}")

if __name__ == "__main__":
    check_stock()
