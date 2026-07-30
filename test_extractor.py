"""
test_extractor.py
=================
Prueba de diagnóstico del extractor contra vilab REAL.
Úsalo la primera vez, en tu PC, para confirmar que la extracción funciona
antes de confiar en la automatización diaria.

Requiere las credenciales en el entorno:
    export VILAB_USER="tu_correo"
    export VILAB_PASSWORD="tu_clave"
    python3 test_extractor.py

Qué hace:
  1. Prueba el login.
  2. Extrae 3 días de UNA estación (San Rafael) y muestra una vista de los datos.
  3. Reporta cualquier problema de formato para poder ajustarlo.

© 2026 Winston Colvin — South Pacific Seeds Chile
"""

import sys
import os
sys.path.insert(0, 'src')
from datetime import datetime, timedelta

import vilab_extractor as ve


def main():
    print('=' * 60)
    print('DIAGNÓSTICO DEL EXTRACTOR vilab')
    print('=' * 60)

    # 1. Login
    print('\n[1] Probando login ...')
    try:
        session = ve.make_session()
        print('    ✓ Login exitoso.')
    except SystemExit as e:
        print(f'    ✗ {e}')
        return

    # 2. Extracción de una estación, pocos días
    print('\n[2] Extrayendo 3 días de San Rafael (pre_id=%s) ...' % ve.STATION_PREID['San Rafael'])
    end = datetime.now()
    start = end - timedelta(days=3)

    # Probar variable por variable para aislar problemas
    pid = ve.STATION_PREID['San Rafael']
    inf, sup = start.strftime('%Y-%m-%d'), end.strftime('%Y-%m-%d')

    for nombre, tipo in [('Temperatura', ve.TIPO_TEMP),
                         ('Humedad', ve.TIPO_HUM),
                         ('Precipitación', ve.TIPO_PRECIP)]:
        try:
            arr = ve.fetch_variable(session, pid, tipo, inf, sup)
            print(f'    {nombre:15s}: {len(arr)} registros', end='')
            if arr:
                print(f'  (primer registro: ts={arr[0][0]}, val={arr[0][1]})')
            else:
                print('  ⚠ VACÍO — revisar tipo o rango de fechas')
        except Exception as ex:
            print(f'    {nombre:15s}: ✗ ERROR — {ex}')

    # 3. DataFrame combinado
    print('\n[3] DataFrame combinado de San Rafael:')
    try:
        df = ve.fetch_station(session, 'San Rafael', start, end)
        print(f'    Filas: {len(df)}')
        print(f'    Columnas: {list(df.columns)}')
        print(f'    Rango de fechas: {df["Date"].min()} → {df["Date"].max()}')
        print('\n    Primeras filas:')
        print(df.head(6).to_string(index=False))
        print('\n    Chequeos:')
        print(f'      T  rango: {df["T"].min():.1f} .. {df["T"].max():.1f} °C')
        print(f'      HR rango: {df["HR"].min():.1f} .. {df["HR"].max():.1f} %')
        print(f'      P  suma:  {df["P"].max():.1f} (acumulada, se des-acumula en el motor)')
        # Sanidad
        if df['HR'].max() > 100 or df['HR'].min() < 0:
            print('      ⚠ HR fuera de rango 0-100: revisar el mapeo de variables.')
        if df['T'].max() > 55 or df['T'].min() < -30:
            print('      ⚠ T fuera de rango plausible: revisar el mapeo de variables.')
        print('\n✓ Extracción de una estación OK. Si los rangos son razonables,')
        print('  el extractor está listo para el pipeline completo (run_daily.py).')
    except Exception as ex:
        import traceback
        print(f'    ✗ ERROR: {ex}')
        traceback.print_exc()


if __name__ == '__main__':
    main()
