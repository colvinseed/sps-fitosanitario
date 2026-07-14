# -*- coding: utf-8 -*-
"""
agromet_extractor.py  ·  Extractor DIRECTO de la red Agromet/INIA
=================================================================
Versión 1.0 · 2026-07-14 · © 2026 Winston Colvin — South Pacific Seeds Chile

Accede directamente a agrometeorologia.cl (red pública INIA) para descargar
datos HORARIOS de CUALQUIER estación, sin depender de vilab ni de proyectos
amarrados. Descubierto por ingeniería inversa de la "ventana de extracción".

MECANISMO (verificado en HAR real, 2026-07-14):
  1. POST a https://agrometeorologia.cl/ con los campos del formulario:
       estaciones[]=INIA-{id}, variables[]=TA_AVG, variables[]=HR_AVG,
       variables[]=PP_SUM, intervalo=hour, desde=DD-MM-YYYY, hasta=DD-MM-YYYY,
       vista[]=csv  (+ campos auxiliares de mes/año).
  2. La RESPUESTA (HTML) contiene el nombre del CSV recién generado:
       tmp/agrometeorologia-{timestamp}.csv
  3. GET de ese CSV -> datos horarios.

VENTAJA CLAVE: cualquier estación se obtiene con su id completo (INIA-xxx o
EXT-xxx). No requiere login ni proyecto amarrado. Acceso a las ~433 estaciones.

NOTA: agrometeorologia.cl puede bloquear peticiones sin apariencia de navegador
(headers). Se envían User-Agent/Origin/Referer de navegador. Si devuelve 403,
revisar que el entorno tenga salida a internet (p.ej. GitHub Actions sí; algunos
entornos restringidos no).

VARIABLES disponibles (nombres del formulario Agromet):
  TA_AVG  temperatura aire promedio      TA_MIN / TA_MAX  min/max
  HR_AVG  humedad relativa promedio      PP_SUM  precipitación acumulada
  VV_AVG  viento promedio                RD_AVG  radiación
  TS10_AVG temperatura de suelo -10cm (¡útil para Sclerotinia!)

IDs de estación (de la lista oficial vilab / JSON Agromet). El id que usa la
ventana de extracción es el id interno de Agromet ('INIA-{id}'):
  Peor es Nada = INIA-317   (verificado en HAR)
  Para las demás, capturar el id interno desde la ventana de extracción de
  Agromet (seleccionar la estación y mirar el valor 'INIA-xxx' del formulario).
"""

import re
import time
from datetime import datetime, timedelta
from io import StringIO

import pandas as pd
import requests

BASE = 'https://agrometeorologia.cl/'

# Mapa nombre -> id COMPLETO de Agromet (con prefijo). Editable por el usuario.
# Prefijos: 'INIA-' (estaciones propias INIA) o 'EXT-' (externas: DMC, ARAUCO,
# CEAZA, COLUN, AGRICHILE, FDF, MMA-DMC, etc.). El prefijo es OBLIGATORIO.
# ---------------------------------------------------------------------------
# 47 ESTACIONES VALIDADAS (2026-07-14): cada una devolvió datos horarios reales.
# Cobertura: Coquimbo a Los Lagos, con foco en las zonas productivas de SPS
# Chile (Maule, O'Higgins, Metropolitana, Ñuble).
# NOTA: las 4 estaciones de la red VDCH-INIA (Pencahue, Villa Seca, Calleuque,
# Los Lingues) usan prefijo INIA- (no EXT-), pese a ser convenio VDCH: Agromet
# las clasifica bajo INIA porque INIA participa en esa red.
# ---------------------------------------------------------------------------
AGROMET_ID = {
    # --- Coquimbo ---
    'Illapel':                    'EXT-5',
    'Aeródromo La Florida':       'EXT-100',
    'Escuela Agrícola Ovalle':    'EXT-101',
    # --- Valparaíso ---
    'La Cruz':                    'INIA-51',
    'Liceo Agrícola Quillota':    'EXT-1029',
    # --- Metropolitana ---
    'El Asiento (Alhué)':         'INIA-210',
    'Los Tilos (Buin)':           'INIA-6',
    'Valdivia de Paine (Buin)':   'INIA-321',
    'Aeródromo Curacaví':         'EXT-150',
    'San Antonio de Naltahua':    'INIA-100',
    'Chorrillos (Lampa)':         'INIA-314',
    'Chorombo Hacienda':          'EXT-141',
    'Talagante':                  'EXT-118',
    # --- O'Higgins ---
    'Peor es Nada (Chimbarongo)': 'INIA-317',
    'Liceo Jean Buchanan (Peumo)':'INIA-228',
    'Nilahue - La Quebrada':      'EXT-155',
    'El Arenal (Q. Tilcoco)':     'INIA-163',
    'Rayentué (Rengo)':           'INIA-303',
    'El Tambo (San Vicente)':     'INIA-52',
    'Calleuque (Peralillo)':      'INIA-334',   # VDCH-INIA
    'Los Lingues (San Fernando)': 'INIA-329',   # VDCH-INIA
    # --- Maule ---
    'Cauquenes':                  'INIA-46',
    'Sauzal (Cauquenes)':         'INIA-11',
    'Chanco':                     'INIA-22',
    'Hualañé':                    'EXT-983',
    'Escuela de Artillería (Linares)': 'EXT-974',
    'Santa Amada (Linares)':      'INIA-136',
    'Parral':                     'EXT-960',
    'El Auquil (Pelarco)':        'EXT-992',
    'Pencahue':                   'INIA-333',   # VDCH-INIA
    'Villa Seca (Retiro)':        'INIA-327',   # VDCH-INIA
    'San Clemente':               'INIA-135',
    'Panguilemo (Talca)':         'EXT-156',
    'Talca':                      'EXT-982',
    'Teno':                       'EXT-1031',
    'Villa Alegre':               'EXT-977',
    # --- Ñuble ---
    "Aeródromo Gral. B. O'Higgins (Chillán)": 'EXT-157',
    'Quilamapu (Chillán)':        'INIA-351',
    'Navidad (El Carmen)':        'INIA-73',
    'Centro Experimental Arroz (San Carlos)': 'INIA-139',
    'Yungay':                     'INIA-49',
    # --- Biobío ---
    'Aeródromo María Dolores (Los Ángeles)': 'EXT-229',
    'Liceo Agrícola El Huertón (Los Ángeles)': 'EXT-162',
    # --- La Araucanía ---
    'El Vergel (Angol)':          'INIA-237',
    'San Sebastián (Perquenco)':  'INIA-235',
    # --- Los Ríos / Los Lagos ---
    'Ignao (Río Bueno)':          'EXT-1023',
    'Adolfo Matthei (Osorno)':    'EXT-76',
}

# Variables a pedir (las que consume el motor de enfermedades).
# TS00_AVG = temperatura de suelo en SUPERFICIE (0 cm); TS10_AVG = a -10 cm.
# Ambas alimentan las dos variantes del modelo de Sclerotinia (la germinación
# carpogénica de esclerocios ocurre en la capa superficial del suelo).
VARIABLES = ('TA_AVG', 'HR_AVG', 'PP_SUM', 'TS00_AVG', 'TS10_AVG')

_HEADERS = {
    'User-Agent': ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                   'AppleWebKit/537.36 (KHTML, like Gecko) '
                   'Chrome/125.0 Safari/537.36'),
    'Origin': 'https://agrometeorologia.cl',
    'Referer': 'https://agrometeorologia.cl/',
    'Accept': 'text/html,application/xhtml+xml',
}


def _build_payload(estacion_id, desde, hasta, variables=VARIABLES):
    """Arma la lista de tuplas del formulario (permite claves repetidas).
    estacion_id debe incluir el prefijo completo: 'INIA-317', 'EXT-156', etc.
    (INIA = estaciones propias INIA; EXT = externas: DMC, ARAUCO, CEAZA...)."""
    data = [('estaciones[]', str(estacion_id))]
    for v in variables:
        data.append(('variables[]', v))
    data += [
        ('intervalo', 'hour'),
        ('desde', desde),
        ('hasta', hasta),
        ('month_desde', '1'), ('month_hasta', '1'),
        ('yearMonth_desde', '2026'), ('yearMonth_hasta', '2026'),
        ('year_desde', '2026-01-01'), ('year_hasta', '2026-12-31'),
        ('vista[]', 'csv'),
    ]
    return data


def fetch_csv(estacion_id, desde, hasta, variables=VARIABLES, session=None, retries=3):
    """
    Ejecuta el POST + descarga del CSV para una estación.
    estacion_id: int/str del id interno Agromet (ej 317).
    desde, hasta: 'DD-MM-YYYY'.
    Devuelve el texto del CSV, o None si falla.
    """
    s = session or requests.Session()
    s.headers.update(_HEADERS)
    payload = _build_payload(estacion_id, desde, hasta, variables)
    for intento in range(1, retries + 1):
        try:
            r = s.post(BASE, data=payload, timeout=90)
            if r.status_code != 200:
                if intento < retries:
                    time.sleep(2 * intento)
                    continue
                raise RuntimeError(f'POST devolvió {r.status_code}')
            m = re.search(r'tmp/agrometeorologia-\d+\.csv', r.text)
            if not m:
                if intento < retries:
                    time.sleep(2 * intento)
                    continue
                raise RuntimeError('no se encontró el CSV en la respuesta del POST')
            csv_url = BASE + m.group(0)
            r2 = s.get(csv_url, timeout=90)
            if r2.status_code == 200 and r2.text:
                return r2.text
            if intento < retries:
                time.sleep(2 * intento)
        except requests.RequestException:
            if intento < retries:
                time.sleep(2 * intento)
            else:
                raise
    return None


def parse_csv(texto):
    """
    Parsea el CSV de Agromet a un DataFrame ancho con columnas
    Date, T, HR, P (las que el motor de enfermedades espera).
    El CSV tiene ~5 líneas de metadata, luego una fila de encabezados y datos.
    Cada variable pedida agrega DOS columnas: valor y '% de datos'.
    """
    lineas = texto.split('\n')
    hdr_idx = next((i for i, l in enumerate(lineas) if 'Tiempo' in l), None)
    if hdr_idx is None:
        raise ValueError('no se encontró el encabezado "Tiempo" en el CSV')
    df = pd.read_csv(StringIO('\n'.join(lineas[hdr_idx:])), quotechar='"')

    # Primera columna = tiempo. Las demás alternan valor / '% de datos'.
    cols = list(df.columns)
    out = pd.DataFrame()
    out['Date'] = pd.to_datetime(df[cols[0]], format='%d-%m-%Y %H:%M', errors='coerce')

    # Mapear por nombre de columna (robusto ante orden de variables)
    def find_col(keyword, exclude=None):
        for c in cols[1:]:
            cl = c.lower()
            if 'de datos' in cl:
                continue
            if keyword.lower() in cl and (exclude is None or exclude.lower() not in cl):
                return c
        return None

    # Temperatura de AIRE: contiene 'temperatura' pero NO 'suelo'
    c_t = find_col('Temperatura', exclude='suelo')
    c_hr = find_col('Humedad')
    c_pp = find_col('Precipita')
    # Temperaturas de SUELO: superficie (0 cm) y -10 cm. En el CSV de Agromet
    # ambas dicen 'Temperatura de suelo'; se distinguen por la profundidad en el
    # nombre de la columna (0 / superficie vs 10). Se detectan de forma robusta.
    c_ts0 = None    # superficie (TS00)
    c_ts10 = None   # -10 cm (TS10)
    for c in cols[1:]:
        cl = c.lower()
        if 'de datos' in cl:
            continue
        if 'temperatura' in cl and 'suelo' in cl:
            # distinguir por profundidad indicada en el encabezado
            if '10' in cl:
                c_ts10 = c
            elif ('0' in cl or 'superf' in cl):
                c_ts0 = c
            elif c_ts0 is None:
                c_ts0 = c    # primera de suelo sin marca clara -> superficie

    out['T'] = pd.to_numeric(df[c_t], errors='coerce') if c_t else pd.NA
    out['HR'] = pd.to_numeric(df[c_hr], errors='coerce') if c_hr else pd.NA
    out['P'] = pd.to_numeric(df[c_pp], errors='coerce') if c_pp else 0.0
    if c_ts0:
        out['Tsoil0'] = pd.to_numeric(df[c_ts0], errors='coerce')   # superficie
    if c_ts10:
        out['Tsoil10'] = pd.to_numeric(df[c_ts10], errors='coerce')  # -10 cm

    out = out.dropna(subset=['Date']).sort_values('Date').reset_index(drop=True)
    cols_out = ['Date', 'T', 'P', 'HR']
    if c_ts0:  cols_out.append('Tsoil0')
    if c_ts10: cols_out.append('Tsoil10')
    return out[cols_out]


def fetch_station(estacion_id, desde, hasta, **kw):
    """POST + parse en un paso. Devuelve DataFrame(Date,T,P,HR) o None."""
    texto = fetch_csv(estacion_id, desde, hasta, **kw)
    if not texto:
        return None
    return parse_csv(texto)


def extract_all(days=37, stations=None):
    """
    Extrae las estaciones indicadas (dict nombre->id) para los últimos `days`.
    Por defecto usa AGROMET_ID. Devuelve dict {nombre: DataFrame}.
    """
    stations = stations or AGROMET_ID
    end = datetime.now()
    start = end - timedelta(days=days)
    desde, hasta = start.strftime('%d-%m-%Y'), end.strftime('%d-%m-%Y')
    session = requests.Session()
    out = {}
    for nombre, sid in stations.items():
        print(f'  Agromet: extrayendo {nombre} ({sid}) ...', flush=True)
        df = fetch_station(sid, desde, hasta, session=session)
        if df is not None and len(df):
            out[nombre] = df
        else:
            print(f'    ADVERTENCIA: {nombre} no devolvió datos')
    return out


if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser(description='Extractor directo Agromet/INIA')
    ap.add_argument('--id', default='INIA-317',
                    help='id completo con prefijo (ej INIA-317, EXT-156)')
    ap.add_argument('--days', type=int, default=10)
    args = ap.parse_args()
    end = datetime.now(); start = end - timedelta(days=args.days)
    df = fetch_station(args.id, start.strftime('%d-%m-%Y'), end.strftime('%d-%m-%Y'))
    if df is not None:
        print(df.head(20).to_string())
        print(f'\nTotal filas: {len(df)}')
    else:
        print('Sin datos (posible 403 por restricción de red del entorno).')
