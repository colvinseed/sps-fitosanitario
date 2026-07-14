# -*- coding: utf-8 -*-
"""
agromet_tablero.py · Tablero de condiciones actuales (red Agromet/INIA)
========================================================================
Versión 1.0 · 2026-07-14 · © 2026 Winston Colvin — South Pacific Seeds Chile

Baja el JSON del MAPA de agrometeorologia.cl (distinto del formulario de
extracción horaria) que trae, para TODAS las estaciones del país en una sola
petición, las condiciones del día ('hoy') y de ayer: temperatura mín/máx,
humedad, agua caída y viento.

Alimenta el tablero de inicio del sistema con "condiciones actuales". Pensado
para correr en GitHub Actions cada hora (Opción 1: actualización horaria).

MECANISMO (descubierto por ingeniería inversa):
  1. GET a https://agrometeorologia.cl/ (página principal).
  2. Extraer el token del HTML: atributo data-ts-map-tmp="tmp_XXXX".
  3. GET a https://agrometeorologia.cl/json/{token}/items-resumen.json
  4. Para cada estación, leer STACK-DAY['hoy'] (o 'ayer' si no hay 'hoy').

El token cambia con el tiempo; por eso se obtiene fresco en cada corrida desde
el HTML. No requiere login. (En entornos de red restringida puede dar 403; en
GitHub Actions funciona.)
"""

import re
import json
import time
from datetime import datetime

import requests

BASE = 'https://agrometeorologia.cl/'

# Las 47 estaciones de interés de SPS Chile. El JSON del mapa identifica cada
# estación por 'id' (numérico) MÁS 'source' (inia/ext): dos estaciones pueden
# compartir número si una es INIA y otra externa (p.ej. id 100 es La Florida/EXT
# y también San Antonio de Naltahua/INIA). Por eso la clave de cruce es
# "source:id" y no solo el número.
def _clave_agromet(idp):
    """De 'INIA-317' -> 'inia:317'; de 'EXT-156' -> 'ext:156'."""
    pref, num = idp.split('-', 1)
    fuente = 'inia' if pref.upper() == 'INIA' else 'ext'
    return f'{fuente}:{num}'

try:
    from agromet_extractor import AGROMET_ID
    # nombre -> clave 'source:id'
    ESTACIONES_SPS = {nombre: _clave_agromet(idp)
                      for nombre, idp in AGROMET_ID.items()}
except Exception:
    ESTACIONES_SPS = {}
_HEADERS = {
    'User-Agent': ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                   'AppleWebKit/537.36 (KHTML, like Gecko) '
                   'Chrome/125.0 Safari/537.36'),
    'Referer': 'https://agrometeorologia.cl/',
}


def obtener_token(session):
    """Baja la página principal y extrae el token data-ts-map-tmp."""
    r = session.get(BASE, timeout=60)
    r.raise_for_status()
    # Buscar data-ts-map-tmp="tmp_XXXX" o variantes con comillas simples
    m = re.search(r'data-ts-map-tmp=["\']?(tmp_\d+)', r.text)
    if not m:
        # fallback: cualquier tmp_ en el HTML
        m = re.search(r'(tmp_\d{6,})', r.text)
    if not m:
        raise RuntimeError('no se pudo extraer el token del HTML')
    return m.group(1)


def bajar_json_mapa(session=None, retries=3):
    """Devuelve la lista completa de estaciones del JSON del mapa."""
    s = session or requests.Session()
    s.headers.update(_HEADERS)
    for intento in range(1, retries + 1):
        try:
            token = obtener_token(s)
            url = f'{BASE}json/{token}/items-resumen.json'
            r = s.get(url, timeout=60)
            if r.status_code == 200:
                return r.json()
            if intento < retries:
                time.sleep(2 * intento)
        except (requests.RequestException, ValueError) as e:
            if intento < retries:
                time.sleep(2 * intento)
            else:
                raise
    return None


def _num(v):
    try:
        return float(v) if v is not None else None
    except (ValueError, TypeError):
        return None


def condiciones_estacion(est):
    """Extrae condiciones actuales (hoy, o ayer si no hay hoy) de una estación."""
    sd = est.get('STACK-DAY', {})
    hoy = sd.get('hoy')
    ayer = sd.get('ayer')
    actual = hoy if hoy else ayer
    if not actual:
        return None
    return {
        'id': est.get('id'),
        'nombre': est.get('nombre'),
        'comuna': est.get('comuna'),
        'region': est.get('region'),
        'institucion': est.get('institucion_sigla'),
        'estado': est.get('status_name'),
        'vigencia': 'hoy' if hoy else 'ayer',
        't_min': _num(actual.get('TA-MIN')),
        't_max': _num(actual.get('TA-MAX')),
        'hr': _num(actual.get('HR-AVG')),
        'lluvia_24h': _num(actual.get('PP-SUM')),
        'viento': _num(actual.get('VV-AVG')),
        'viento_max': _num(actual.get('VV-MAX')),
        'dir_viento': _num(actual.get('DV-AVG')),
    }


def _clave_estacion(est):
    """Clave 'source:id' de una estación del JSON del mapa."""
    src = (est.get('source') or '').lower()
    fuente = 'inia' if src == 'inia' else 'ext'
    return f"{fuente}:{est.get('id')}"


def tablero(ids_interes=None, session=None):
    """
    Devuelve un dict {clave: condiciones} para las estaciones pedidas, donde
    clave = 'source:id' (p.ej. 'inia:317', 'ext:156'). Esto evita colisiones
    entre estaciones INIA y externas que comparten número.
    ids_interes: iterable de claves 'source:id'. Si es None, usa las 47
      estaciones de SPS Chile. Para todas, pasar 'ALL'.
    Incluye marca de tiempo y el mapa nombre->clave.
    """
    data = bajar_json_mapa(session)
    if data is None:
        return {'timestamp': None, 'estaciones': {}, 'name2id': {}}
    if ids_interes == 'ALL':
        claves = None
        name2id = {}
    elif ids_interes:
        claves = set(str(i) for i in ids_interes)
        name2id = {}
    else:
        claves = set(ESTACIONES_SPS.values())
        name2id = dict(ESTACIONES_SPS)
    out = {}
    for est in data:
        clave = _clave_estacion(est)
        if claves is not None and clave not in claves:
            continue
        cond = condiciones_estacion(est)
        if cond:
            out[clave] = cond
    return {
        'timestamp': datetime.now().isoformat(timespec='minutes'),
        'estaciones': out,
        'name2id': name2id,
    }


if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser(description='Tablero de condiciones Agromet')
    ap.add_argument('--ids', nargs='*',
                    help="claves 'source:id' (ej inia:317 ext:156) o números sueltos")
    ap.add_argument('--all', action='store_true',
                    help='traer todas las estaciones de la red (no solo las 47 SPS)')
    ap.add_argument('--out', default='output/condiciones.json')
    args = ap.parse_args()

    if args.all:
        pedido = 'ALL'
    elif args.ids:
        # Permitir números sueltos: se prueban ambas fuentes (inia/ext)
        pedido = []
        for x in args.ids:
            if ':' in x:
                pedido.append(x)
            else:
                pedido += [f'inia:{x}', f'ext:{x}']
    else:
        pedido = None    # por defecto: las 47 estaciones de SPS Chile

    res = tablero(pedido)
    if res['estaciones']:
        print(f"Extraídas {len(res['estaciones'])} estaciones @ {res['timestamp']}\n")
        for clave, c in res['estaciones'].items():
            print(f"  [{clave}] {c['nombre']} ({c['comuna']}): "
                  f"{c['t_min']}–{c['t_max']}°C, HR {c['hr']}%, "
                  f"lluvia {c['lluvia_24h']}mm, viento {c['viento']} km/h "
                  f"[{c['vigencia']}, {c['estado']}]")
        import os
        os.makedirs(os.path.dirname(args.out), exist_ok=True)
        with open(args.out, 'w', encoding='utf-8') as f:
            json.dump(res, f, ensure_ascii=False, indent=1)
        print(f"\nGuardado en {args.out}")
    else:
        print('Sin datos (posible 403 por restricción de red del entorno).')
