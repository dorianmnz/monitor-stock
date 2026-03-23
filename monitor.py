import requests
import re
import json
import os
from datetime import datetime

TG_TOKEN = os.environ['TG_TOKEN']
TG_CHAT_ID = os.environ['TG_CHAT_ID']
STATE_FILE = 'state.json'
HOUR_START = 9
HOUR_END = 20

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

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'es-CL,es;q=0.9',
    'Connection': 'keep-alive',
}


def send_telegram(text):
    try:
        r = requests.post(
            'https://api.telegram.org/bot' + TG_TOKEN + '/sendMessage',
            json={'chat_id': TG_CHAT_ID, 'text': text, 'parse_mode': 'Markdown', 'disable_web_page_preview': True},
            timeout=10
        )
        print('Telegram OK' if r.ok else 'Telegram error: ' + r.text)
    except Exception as e:
        print('Telegram error: ' + str(e))


def is_available(html):
    blocks = re.findall(r'<script[^>]*application/ld\+json[^>]*>([\s\S]*?)</script>', html, re.IGNORECASE)
    for block in blocks:
        try:
            j = json.loads(block)
            candidates = []
            if isinstance(j.get('availability'), str):
                candidates.append(j['availability'])
            if isinstance(j.get('offers'), dict):
                candidates.append(j['offers'].get('availability', ''))
            elif isinstance(j.get('offers'), list):
                for o in j['offers']:
                    if isinstance(o, dict):
                        candidates.append(o.get('availability', ''))
            for a in candidates:
                if 'InStock' in a:
                    return True
                if 'OutOfStock' in a:
                    return False
        except Exception:
            pass

    if 'schema.org/InStock' in html:
        return True
    if 'schema.org/OutOfStock' in html:
        return False
    if 'InStock' in html:
        return True
    if 'OutOfStock' in html:
        return False
    if 'Agotado' in html:
        return False
    if 'Comprar ahora' in html:
        return True
    return None


def load_state():
    try:
        with open(STATE_FILE, 'r') as f:
            return json.load(f)
    except Exception:
        return {}


def save_state(state):
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2)


def in_hours():
    return True


def main():
    print('=== Monitor ' + datetime.utcnow().strftime('%Y-%m-%d %H:%M') + ' UTC ===')
    state = load_state()
    horario = in_hours()

    for product in PRODUCTS:
        pid = product['id']
        name = product['name']
        url = product['url']
        print('-> ' + name)

        try:
            r = requests.get(url, headers=HEADERS, timeout=20)
            html = r.text
            print('   HTTP ' + str(r.status_code) + ' | ' + str(len(html)) + ' chars')
        except Exception as e:
            print('   Error: ' + str(e))
            continue

        available = is_available(html)
        prev = state.get(pid, {}).get('status')
        print('   Disponible: ' + str(available) + ' | Anterior: ' + str(prev))

        if available is None:
            print('   No se pudo determinar')
            continue

        state[pid] = {'status': 'available' if available else 'unavailable'}

        if available and prev != 'available':
            print('   *** DISPONIBLE - enviando Telegram ***')
            if horario:
                send_telegram('🟢 *' + name + '* disponible!\n\n🔗 [Ver producto](' + url + ')\n\n_mercadoamericano.cl_')
            else:
                print('   Fuera de horario (9-20h Chile), no se envia')

    save_state(state)
    print('=== Listo ===')


if __name__ == '__main__':
    main()
