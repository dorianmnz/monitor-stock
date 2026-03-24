import requests
import re
import json
import os
import time
import random
from datetime import datetime
import firebase_admin
from firebase_admin import credentials, firestore

# --- CONFIGURACIÓN ---
TG_TOKEN = os.environ.get('TG_TOKEN')
TG_CHAT_ID = os.environ.get('TG_CHAT_ID')

# Inicializar Firebase (Asegúrate de que serviceAccountKey.json esté en el repo)
if not firebase_admin._apps:
    cred = credentials.Certificate("serviceAccountKey.json")
    firebase_admin.initialize_app(cred)

db = firestore.client()
doc_ref = db.collection('config').document('shared')

PRODUCTS = [
    {'id': 'parka',    'name': 'Parka Corriente Invierno',            'url': 'https://mercadoamericano.cl/parka-corriente-invierno'},
    {'id': 'jeans',    'name': 'Blue Jeans Corriente',                'url': 'https://mercadoamericano.cl/blue-jeans-corriente-toda-temporada'},
    {'id': 'casaca',   'name': 'Casaca Corriente Invierno',           'url': 'https://mercadoamericano.cl/casaca-corriente-invierno'},
    {'id': 'buzo',     'name': 'Buzo Corriente',                      'url': 'https://mercadoamericano.cl/buzo-hombre-mujer-corriente-toda-temporada'},
    {'id': 'poleron',  'name': 'Poleron Canguro Corriente',           'url': 'https://mercadoamericano.cl/poleron-canguro-corriente-toda-temporada'},
    {'id': 'paso',     'name': 'Paso Corriente Invierno',             'url': 'https://mercadoamericano.cl/paso-corriente-invierno'},
    {'id': 'polera',   'name': 'Polera Manga Larga Hombre Corriente', 'url': 'https://mercadoamericano.cl/polera-manga-larga-corriente-invierno'},
    {'id': 'sweater',  'name': 'Sweater Algodon Corriente',           'url': 'https://mercadoamericano.cl/sweater-algodon-corriente-toda-temporada'},
    {'id': 'camisa',   'name': 'Camisa Manga Larga Corriente',        'url': 'https://mercadoamericano.cl/camisa-manga-larga-corriente-toda-temporada'},
    {'id': 'franela',  'name': 'Camisa Franela Corriente',            'url': 'https://mercadoamericano.cl/camisa-lana-franela-corriente-invierno'},
    {'id': 'blusa',    'name': 'Blusa Manga Larga Extra Corriente',   'url': 'https://mercadoamericano.cl/blusa-manga-larga-extra-especial-toda-temporada'},
    {'id': 'polcorta', 'name': 'Polera Hombre Manga Corta Corriente', 'url': 'https://mercadoamericano.cl/polera-manga-corta-corriente-verano'},
    {'id': 'polpolar', 'name': 'Poleron Polar Corriente',             'url': 'https://mercadoamericano.cl/poleron-polar-corriente-invierno'},
]

UA_LIST = [
    'Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1',
    'Mozilla/5.0 (Linux; Android 14; SM-S928B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.6261.105 Mobile Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
]

def send_telegram(text):
    if not text or text == ".": return
    try:
        url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
        payload = {'chat_id': TG_CHAT_ID, 'text': text, 'parse_mode': 'Markdown', 'disable_web_page_preview': True}
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f'Error Telegram: {e}')

def is_available(html):
    # Tu lógica original de detección (JSON-LD + Strings)
    blocks = re.findall(r'<script[^>]*application/ld\+json[^>]*>([\s\S]*?)</script>', html, re.IGNORECASE)
    for block in blocks:
        try:
            j = json.loads(block)
            candidates = []
            if isinstance(j.get('availability'), str): candidates.append(j['availability'])
            offers = j.get('offers')
            if isinstance(offers, dict): candidates.append(offers.get('availability', ''))
            elif isinstance(offers, list):
                for o in offers:
                    if isinstance(o, dict): candidates.append(o.get('availability', ''))
            for a in candidates:
                if 'InStock' in a: return True
                if 'OutOfStock' in a: return False
        except: pass
    
    if 'schema.org/InStock' in html or 'Comprar ahora' in html: return True
    if 'Agotado' in html or 'schema.org/OutOfStock' in html: return False
    return None

def ejecutar_ciclo():
    print(f'--- Ciclo {datetime.now().strftime("%H:%M:%S")} ---')
    
    # Leer configuración desde Firebase
    try:
        fb_data = doc_ref.get().to_dict() or {}
        alertas_activas = fb_data.get('alerts', {})
        estados_stock = fb_data.get('estados_stock', {})
    except Exception as e:
        print(f"Error Firebase: {e}")
        return

    cambios = False

    for product in PRODUCTS:
        pid = product['id']
        # SOLO procesar si la campana está en ON en la web
        if alertas_activas.get(pid) is True:
            headers = {'User-Agent': random.choice(UA_LIST), 'Accept-Language': 'es-CL,es;q=0.9'}
            try:
                # Delay pequeño aleatorio para camuflaje
                time.sleep(random.uniform(0.5, 1.2))
                r = requests.get(product['url'], headers=headers, timeout=15)
                available = is_available(r.text)
                prev_status = estados_stock.get(pid)

                # Notificar SOLO si cambia de Agotado -> Disponible
                if available is True and prev_status != 'available':
                    send_telegram(f"🟢 *{product['name']}* disponible!\n\n🔗 [Comprar ahora]({product['url']})")
                    print(f"!!! Notificación enviada: {pid}")
                
                # Actualizar memoria
                nuevo_status = 'available' if available else 'unavailable'
                if prev_status != nuevo_status:
                    estados_stock[pid] = nuevo_status
                    cambios = True
            except:
                continue

    if cambios:
        doc_ref.update({'estados_stock': estados_stock})

# BUCLE DE 5 MINUTOS (Para GitHub Actions)
start_run = time.time()
while (time.time() - start_run) < 280: # Corre por 4.6 min
    ejecutar_ciclo()
    wait = random.randint(10, 20)
    print(f"Esperando {wait}s...")
    time.sleep(wait)
