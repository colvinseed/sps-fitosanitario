"""
vilab_extractor.py
==================
Extractor de datos horarios desde vilab (spsc.vilab.cl) para el pronóstico diario.

Traducido del extractor v7 (que corría en el navegador) a Python de servidor.
Mecánica confirmada contra vilab real:
  - Login:  POST a /index.php/home/formulario_ingreso  con campos 'correo' y 'pass'
            (sin token CSRF).
  - Datos:  POST a /index.php/predios/clima  con usu_id, pre_id, umbral, tipo,
            tipo_grafico, inf, sup.  Respuesta JSON con {data_avg:[[ts,val],...]}.
  - Para T y HR usamos data_avg horario (tipo_grafico=2).
  - La precipitación viene acumulada; se des-acumula en disease_models.

>>> SEGURIDAD: las credenciales se leen del entorno (GitHub Secrets), NUNCA
    están en el código:  VILAB_USER, VILAB_PASSWORD, VILAB_BASE.

>>> PRE_IDS DE ESTACIONES: editables abajo en STATION_PREID. Se obtienen una vez
    desde la página de Predios de vilab (ver docs/GUIA_DESPLIEGUE.md).

© 2026 Winston Colvin — South Pacific Seeds Chile
Versión 2.0 · 2026-07-13
"""

import os
import sys
import argparse
from datetime import datetime, timedelta

import requests
import pandas as pd

# ---------------------------------------------------------------------------
# Credenciales y configuración (desde entorno — NUNCA hardcodear)
# ---------------------------------------------------------------------------
BASE = os.environ.get('VILAB_BASE', 'https://spsc.vilab.cl')
USER = os.environ.get('VILAB_USER')
PASSWORD = os.environ.get('VILAB_PASSWORD')

# Identificador de usuario en vilab. El v7 usaba usu_id=3 (constante de la plataforma).
USU_ID = int(os.environ.get('VILAB_USU_ID', '3'))

# Endpoints confirmados contra vilab
LOGIN_URL = f'{BASE}/index.php/home/formulario_ingreso'
DATA_URL = f'{BASE}/index.php/predios/clima'

# ---------------------------------------------------------------------------
# PRE_IDS DE LAS ESTACIONES  ·  EDITABLE
# ---------------------------------------------------------------------------
# Cada estación en vilab se identifica por un pre_id (id de predio representativo).
# Rellena estos valores con los que entrega el script de la guía (sección 3.3).
# Para cambiar de estaciones más adelante, edita SOLO este diccionario.
STATION_PREID = {
    'Chocalán':     4659,
    'Talagante':    4690,
    'Placilla':     4629,
    'Peor es Nada': 7515,   # NOTA: rango de pre_id distinto (75xx vs 46xx del resto)
    'San Rafael':   4634,   #       -> verificar en la primera corrida real.
}
# Capturados 2026-07-13 desde la página de Predios de vilab.
# ADVERTENCIA: los pre_id dependen de la CAMPAÑA activa en vilab. Si cambia la
# temporada, estos valores pueden dejar de ser válidos y hay que recapturarlos
# (ver docs/GUIA_DESPLIEGUE.md, sección 3.3).

# Tipos de variable en vilab (confirmados del v7)
TIPO_TEMP = 'g_clima_temperatura'
TIPO_HUM = 'g_clima_humedad'
TIPO_PRECIP = 'g_clima_precipitacion'

GRAF_HORARIO = 2   # tipo_grafico: 1=diario, 2=horario


def make_session():
    """Inicia sesión en vilab con las credenciales del entorno. Devuelve la sesión."""
    if not USER or not PASSWORD:
        sys.exit('ERROR: define VILAB_USER y VILAB_PASSWORD '
                 '(en producción provienen de GitHub Secrets).')

    s = requests.Session()
    s.headers.update({
        'User-Agent': 'SPS-Chile-DiseaseForecast/2.0',
        'X-Requested-With': 'XMLHttpRequest',
    })

    # Cargar la página de login primero (por si vilab setea alguna cookie inicial)
    try:
        s.get(f'{BASE}/index.php/home/login', timeout=30)
    except requests.RequestException:
        pass  # no es crítico

    # POST de login con los campos confirmados: 'correo' y 'pass'
    r = s.post(LOGIN_URL, data={'correo': USER, 'pass': PASSWORD}, timeout=30)
    r.raise_for_status()

    # Verificar que la sesión quedó activa: pedimos la página de predios y
    # comprobamos que NO nos redirige de vuelta al login.
    check = s.get(f'{BASE}/index.php/predios/lista', timeout=30)
    if 'formulario_ingreso' in check.text or '/home/login' in check.url:
        sys.exit('ERROR: el login en vilab falló. Revisa VILAB_USER / VILAB_PASSWORD.')

    return s


def fetch_variable(session, pre_id, tipo, inf, sup, graf=GRAF_HORARIO):
    """
    Descarga una variable (tipo) para un predio entre inf y sup (fechas 'YYYY-MM-DD').
    Devuelve la lista data_avg: [[timestamp_ms, valor], ...].
    """
    payload = {
        'usu_id': USU_ID,
        'pre_id': pre_id,
        'umbral': 0,
        'tipo': tipo,
        'tipo_grafico': graf,
        'inf': inf,
        'sup': sup,
    }
    r = session.post(DATA_URL, data=payload, timeout=60)
    r.raise_for_status()
    j = r.json()
    o = j[0] if isinstance(j, list) else j
    return (o or {}).get('data_avg', []) or []


def fetch_station(session, station, start, end):
    """
    Descarga T, HR y P horarias de una estación y las combina en un DataFrame
    con columnas Date, T, P, HR.
    """
    pre_id = STATION_PREID.get(station)
    if not pre_id:
        raise ValueError(f'Falta el pre_id de la estación "{station}". '
                         'Edita STATION_PREID en vilab_extractor.py.')

    inf = start.strftime('%Y-%m-%d')
    sup = end.strftime('%Y-%m-%d')

    temp = fetch_variable(session, pre_id, TIPO_TEMP, inf, sup)
    hum = fetch_variable(session, pre_id, TIPO_HUM, inf, sup)
    precip = fetch_variable(session, pre_id, TIPO_PRECIP, inf, sup)

    # Cada serie es [[ts_ms, val], ...]. Las unimos por timestamp.
    def to_series(arr, name):
        if not arr:
            return pd.Series(dtype=float, name=name)
        idx = pd.to_datetime([a[0] for a in arr], unit='ms', utc=True).tz_convert('America/Santiago').tz_localize(None)
        return pd.Series([a[1] for a in arr], index=idx, name=name)

    sT = to_series(temp, 'T')
    sH = to_series(hum, 'HR')
    sP = to_series(precip, 'P')

    df = pd.concat([sT, sH, sP], axis=1).reset_index()
    df.columns = ['Date', 'T', 'HR', 'P']
    df = df[['Date', 'T', 'P', 'HR']].sort_values('Date').reset_index(drop=True)
    # La des-acumulación de P se hace en disease_models.prepare_station_df().
    return df


def extract_all(days=10):
    """
    Extrae las estaciones definidas en STATION_PREID para los últimos `days` días.
    Devuelve dict {estacion: DataFrame(Date,T,P,HR)}.
    """
    session = make_session()
    end = datetime.now()
    start = end - timedelta(days=days)
    out = {}
    for st in STATION_PREID:
        print(f'  extrayendo {st} ...', flush=True)
        out[st] = fetch_station(session, st, start, end)
    return out


def main():
    ap = argparse.ArgumentParser(description='Extractor vilab -> Excel')
    ap.add_argument('--days', type=int, default=10)
    ap.add_argument('--out', default='output/clima.xlsx')
    args = ap.parse_args()

    data = extract_all(days=args.days)
    os.makedirs(os.path.dirname(args.out) or '.', exist_ok=True)
    with pd.ExcelWriter(args.out, engine='openpyxl') as w:
        for st, df in data.items():
            df.to_excel(w, sheet_name=st[:31], index=False)
    print(f'OK -> {args.out} ({len(data)} estaciones)')


if __name__ == '__main__':
    main()
