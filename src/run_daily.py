"""
run_daily.py
============
Orquestador del pipeline diario. Encadena las etapas:
    1. Descargar el JSON del mapa Agromet -> condiciones actuales (tablero de
       inicio) + metadata geográfica (región, lat, lon) de las 47 estaciones.
    2. Extraer datos horarios de Agromet (últimos ~37 días) para las 47.
    3. Calcular las ocho enfermedades.
    4. Generar el artefacto HTML bilingüe (vista de 7 días).

FUENTE DE DATOS: red Agromet/INIA (acceso directo, sin vilab). Decisión tomada
el 2026-07-14: se privilegia la cobertura nacional (47 estaciones) y la
temperatura de suelo (TS00/TS10, que mejora Sclerotinia) por sobre las
estaciones propias de vilab. NOTA: las estaciones San Rafael, Chocalán y
Placilla no existen en Agromet; sus proxies son Panguilemo (EXT-156) y
El Auquil (EXT-992). Si el pronóstico no calza con lo observado en terreno,
revisar este punto primero.

Se ejecuta automáticamente cada mañana desde GitHub Actions.
También puede correrse a mano:  python3 src/run_daily.py

© 2026 Winston Colvin — South Pacific Seeds Chile
Versión 2.0 · 2026-07-14
"""

import os
import sys
import json
import traceback
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from disease_models import compute_all       # noqa: E402
from build_artifact import build             # noqa: E402

# Ventana de visualización (días) y colchón de extracción.
# El colchón extra (FETCH_DAYS - DISPLAY_DAYS = 30 días) garantiza que los
# modelos acumulativos tengan su historia completa hacia atrás en TODOS los
# días visibles, no solo en los más recientes.
DISPLAY_DAYS = 7
FETCH_DAYS = 37


def main():
    print(f'[{datetime.now():%Y-%m-%d %H:%M}] Iniciando pipeline diario SPS ...')
    out_dir = os.path.join(os.path.dirname(HERE), 'output')
    os.makedirs(out_dir, exist_ok=True)

    # --- 1. Tablero de condiciones + metadata geográfica ---
    # Una sola descarga del JSON del mapa sirve para ambos fines.
    tablero_res, station_meta = None, {}
    try:
        from agromet_tablero import tablero, metadata_estaciones
        print('1/4 Descargando condiciones actuales y metadata (mapa Agromet) ...')
        tablero_res = tablero()          # por defecto: las 47 de SPS Chile
        station_meta = metadata_estaciones(tablero_res)
        print(f'    {len(tablero_res.get("estaciones", {}))} estaciones en el tablero, '
              f'{len(station_meta)} con metadata')
        # Publicar también el JSON, por si se quiere consumir aparte
        with open(os.path.join(out_dir, 'condiciones.json'), 'w', encoding='utf-8') as f:
            json.dump(tablero_res, f, ensure_ascii=False, indent=1)
    except Exception:
        # El tablero es complementario: si falla, el pronóstico igual se genera.
        print('ADVERTENCIA: no se pudo obtener el tablero/metadata:')
        traceback.print_exc()
        tablero_res = None

    # --- 2. Extracción horaria ---
    try:
        from agromet_extractor import extract_all, AGROMET_ID
        print(f'2/4 Extrayendo datos horarios de Agromet ({len(AGROMET_ID)} estaciones) ...')
        station_dfs = extract_all(days=FETCH_DAYS)
    except SystemExit:
        raise
    except Exception:
        print('ERROR en la extracción de Agromet:')
        traceback.print_exc()
        sys.exit(1)

    if not station_dfs:
        print('ERROR: la extracción no devolvió ninguna estación con datos.')
        sys.exit(1)
    print(f'    {len(station_dfs)} estaciones con datos horarios')

    # --- 3. Cálculo ---
    print('3/4 Calculando las ocho enfermedades ...')
    results = compute_all(station_dfs, window_days=DISPLAY_DAYS,
                          station_meta=station_meta)

    # --- 4. Generación del artefacto ---
    print('4/4 Generando el artefacto HTML bilingüe ...')
    name2id = (tablero_res or {}).get('name2id') or {}
    out = build(results,
                out_path=os.path.join(out_dir, 'index.html'),
                tablero=tablero_res,
                name2id=name2id)

    print(f'OK -> {out}')
    print(f'[{datetime.now():%Y-%m-%d %H:%M}] Pipeline completado.')


if __name__ == '__main__':
    main()
