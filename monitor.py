import os
import json
import requests
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime

# --- CONFIGURACIÓN DE SEGURIDAD ---
# Intentamos leer primero desde los Secrets de GitHub
if 'FIREBASE_KEY' in os.environ:
    try:
        # Cargamos el JSON desde la variable de entorno
        key_dict = json.loads(os.environ['FIREBASE_KEY'])
        cred = credentials.Certificate(key_dict)
        print("✅ Conectado usando GitHub Secrets.")
    except Exception as e:
        print(f"❌ Error procesando el Secret FIREBASE_KEY: {e}")
        exit(1) # Detener si el secreto está mal formado
else:
    # Si NO hay secreto (ejemplo: en tu PC local), busca el archivo
    if os.path.exists('serviceAccountKey.json'):
        cred = credentials.Certificate('serviceAccountKey.json')
        print("🏠 Conectado usando archivo local.")
    else:
        print("❌ ERROR: No se encontró FIREBASE_KEY en Secrets ni el archivo serviceAccountKey.json")
        exit(1)

# Inicializar Firebase
if not firebase_admin._apps:
    firebase_admin.initialize_app(cred)

db = firestore.client()
doc_ref = db.collection('config').document('shared')

# --- LISTA DE PRODUCTOS ---
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
    print(f"--- Inicio de escaneo: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---")
    
    # Obtener datos actuales de Firebase para comparar
    try:
        doc = doc_ref.get()
        data = doc.to_dict() if doc.exists else {}
    except Exception as e:
        print(f"❌ Error al leer Firebase: {e}")
        return

    alerts = data.get('alerts', {})
    old_stocks = data.get('estados_stock', {})
    new_stocks = {}

    for p in PRODUCTS:
        try:
            # Petición a la web con un User-Agent para evitar bloqueos
            res = requests.get(p['url'], timeout=15, headers={'User-Agent': 'Mozilla/5.0'})
            # Detectar stock (ajustado a la web de Mercado Americano)
            is_in_stock = "schema.org/InStock" in res.text or "Comprar ahora" in res.text
            status = "available" if is_in_stock else "unavailable"
            new_stocks[p['id']] = status
            
            print(f"🔎 {p['name']}: {status}")

        except Exception as e:
            print(f"⚠️ Error en {p['name']}: {e}")
            new_stocks[p['id']] = old_stocks.get(p['id'], "unavailable")

    # Guardar en Firebase (Usamos set con merge para no borrar las alertas)
    try:
        doc_ref.set({
            'estados_stock': new_stocks,
            'last_run': datetime.now().isoformat()
        }, merge=True)
        print("✅ Firebase actualizado correctamente.")
    except Exception as e:
        print(f"❌ Error al guardar en Firebase: {e}")
    
    print("--- Proceso completado ---")

if __name__ == "__main__":
    check_stock()
