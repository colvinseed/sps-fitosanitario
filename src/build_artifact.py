"""
build_artifact.py
=================
Genera el artefacto HTML bilingüe (vista diaria, 7 días móviles) a partir de
los datos calculados por disease_models.compute_all().

Une tres cosas en la plantilla:
  - Datos frescos de las seis enfermedades (ventana de 7 días)
  - Diccionario de interfaz bilingüe (ui.json)
  - Documentación de modelos ES/EN (docs.json / docs_en.json)

Salida: output/index.html  (listo para embeber en Squarespace vía iframe/URL)

© 2026 Winston Colvin — South Pacific Seeds Chile
Versión 1.0 · 2026-07-13
"""

import os
import json
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def _load_json(name):
    with open(os.path.join(HERE, name), encoding='utf-8') as f:
        return json.load(f)


def build(results, out_path=None, window_label=None, tablero=None, name2id=None):
    """
    results: salida de compute_all(..., window_days=7).
    tablero: dict opcional del extractor agromet_tablero.py (condiciones actuales).
    name2id: dict opcional {nombre: id_agromet} para cruzar favoritas con tablero.
    Escribe el HTML final y devuelve su ruta.
    """
    ui = _load_json('ui.json')
    docs_es = _load_json('docs.json')
    docs_en = _load_json('docs_en.json')

    combined = dict(
        mildew=results['mildew'],
        alternaria=results['alternaria'],
        botrytis=results['botrytis'],
        roya=results.get('roya', {}),
        stemph=results.get('stemph', {}),
        docs_es=docs_es,
        docs_en=docs_en,
        ui=ui,
    )
    data_json = json.dumps(combined, ensure_ascii=False, separators=(',', ':'))

    with open(os.path.join(HERE, 'template.html'), encoding='utf-8') as f:
        template = f.read()

    # Inyectar datos frescos
    start = template.index('/*__DATA__*/')
    end = template.index('/*__END__*/') + len('/*__END__*/')
    html = template[:start] + data_json + template[end:]

    # Inyectar datos del tablero de condiciones actuales (página de inicio)
    tablero = tablero or {'timestamp': None, 'estaciones': {}}
    tbl_json = json.dumps(tablero, ensure_ascii=False, separators=(',', ':'))
    if '/*__TABLERO__*/' in html:
        s = html.index('/*__TABLERO__*/')
        e = html.index('/*__ENDTBL__*/') + len('/*__ENDTBL__*/')
        html = html[:s] + tbl_json + html[e:]

    # Inyectar mapa nombre->id (cruce favoritas <-> datos del tablero)
    n2i_json = json.dumps(name2id or {}, ensure_ascii=False, separators=(',', ':'))
    if '/*__NAME2ID__*/' in html:
        s = html.index('/*__NAME2ID__*/')
        e = html.index('/*__ENDN2I__*/') + len('/*__ENDN2I__*/')
        html = html[:s] + n2i_json + html[e:]

    # Inyectar fecha de actualización (hora local de Chile)
    updated = datetime.now().strftime('%Y-%m-%d %H:%M')
    html = html.replace('/*__UPDATED__*/', updated)

    out_path = out_path or os.path.join(ROOT, 'output', 'index.html')
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(html)
    return out_path


if __name__ == '__main__':
    # Prueba local con el Excel de ejemplo, si está disponible.
    import sys
    sys.path.insert(0, HERE)
    from disease_models import compute_all
    import pandas as pd

    sample = '/mnt/user-data/uploads/clima_5est_2026-05-01_a_2026-07-13.xlsx'
    if os.path.exists(sample):
        x = pd.ExcelFile(sample)
        SHEETS = {
            'Chocalán': ('Chocalan Temperatura', 'Chocalan Precipitación', 'Chocalan Humedad'),
            'Talagante': ('TALAGANTE Temperatura', 'TALAGANTE Precipitación', 'TALAGANTE Humedad'),
            'Placilla': ('Placilla Chacarilla Temperatura', 'Placilla Chacarilla Precipitaci', 'Placilla Chacarilla Humedad'),
            'Peor es Nada': ('Peor es Nada Temperatura', 'Peor es Nada Precipitación', 'Peor es Nada Humedad'),
            'San Rafael': ('San Rafael Temperatura', 'San Rafael Precipitación', 'San Rafael Humedad'),
        }

        def load(sh):
            t = pd.read_excel(x, sh[0]); p = pd.read_excel(x, sh[1]); h = pd.read_excel(x, sh[2])
            tc = [c for c in t.columns if c not in ('Date', 'weather station')][0]
            pc = [c for c in p.columns if c not in ('Date', 'weather station')][0]
            hc = [c for c in h.columns if c not in ('Date', 'weather station')][0]
            df = t[['Date', tc]].merge(p[['Date', pc]], on='Date').merge(h[['Date', hc]], on='Date')
            df.columns = ['Date', 'T', 'P', 'HR']
            return df

        dfs = {st: load(sh) for st, sh in SHEETS.items()}
        res = compute_all(dfs, window_days=7)
        out = build(res)
        print('OK ->', out)
    else:
        print('(sin Excel de ejemplo; build() listo para usarse desde el pipeline)')
