"""
vilab_extractor.py
==================
Extractor de datos horarios desde la plataforma vilab (spsc.vilab.cl).
Adaptado del patrón del extractor v7 (des-acumulación de variables + salida tabular).

>>> SEGURIDAD: este script NUNCA contiene credenciales en el código. <<<
Las lee de variables de entorno, que en producción provienen de GitHub Secrets:
    VILAB_USER      -> usuario de vilab
    VILAB_PASSWORD  -> contraseña de vilab
    VILAB_BASE      -> URL base (default: https://spsc.vilab.cl)

Uso local (para pruebas), definiendo las variables en tu shell:
    export VILAB_USER="tu_usuario"
    export VILAB_PASSWORD="tu_clave"
    python3 src/vilab_extractor.py --days 10 --out output/clima.xlsx

═══════════════════════════════════════════════════════════════════════════
  PUNTOS QUE TU EQUIPO DEBE CONFIRMAR (marcados con  # >>> CONFIRMAR)
  La estructura exacta de login y de la API de datos de vilab solo es visible
  con una sesión activa. Los valores por defecto son plausibles pero deben
  verificarse contra el tráfico real de red (F12 → Network) en vilab.
═══════════════════════════════════════════════════════════════════════════

© 2026 Winston Colvin — South Pacific Seeds Chile
Versión 1.0 · 2026-07-13
"""

import os
import sys
import argparse
from datetime import datetime, timedelta

import requests
import pandas as pd

# ---------------------------------------------------------------------------
# Configuración desde entorno (NUNCA hardcodear credenciales)
# ---------------------------------------------------------------------------
BASE = os.environ.get('VILAB_BASE', 'https://spsc.vilab.cl')
USER = os.environ.get('VILAB_USER')
PASSWORD = os.environ.get('VILAB_PASSWORD')

# >>> CONFIRMAR: rutas de login y de datos de vilab.
LOGIN_URL = f'{BASE}/index.php/site/login'          # >>> CONFIRMAR endpoint de login
DATA_URL = f'{BASE}/index.php/predios/datos'         # >>> CONFIRMAR endpoint de datos horarios

# Estaciones y sus identificadores en vilab.
# >>> CONFIRMAR: los IDs internos que vilab usa para cada estación.
STATION_IDS = {
    'Chocalán':     None,   # >>> CONFIRMAR id vilab
    'Talagante':    None,   # >>> CONFIRMAR id vilab
    'Placilla':     None,   # >>> CONFIRMAR id vilab
    'Peor es Nada': None,   # >>> CONFIRMAR id vilab
    'San Rafael':   None,   # >>> CONFIRMAR id vilab
}

# Variables a extraer y si vienen acumuladas (requieren des-acumulación)
VARIABLES = {
    'T':  dict(vilab_name='temperatura', accumulated=False),   # >>> CONFIRMAR nombre
    'HR': dict(vilab_name='humedad',     accumulated=False),   # >>> CONFIRMAR nombre
    'P':  dict(vilab_name='precipitacion', accumulated=True),  # >>> CONFIRMAR: viene acumulada
}


def make_session():
    """Crea una sesión autenticada en vilab usando credenciales del entorno."""
    if not USER or not PASSWORD:
        sys.exit('ERROR: define las variables de entorno VILAB_USER y VILAB_PASSWORD '
                 '(en producción provienen de GitHub Secrets).')

    s = requests.Session()
    s.headers.update({'User-Agent': 'SPS-Chile-DiseaseForecast/1.0'})

    # Muchas plataformas PHP (Yii, por la estructura index.php/...) usan un token CSRF
    # en el formulario de login. Lo obtenemos primero.
    # >>> CONFIRMAR: nombre del campo CSRF y de los campos usuario/clave del form.
    r = s.get(LOGIN_URL, timeout=30)
    csrf = _extract_csrf(r.text)  # puede devolver None si no aplica

    payload = {
        'LoginForm[username]': USER,      # >>> CONFIRMAR nombre del campo
        'LoginForm[password]': PASSWORD,  # >>> CONFIRMAR nombre del campo
    }
    if csrf:
        payload['_csrf'] = csrf           # >>> CONFIRMAR nombre del token

    r = s.post(LOGIN_URL, data=payload, timeout=30)
    r.raise_for_status()

    # Verificación de que el login funcionó (ajustar la condición al sitio real).
    # >>> CONFIRMAR: cómo se detecta una sesión válida (redirección, cookie, texto).
    if 'login' in r.url.lower() or 'incorrect' in r.text.lower():
        sys.exit('ERROR: el login en vilab falló. Revisa credenciales y endpoints.')

    return s


def _extract_csrf(html):
    """Extrae el token CSRF de un formulario, si existe. Best-effort."""
    import re
    # patrones comunes: <input name="_csrf" value="..."> o meta csrf-token
    m = re.search(r'name="_csrf"[^>]*value="([^"]+)"', html)
    if m:
        return m.group(1)
    m = re.search(r'<meta name="csrf-token" content="([^"]+)"', html)
    return m.group(1) if m else None


def fetch_station(session, station, start, end):
    """
    Descarga los datos horarios de una estación entre start y end.
    Devuelve un DataFrame con columnas Date, T, P, HR (P ya des-acumulada).

    >>> CONFIRMAR: el formato real de la respuesta de vilab (JSON, CSV, HTML-tabla).
    Este bloque asume una respuesta JSON con registros horarios; adáptalo al real.
    """
    sid = STATION_IDS.get(station)
    params = {
        'estacion': sid,                         # >>> CONFIRMAR nombre del parámetro
        'desde': start.strftime('%Y-%m-%d'),     # >>> CONFIRMAR formato de fecha
        'hasta': end.strftime('%Y-%m-%d'),
    }
    r = session.get(DATA_URL, params=params, timeout=60)
    r.raise_for_status()

    # ---- ADAPTAR A LA RESPUESTA REAL ----
    # Caso A: respuesta JSON con lista de registros
    try:
        registros = r.json()
        df = pd.DataFrame(registros)
    except ValueError:
        # Caso B: respuesta HTML con una tabla -> usar pandas.read_html
        # df = pd.read_html(r.text)[0]
        raise RuntimeError(
            f'La respuesta de vilab para {station} no es JSON. '
            'Adapta fetch_station() al formato real (HTML/CSV).')

    # Normalizar nombres de columnas al esquema interno.
    # >>> CONFIRMAR: los nombres reales de columnas que devuelve vilab.
    rename = {
        'fecha': 'Date',
        VARIABLES['T']['vilab_name']: 'T',
        VARIABLES['HR']['vilab_name']: 'HR',
        VARIABLES['P']['vilab_name']: 'P',
    }
    df = df.rename(columns=rename)
    df = df[['Date', 'T', 'P', 'HR']].copy()
    df['Date'] = pd.to_datetime(df['Date'])
    df = df.sort_values('Date').reset_index(drop=True)

    # NOTA: la des-acumulación de P se hace en disease_models.prepare_station_df().
    # Aquí entregamos P tal como viene (acumulada) para mantener una sola fuente
    # de verdad de esa lógica. Si prefieres des-acumular aquí, descomenta:
    # if VARIABLES['P']['accumulated']:
    #     df['P'] = df['P'].diff().clip(lower=0).fillna(0)

    return df


def extract_all(days=10):
    """
    Extrae las cinco estaciones para los últimos `days` días.
    Devuelve dict {estacion: DataFrame(Date,T,P,HR)}.
    """
    session = make_session()
    end = datetime.now()
    start = end - timedelta(days=days)
    out = {}
    for st in STATION_IDS:
        print(f'  extrayendo {st} ...', flush=True)
        out[st] = fetch_station(session, st, start, end)
    return out


def main():
    ap = argparse.ArgumentParser(description='Extractor vilab -> Excel')
    ap.add_argument('--days', type=int, default=10,
                    help='días hacia atrás a extraer (default 10, para cubrir la ventana de 7)')
    ap.add_argument('--out', default='output/clima.xlsx', help='ruta de salida Excel')
    args = ap.parse_args()

    data = extract_all(days=args.days)

    # Guardar como Excel multi-hoja (una hoja por estación), formato que el
    # resto del pipeline y tu copia local pueden leer.
    os.makedirs(os.path.dirname(args.out) or '.', exist_ok=True)
    with pd.ExcelWriter(args.out, engine='openpyxl') as w:
        for st, df in data.items():
            df.to_excel(w, sheet_name=st[:31], index=False)
    print(f'OK -> {args.out} ({len(data)} estaciones)')


if __name__ == '__main__':
    main()
