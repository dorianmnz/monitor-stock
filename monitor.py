import os
import json
import requests
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime
import re

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
    if not TOKEN or not CHAT_ID:
        print("⚠️ Telegram no configurado")
        return
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": mensaje, "parse_mode": "HTML"}
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"❌ Error enviando a Telegram: {e}")

# --- LISTA DE PRODUCTOS (Mantenemos tus URLs originales) ---
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
    {"id":"polpolar", "name":"Polerón Polar", "url":"https://mercadoamericano.cl/poleron-polar-corriente-invierno"}
]

def check_stock():
    print(f"--- Escaneo Iniciado: {datetime.now().strftime('%H:%M:%S')} ---")
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}

    try:
        doc = doc_ref.get()
        data = doc.to_dict() if doc.exists else {}
        
        alerts = data.get('alerts', {})
        old_stocks = data.get('estados_stock', {})
        new_stocks = {}

        for p in PRODUCTS:
            try:
                res = requests.get(p['url'], headers=headers, timeout=20)
                html = res.text
                
                # --- LÓGICA DE DETECCIÓN POR NÚMERO EXACTO ---
                status = "unavailable" # Asumimos agotado por seguridad
                
                # Buscamos la etiqueta que me pasaste
                # Esta expresión regular busca el número que esté ANTES de la palabra "unidades"
                stock_match = re.search(r'product-stock__text-exact">(\d+)\s*unidades', html)
                
                if stock_match:
                    cantidad = int(stock_match.group(1))
                    print(f"📦 {p['name']}: {cantidad} unidades detectadas.")
                    
                    # REGLA DE ORO: Solo disponible si hay más de 0
                    if cantidad > 0:
                        status = "available"
                    else:
                        status = "unavailable"
                
                # RESPALDO: Si no encuentra el número, buscamos la palabra "Agotado"
                elif "product-message__title" in html and "Agotado" in html:
                    status = "unavailable"
                
                # RESPALDO 2: Si no hay número ni mensaje de agotado, usamos el schema estándar
                else:
                    status = "available" if "schema.org/InStock" in html else "unavailable"

                new_stocks[p['id']] = status

                # --- LÓGICA DE TELEGRAM ---
                # Solo notifica si: Cambia de Agotado -> Stock Y la campana está ON
                if status == "available" and old_stocks.get(p['id']) != "available":
                    if alerts.get(p['id']) is True:
                        msg = f"🔔 <b>¡STOCK DETECTADO!</b> 🔔\n\n<b>Producto:</b> {p['name']}\n<b>Link:</b> <a href='{p['url']}'>Ir a la tienda</a>"
                        send_telegram(msg)
                        print(f"🚀 Telegram enviado para {p['name']}")

            except Exception as e:
                print(f"⚠️ Error escaneando {p['name']}: {e}")
                new_stocks[p['id']] = old_stocks.get(p['id'], "unavailable")

        # Guardar resultados finales
        doc_ref.set({
            'estados_stock': new_stocks,
            'last_run': datetime.now().isoformat()
        }, merge=True)
        print("✅ Firebase actualizado correctamente.")

    except Exception as e:
        print(f"❌ Error crítico en el proceso: {e}")

if __name__ == "__main__":
    check_stock()
