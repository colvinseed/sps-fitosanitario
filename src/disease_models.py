"""
disease_models.py
=================
Motor de cálculo fitosanitario — South Pacific Seeds Chile.
Modelos de pronóstico para seis enfermedades foliares/florales, adaptados a la
red de estaciones de Chile central.

Fases modeladas (cada patógeno según lo que la literatura documenta mejor):
  - Mildiú velloso (Peronospora destructor) ...... ESPORULACIÓN  (MILIONCAST2 + DOWNCAST)
  - Alternaria porri (cebolla) ................... INFECCIÓN     (Suheri & Price 2000)
  - Alternaria dauci (zanahoria) ................. INFECCIÓN     (TOM-CAST / Pitblado 1992)
  - Alternaria brassicae (brásicas) ............. INFECCIÓN     (umbral T×mojado literatura)
  - Botrytis squamosa (cebolla) ................. INFECCIÓN     (BOTCAST + Carisse 2012)
  - Botrytis cinerea (moho gris polífago) ....... INFECCIÓN     (umbral T×mojado genérico)
  - Sclerotinia sclerotiorum (moho blanco) ...... ÍNDICE FAVORABILIDAD (asume inóculo en suelo)
  - Puccinia allii (roya cebolla/cebollín) ...... INFECCIÓN     (Furuya et al. 2009, Duthie/Weibull)

NOTA IMPORTANTE: el mojado foliar se estima por proxy de HR>=90% (no medido).
Todos los modelos salvo la esporulación del mildiú dependen de ese proxy.
Parámetros sin recalibrar a Chile — salidas referenciales, no prescriptivas.

© 2026 Winston Colvin — South Pacific Seeds Chile
Versión 1.1 · 2026-07-13 (+ Puccinia allii)
"""

import math
from math import gamma as _gamma, exp
import pandas as pd
import numpy as np

# ---------------------------------------------------------------------------
# Configuración de estaciones (coordenadas confirmadas)
# ---------------------------------------------------------------------------
STATIONS = {
    'Chocalán':     dict(region='RM',        lat=-33.75, lon=-71.05),
    'Talagante':    dict(region='RM',        lat=-33.67, lon=-70.93),
    'Placilla':     dict(region="O'Higgins", lat=-34.63, lon=-71.12),
    'Peor es Nada': dict(region="O'Higgins", lat=-34.78, lon=-70.99),
    'San Rafael':   dict(region='Maule',     lat=-35.32, lon=-71.10),
}

WET_HR = 90          # Umbral de HR (%) que cuenta como "hora de mojado foliar" (proxy)
DARK_TWILIGHT = -6   # Crepúsculo civil (grados) para la ventana de oscuridad
UTC_OFFSET = -4      # Hora local de Chile central (aprox., para cálculo astronómico)


# ===========================================================================
# UTILIDADES COMUNES
# ===========================================================================
def sun_events(lat, lon, d):
    """Devuelve (amanecer, atardecer) en hora local decimal para la fecha d."""
    N = d.timetuple().tm_yday
    lat_r = math.radians(lat)
    decl = math.radians(-23.44 * math.cos(math.radians(360 / 365 * (N + 10))))
    cosH = ((math.sin(math.radians(DARK_TWILIGHT)) - math.sin(lat_r) * math.sin(decl))
            / (math.cos(lat_r) * math.cos(decl)))
    cosH = min(1, max(-1, cosH))
    H = math.degrees(math.acos(cosH))
    noon = 12 - (lon - (UTC_OFFSET * 15)) / 15
    return noon - H / 15, noon + H / 15


def wet_events_by_day(df):
    """
    Detecta corridas continuas de HR>=WET_HR. Devuelve, por fecha, la corrida de
    mojado más larga que TERMINA ese día: {date: (horas, T_media_del_evento)}.
    """
    df = df.sort_values('Date').reset_index(drop=True)
    df['wet'] = df['HR'] >= WET_HR
    df['grp'] = (df['wet'] != df['wet'].shift()).cumsum()
    out = {}
    for _, sub in df[df['wet']].groupby('grp'):
        dur = len(sub)
        Tm = sub['T'].mean()
        d = sub['Date'].max().date()
        if d not in out or dur > out[d][0]:
            out[d] = (dur, round(float(Tm), 1))
    return out


# ===========================================================================
# MILDIÚ VELLOSO — MILIONCAST2 (esporulación)  ·  Gilles et al. 2004
# ===========================================================================
def _c_of_T(T):
    if T <= 0:
        return 0.0
    return (213.0 * (12.0 ** (-2.15)) * (T ** 1.15) * exp(-T / 12.0)) / _gamma(2.15)


def _m_of_T(T):
    if T <= 0:
        return 1e9
    return _gamma(2.61) / (4.01 * (6.93 ** (-2.61)) * (T ** 1.61) * exp(-T / 6.93))


def _gompertz(c, t, m):
    z = min(-0.90 * (t - m), 50)
    return c * exp(-min(exp(z), 50))


def _log_sr(v):
    return (100 - max(0, min(100, v))) * math.log10(0.60)


def milioncast(df, lat, lon):
    """Esporulación de mildiú. Devuelve {fecha_str: (log10_esporangios, T_media, horas_humedas)}."""
    df = df.copy()
    df['dt'] = df['Date']
    res = {}
    dias = sorted(df['date'].unique())
    for i in range(1, len(dias)):
        d = dias[i]
        dusk = sun_events(lat, lon, dias[i - 1])[1]
        start = pd.Timestamp(dias[i - 1]) + pd.Timedelta(hours=dusk)
        end = pd.Timestamp(d) + pd.Timedelta(hours=9)
        night = df[(df['dt'] >= start) & (df['dt'] <= end)]
        wet = night[night['HR'] >= 92]
        if len(wet) == 0:
            res[str(d)] = (0.0, None, 0)
            continue
        eff = float(len(wet))
        Tm = float(wet['T'].mean())
        hm = float(wet['HR'].mean())
        ls = max(0.0, _gompertz(_c_of_T(Tm), eff, _m_of_T(Tm)) + _log_sr(hm))
        res[str(d)] = (round(ls, 2), round(Tm, 1), len(wet))
    return res


# ===========================================================================
# MILDIÚ VELLOSO — DOWNCAST (comparación binaria)  ·  Tabla 1, Gilles et al. 2004
# ===========================================================================
def downcast(df):
    """Predicción binaria DOWNCAST por día. Devuelve {fecha_str: bool}."""
    res = {}
    dias = sorted(df['date'].unique())
    for i in range(1, len(dias)):
        d = dias[i]
        cur = df[df['date'] == d]
        prev = df[df['date'] == dias[i - 1]]
        p1 = prev[(prev['hour'] >= 8) & (prev['hour'] <= 20)]
        c1 = bool(len(p1) and p1['T'].mean() <= 24)
        n = pd.concat([prev[prev['hour'] >= 20], cur[cur['hour'] <= 8]])
        c2 = bool(len(n) and ((n['T'] >= 4) & (n['T'] <= 24)).all())
        r3 = cur[(cur['hour'] >= 1) & (cur['hour'] <= 6)]
        c3 = bool((r3['precip_h'] <= 1).all())
        r4 = cur[(cur['hour'] >= 2) & (cur['hour'] <= 6)].sort_values('hour')
        c4 = bool(len(r4) and (r4['HR'] >= 95).all())
        res[str(d)] = bool(c1 and c2 and c3 and c4)
    return res


# ===========================================================================
# ALTERNARIA PORRI (cebolla, infección)  ·  Suheri & Price 2000
# ===========================================================================
def _porri_threshold(T):
    if T < 6:   return 999
    if T < 10:  return 16 + (10 - T) * 2
    if T <= 25: return 8
    if T <= 34: return 8 + (T - 25) * 0.5
    return 999


def _porri_temp_factor(T):
    if T < 6 or T > 34:  return 0.0
    if 25 <= T <= 27:    return 1.0
    if T < 25:           return max(0, (T - 6) / (25 - 6))
    return max(0, (34 - T) / (34 - 27))


def alt_porri(T, wet):
    if wet <= 0 or T is None:
        return 0.0
    thr = _porri_threshold(T)
    if thr >= 999:
        return 0.0
    infected = 1 if wet >= thr else 0
    return round(min(4, (wet / thr) * 4 * _porri_temp_factor(T)) * infected, 1)


# ===========================================================================
# ALTERNARIA DAUCI (zanahoria, infección)  ·  TOM-CAST / Pitblado 1992
# ===========================================================================
def alt_dauci_dsv(T, wet):
    if T is None or wet < 1:
        return 0
    if 13 <= T <= 17:
        return 0 if wet <= 6 else 1 if wet <= 15 else 2 if wet <= 20 else 3
    if 18 <= T <= 20:
        return 0 if wet <= 3 else 1 if wet <= 8 else 2 if wet <= 15 else 3 if wet <= 22 else 4
    if 21 <= T <= 25:
        return 0 if wet <= 2 else 1 if wet <= 5 else 2 if wet <= 12 else 3 if wet <= 20 else 4
    if 26 <= T <= 29:
        return 0 if wet <= 3 else 1 if wet <= 8 else 2 if wet <= 15 else 3 if wet <= 22 else 4
    if 8 <= T < 13:
        return 0 if wet <= 12 else 1 if wet <= 20 else 2
    return 0


# ===========================================================================
# ALTERNARIA BRASSICAE (brásicas, infección)  ·  umbral T×mojado (literatura)
# ===========================================================================
def alt_brassicae(T, wet):
    if T is None or wet < 4 or T < 5 or T > 30:
        return 0
    tf = 1.0 if 15 <= T <= 24 else (0.6 if 10 <= T < 28 else 0.3)
    base = 1 if wet < 8 else 2 if wet < 12 else 3 if wet < 18 else 4
    return round(base * tf)


# ===========================================================================
# BOTRYTIS SQUAMOSA (cebolla, infección)  ·  BOTCAST + Carisse 2012 (Weibull)
# ===========================================================================
def bot_squamosa(T, wet):
    if T is None or wet < 6 or T < 6 or T > 29:
        return 0.0
    if 18 <= T <= 22:            tf = 1.0
    elif 10 <= T < 25:           tf = 0.7
    elif 6 <= T < 10 or 25 <= T < 27: tf = 0.4
    else:                        tf = 0.15
    if wet < 12:   wf = 0.3
    elif wet < 24: wf = 0.6
    elif wet < 48: wf = 0.85
    else:          wf = 1.0
    return round(tf * wf * 4, 1)


# ===========================================================================
# BOTRYTIS CINEREA (moho gris polífago, infección)  ·  umbral T×mojado genérico
# ===========================================================================
def bot_cinerea(T, wet):
    if T is None or wet < 4 or T < 1 or T > 30:
        return 0.0
    if 15 <= T <= 22: tf = 1.0
    elif 8 <= T < 28: tf = 0.7
    else:             tf = 0.35
    if wet < 8:    wf = 0.4
    elif wet < 16: wf = 0.7
    elif wet < 24: wf = 0.9
    else:          wf = 1.0
    return round(tf * wf * 4, 1)


# ===========================================================================
# PUCCINIA ALLII (roya de cebolla/cebollín, infección)  ·  Furuya et al. 2009
# ---------------------------------------------------------------------------
# Modelo de infección por urediniosporas en función de temperatura y mojado
# foliar. Furuya, Takanashi, Fuji, Nagai & Naito (2009), Phytopathology
# 99:951-956, ajustaron la infección relativa con la ecuación de Duthie (forma
# modificada de Weibull), R²=0.9369.
#
# Parámetros epidemiológicos CONFIRMADOS por la literatura (Furuya 2009; PNW
# Handbook), usados aquí para definir los factores:
#   - Infección entre 6.5 y 27 h de mojado (10-25°C); requiere >=10 h a 5°C.
#   - Aumento rápido de infección entre 6.5 y 15 h de mojado (10-20°C).
#   - Óptimo en clima FRESCO 10-15°C; a 25°C casi no hay infección pese al mojado.
#   - Mínimo ~4-6 h de mojado para cualquier infección (PNW; Morinaka).
#
# ADVERTENCIA (calibración): los coeficientes numéricos exactos (a,b,c) del
# ajuste de Duthie de Furuya están en el paper original (acceso restringido).
# Esta implementación reproduce la ESTRUCTURA y los rangos publicados mediante
# factores por tramos (igual estilo que los demás modelos de esta suite), NO
# los coeficientes originales. Salida referencial 0-4, a calibrar en terreno.
#
# ADVERTENCIA (inóculo): la roya tiene fuerte componente de inóculo transportado
# por viento a larga distancia; este modelo estima la VENTANA de infección
# favorable, no la llegada del inóculo (análogo a la nota de Sclerotinia).
#
# ADVERTENCIA (hospedante): el ajuste original es en cebollín (Allium fistulosum).
# En cebolla (A. cepa) el mismo patógeno infecta, pero A. cepa es más resistente;
# la extrapolación es razonable pero conservadora.
# ===========================================================================
def puccinia_allii(T, wet):
    """
    Índice de infección de roya (Puccinia allii) 0-4.
    T   : temperatura media del período de mojado (°C)
    wet : duración de mojado foliar (h, proxy HR>=WET_HR)
    Patógeno de clima fresco: óptimo 10-15°C, colapsa >=25°C.
    """
    if T is None or wet < 4 or T < 3 or T > 26:
        return 0.0
    # Factor de temperatura (asimétrico, óptimo fresco 10-15°C; cae fuerte >20°C)
    if 10 <= T <= 15:            tf = 1.0     # óptimo confirmado
    elif 15 < T <= 18:           tf = 0.8
    elif 8 <= T < 10:            tf = 0.7
    elif 18 < T <= 20:           tf = 0.55
    elif 5 <= T < 8:             tf = 0.4
    elif 20 < T <= 23:           tf = 0.30    # infección escasa acercándose al límite cálido
    elif 3 <= T < 5:             tf = 0.20    # a 5°C requiere >=10 h de mojado
    else:                        tf = 0.10    # 23-26°C: casi nula (a 25°C casi no hay uredinias)
    # Factor de mojado foliar (aumento rápido 6.5-15 h; requiere >=6 h para subir)
    if wet < 6:      wf = 0.15               # mínimo marginal
    elif wet < 10:   wf = 0.45               # entra el rango de infección
    elif wet < 15:   wf = 0.80               # ascenso rápido documentado
    elif wet < 27:   wf = 1.0                # meseta hasta ~27 h
    else:            wf = 1.0
    # A <8°C, la infección real exige mojados largos: penaliza mojado corto en frío
    if T < 8 and wet < 10:
        wf *= 0.5
    return round(tf * wf * 4, 1)


# ===========================================================================
# SCLEROTINIA SCLEROTIORUM (índice favorabilidad)  ·  asume inóculo en suelo
# ===========================================================================
def _sclero_conducive(Tmean_day, hr_mean_day):
    return 1 if (12 <= Tmean_day <= 22 and hr_mean_day >= 75) else 0


def compute_sclerotinia(daily):
    """
    daily: DataFrame indexado por fecha con columnas Tmean, HRmean.
    Devuelve dict {fecha_str: (indice_0_100, preparacion_apotecios_0_100)}.
    ASUME inóculo (esclerocios) presente en el suelo.
    """
    d = daily.copy()
    d['cond'] = d.apply(lambda r: _sclero_conducive(r['Tmean'], r['HRmean']), axis=1)
    d['cond10'] = d['cond'].rolling(10, min_periods=1).sum()
    out = {}
    for idx, row in d.iterrows():
        readiness = min(1.0, row['cond10'] / 10.0)
        infect = 1 if (12 <= row['Tmean'] <= 25 and row['HRmean'] >= 78) else 0
        out[str(idx)] = (round(readiness * infect * 100), round(readiness * 100))
    return out


# ===========================================================================
# ORQUESTADOR: de DataFrame por estación -> dict de resultados de las 6 enfermedades
# ===========================================================================
def prepare_station_df(df):
    """
    Normaliza un DataFrame crudo (columnas Date, T, P, HR) al formato interno:
    des-acumula precipitación, añade columnas date/hour/precip_h.
    """
    df = df.copy()
    df['Date'] = pd.to_datetime(df['Date'])
    df = df.sort_values('Date').reset_index(drop=True)
    # Des-acumular precipitación (viene como serie acumulada monótona)
    df['precip_h'] = df['P'].diff()
    df.loc[df.index[0], 'precip_h'] = 0
    df.loc[df['precip_h'] < 0, 'precip_h'] = 0
    df['date'] = df['Date'].dt.date
    df['hour'] = df['Date'].dt.hour
    return df


def compute_all(station_dfs, window_days=None):
    """
    station_dfs: dict {nombre_estacion: DataFrame crudo (Date,T,P,HR)}.
    window_days: si se indica, recorta la salida a los últimos N días.
    Devuelve la estructura de datos lista para el artefacto:
      {'mildew': {...}, 'alternaria': {...}, 'botrytis': {...}, 'meta': {...}}
    """
    mildew, alternaria, botrytis, roya = {}, {}, {}, {}

    for st, raw in station_dfs.items():
        if st not in STATIONS:
            continue
        cfg = STATIONS[st]
        df = prepare_station_df(raw)
        wev = wet_events_by_day(df)

        # --- Mildiú ---
        dc = downcast(df)
        mc = milioncast(df, cfg['lat'], cfg['lon'])
        dias = sorted(str(d) for d in df['date'].unique())[1:]
        m_rows = []
        for ds in dias:
            ls, tm, wh = mc[ds]
            m_rows.append(dict(f=ds, dc=1 if dc.get(ds) else 0, mc=ls, tm=tm, wh=wh))

        # --- Alternaria + Botrytis (por evento de mojado diario) ---
        daily = df.groupby('date').agg(Tmean=('T', 'mean'), HRmean=('HR', 'mean'))
        scl = compute_sclerotinia(daily)

        a_rows, b_rows, r_rows = [], [], []
        for ds in dias:
            dd = pd.to_datetime(ds).date()
            dur, Tm = wev.get(dd, (0, None))
            a_rows.append(dict(f=ds, wet=dur, tm=Tm,
                               porri=alt_porri(Tm, dur),
                               dauci=alt_dauci_dsv(Tm, dur),
                               bras=alt_brassicae(Tm, dur)))
            sidx, sready = scl.get(ds, (0, 0))
            b_rows.append(dict(f=ds, wet=dur, tm=Tm,
                               squa=bot_squamosa(Tm, dur),
                               cin=bot_cinerea(Tm, dur),
                               scl=sidx, scl_ready=sready))
            r_rows.append(dict(f=ds, wet=dur, tm=Tm,
                               allii=puccinia_allii(Tm, dur)))

        # Recorte de ventana (para la vista diaria de N días)
        if window_days:
            m_rows = m_rows[-window_days:]
            a_rows = a_rows[-window_days:]
            b_rows = b_rows[-window_days:]
            r_rows = r_rows[-window_days:]

        # Resúmenes de mildiú
        strong = sum(1 for e in m_rows if e['mc'] > 4)
        mod = sum(1 for e in m_rows if 2 < e['mc'] <= 4)
        low = sum(1 for e in m_rows if 0 < e['mc'] <= 2)
        nulo = sum(1 for e in m_rows if e['mc'] == 0)
        ndc = sum(1 for e in m_rows if e['dc'] == 1)

        mildew[st] = dict(region=cfg['region'], ndc=ndc, strong=strong,
                          mod=mod, low=low, nulo=nulo, data=m_rows)
        alternaria[st] = dict(region=cfg['region'], data=a_rows)
        botrytis[st] = dict(region=cfg['region'], data=b_rows)
        roya[st] = dict(region=cfg['region'], data=r_rows)

    return dict(mildew=mildew, alternaria=alternaria, botrytis=botrytis, roya=roya)
