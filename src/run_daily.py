"""
run_daily.py
============
Orquestador del pipeline diario. Encadena las tres etapas:
    1. Extraer datos frescos de vilab (últimos ~10 días, para cubrir la ventana de 7)
    2. Calcular las seis enfermedades
    3. Generar el artefacto HTML bilingüe (vista de 7 días)

Se ejecuta automáticamente cada mañana desde GitHub Actions.
También puede correrse a mano:  python3 src/run_daily.py

Requiere las variables de entorno VILAB_USER y VILAB_PASSWORD
(en producción provienen de GitHub Secrets).

© 2026 Winston Colvin — South Pacific Seeds Chile
Versión 1.0 · 2026-07-13
"""

import os
import sys
import traceback
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from disease_models import compute_all       # noqa: E402
from build_artifact import build             # noqa: E402

# Ventana de visualización (días) y colchón de extracción
DISPLAY_DAYS = 7
FETCH_DAYS = 10


def main():
    print(f'[{datetime.now():%Y-%m-%d %H:%M}] Iniciando pipeline diario SPS ...')

    # --- 1. Extracción ---
    try:
        from vilab_extractor import extract_all
        print('1/3 Extrayendo datos de vilab ...')
        station_dfs = extract_all(days=FETCH_DAYS)
    except SystemExit:
        raise
    except Exception:
        print('ERROR en la extracción de vilab:')
        traceback.print_exc()
        sys.exit(1)

    # --- 2. Cálculo ---
    print('2/3 Calculando las seis enfermedades ...')
    results = compute_all(station_dfs, window_days=DISPLAY_DAYS)

    # --- 3. Generación del artefacto ---
    print('3/3 Generando el artefacto HTML bilingüe ...')
    out = build(results, out_path=os.path.join(os.path.dirname(HERE), 'output', 'index.html'))

    print(f'OK -> {out}')
    print(f'[{datetime.now():%Y-%m-%d %H:%M}] Pipeline completado.')


if __name__ == '__main__':
    main()
