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
Versión 1.7 · 2026-07-14 (Sclerotinia: variantes superficie/-10cm/aire)
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
# STEMPHYLIUM VESICARIUM (tizón foliar de cebolla, SLB)  ·  STEMcast 2.0
# ---------------------------------------------------------------------------
# Valor de severidad diaria (DSV, 0-4) de STEMcast 2.0, el modelo específico
# de Stemphylium en CEBOLLA desarrollado en Ontario. Tabla 2.3 de:
#   Scicluna, J. (2025). Determining Effective Management Strategies for
#   Stemphylium Leaf Blight of Onion. MSc Thesis, University of Guelph.
# (STEMcast 2.0 deriva de TOMcast/Pitblado 1992, ajustado a S. vesicarium.)
#
# Matriz real (Tabla 2.3): DSV sólo se acumula entre 18 y 25°C.
#   18-20°C:  0-14h→0 | 15-16h→1 | 17+h→2
#   21-25°C:  0-12h→0 | 13-14h→1 | 15-16h→2 | 17-20h→3 | 21+h→4
# Umbral de acción del ensayo: CDSV=15 (acumulado).
#
# SALVEDAD IMPORTANTE (de la propia tesis): STEMcast 2.0 redujo el número de
# aplicaciones de fungicida pero NO redujo la severidad del SLB en los ensayos
# 2023-2024. Las combinaciones exactas T×mojado óptimas para infección de
# S. vesicarium en cebolla aún no se conocen con precisión. Por eso esta salida
# es una ALERTA DE VENTANA CLIMÁTICA conducente, NO un predictor de severidad
# ni una prescripción de tratamiento.
# SALVEDAD (heridas): S. vesicarium es patógeno débil que infecta sobre todo por
# heridas previas (trips, lesiones de mildiú/Alternaria). El modelo climático no
# captura esa predisposición.
# ===========================================================================
def stemphylium_dsv(T, wet):
    """DSV diario (0-4) de STEMcast 2.0 (Scicluna 2025, Tabla 2.3)."""
    if T is None or wet is None or wet <= 0:
        return 0
    if 18 <= T <= 20:
        if wet <= 14:   return 0
        elif wet <= 16: return 1
        else:           return 2
    elif 21 <= T <= 25:
        if wet <= 12:   return 0
        elif wet <= 14: return 1
        elif wet <= 16: return 2
        elif wet <= 20: return 3
        else:           return 4
    return 0     # <18°C o >25°C: sin acumulación (matriz STEMcast 2.0)


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
# 99:951-956. Ecuación INTEGRADA de Duthie (forma modificada de Weibull),
# implementada con los COEFICIENTES ORIGINALES del paper (Tablas 2 y 3 + ec.
# 4-6 y 8). Versión con parámetro H variable en el tiempo (R²=0.9501).
#
# Ecuaciones (paper):
#   f(w,t) = f(t) · {1 − exp[−(B·(w−C))^D]}                    (ec. 4)
#   f(t)   = E' · exp[(t−F)·G/(H+1)] / {1 + exp[(t−F)·G]}      (ec. 5)
#   E'     = E · [(H+1)/H] · H^(1/(H+1))                       (ec. 6)
#   H(w)   = 1.0196 · e^(0.1231·w)   (H variable en el tiempo) (ec. 8)
# Coeficientes: B=0.0877, C=0, D=2.8087 (Tabla 2, 15°C);
#               E=0.9602, F=21.0547, G=1.0814 (Tabla 3, 27 h).
# Mínimo de mojado para infección: 5.25 h (preliminar del paper; a 4 h no hay).
# Temperatura óptima media: 17.76 °C. Colapsa >20 °C, casi nula a 25 °C.
#
# NOTA (hospedante): ajuste original en cebollín (Allium fistulosum). En cebolla
# (A. cepa, más resistente) la extrapolación es razonable pero conservadora.
# NOTA (inóculo): la roya depende de inóculo transportado por viento a larga
# distancia; el modelo estima la VENTANA de infección favorable, no la llegada
# del inóculo (análogo a la nota de Sclerotinia).
# NOTA (mojado): se usa el proxy HR>=WET_HR como duración de mojado foliar.
# ===========================================================================
def _furuya_RI(T, w):
    """Infección relativa (RI, 0-1) según la ecuación integrada de Furuya 2009."""
    C = 0.0
    if w <= C or w < 5.25:      # sin infección bajo el mínimo de 5.25 h
        return 0.0
    F, G = 21.0547, 1.0814
    H = 1.0196 * exp(0.1231 * w)               # ec. 8 (H variable en el tiempo)
    E = 0.9602
    Ep = E * ((H + 1) / H) * (H ** (1.0 / (H + 1)))   # ec. 6
    ft = Ep * exp(((T - F) * G) / (H + 1)) / (1.0 + exp((T - F) * G))  # ec. 5
    B, D = 0.0877, 2.8087
    fw = 1.0 - exp(-((B * (w - C)) ** D))      # ec. 4 (factor de mojado)
    return max(0.0, ft * fw)


def puccinia_allii(T, wet):
    """
    Índice de infección de roya (Puccinia allii) 0-4.
    T   : temperatura media del período de mojado (°C)
    wet : duración de mojado foliar (h, proxy HR>=WET_HR)
    Basado en la ecuación integrada de Furuya et al. (2009) con H(w).
    Salida = RI(0-1) · 4, coherente con la escala de los demás modelos.
    """
    if T is None or wet is None:
        return 0.0
    try:
        ri = _furuya_RI(float(T), float(wet))
    except (ValueError, OverflowError):
        return 0.0
    return round(ri * 4, 1)


# ===========================================================================
# SCLEROTINIA SCLEROTIORUM  ·  Germinación carpogénica (Clarkson et al. 2007)
# ---------------------------------------------------------------------------
# Modelo de producción de apotecios por germinación carpogénica de esclerocios.
# Clarkson, Phelps, Whipps, Young, Smith & Watling (2007), Phytopathology
# 97:621-631. Modelo de DOS FASES secuenciales, con COEFICIENTES ORIGINALES
# (Tabla 4, isolate 13; ecuaciones 2 y 3):
#
#   Fase 1 — Acondicionamiento (conditioning): rc = a + b·e^(−k·T)   (ec. 2)
#            a=0.03273, b=1000, k=1.498. Rápido en FRÍO (5-10°C, ~2 días a 5°C),
#            lento en templado (~30 días a 15°C). Nulo ≥20°C.
#   Fase 2 — Germinación (germination): rg = exp(d0 + d1/(T+273))     (ec. 3)
#            d0=31.12, d1=−10138. Óptimo TEMPLADO (18-20°C, ~30-40 días),
#            muy lento en frío (~210 días a 5°C). Nulo ≥25°C.
#
# El acondicionamiento debe COMPLETARSE (Σrc ≥ 1) antes de que empiece la
# germinación (Σrg ≥ 1). Validado: reproduce los totales del paper (212 días a
# 5°C constante; 72 días a 18°C). Requiere además suelo húmedo (proxy HR alta).
#
# NOTA (hospedante): calibrado en lechuga de campo (UK). Es el modelo hortícola
# más cercano a brásicas de semilla; aun así, la extrapolación a B. oleracea es
# aproximada (no hay modelo dedicado a oleráceas).
# NOTA (temperatura): el acondicionamiento y la germinación carpogénica ocurren
# en el SUELO. Si la estación entrega temperatura de suelo (TS10, -10 cm de
# Agromet), el modelo la usa para esas tasas (fisiológicamente correcto). Si no,
# cae a T de aire como proxy conservador. La ventana de infección aérea sigue
# usando T de aire. -10 cm se prefiere sobre la superficie por ser más estable
# (la superficie tiene extremos día/noche que introducen ruido).
# NOTA (invierno): en la práctica, tras un invierno completo los esclerocios ya
# están acondicionados (Clarkson lo señala). Por eso el índice refleja sobre
# todo el avance de la fase de germinación durante la temporada.
# ===========================================================================
_SCL_A, _SCL_B, _SCL_K = 0.03273, 1000.0, 1.498      # ec. 2 (isolate 13)
_SCL_D0, _SCL_D1 = 31.12, -10138.0                    # ec. 3 (isolate 13)
_SCL_TMAX_COND = 20.0
_SCL_TMAX_GERM = 25.0


def _rate_conditioning(T):
    """Tasa de acondicionamiento por día (ec. 2). Rápida en frío."""
    if T is None or T >= _SCL_TMAX_COND:
        return 0.0
    return _SCL_A + _SCL_B * exp(-_SCL_K * T)


def _rate_germination(T):
    """Tasa de germinación por día (ec. 3, Arrhenius). Óptima en templado."""
    if T is None or T >= _SCL_TMAX_GERM:
        return 0.0
    return exp(_SCL_D0 + _SCL_D1 / (T + 273.0))


def _sclerotinia_una_variante(d, col_suelo):
    """
    Corre el modelo de Clarkson usando la columna de temperatura indicada
    (col_suelo: 'Tsoil0' superficie, 'Tsoil10' -10cm, o None para usar aire).
    Devuelve dict {fecha_str: (indice_0_100, germinacion_0_100)}.
    """
    has_col = col_suelo is not None and col_suelo in d.columns
    cond_acc = 1.0     # acondicionamiento asumido completo tras el invierno
    germ_acc = 0.0
    out = {}
    for idx, row in d.iterrows():
        T = row['Tmean']              # T aire (ventana de infección aérea)
        HR = row['HRmean']
        # Temperatura que gobierna los procesos EN EL SUELO
        Tsoil = row[col_suelo] if has_col else None
        if Tsoil is None or (isinstance(Tsoil, float) and Tsoil != Tsoil):
            Tsoil = T                 # respaldo: aire si falta el dato de suelo
        moist = HR >= 75

        if moist and Tsoil is not None:
            if cond_acc < 1.0:
                cond_acc = min(1.0, cond_acc + _rate_conditioning(Tsoil))
            if cond_acc >= 1.0 and germ_acc < 1.0:
                germ_acc = min(1.0, germ_acc + _rate_germination(Tsoil))

        germination = germ_acc
        infect = 1 if (T is not None and 7 <= T <= 25 and HR >= 80) else 0
        idx_val = round(germination * infect * 100)
        out[str(idx)] = (idx_val, round(germination * 100))
    return out


def compute_sclerotinia(daily):
    """
    daily: DataFrame indexado por fecha con columnas Tmean, HRmean y,
      opcionalmente, Tsoil0 (superficie, TS00) y/o Tsoil10 (-10 cm, TS10).
    Devuelve dict con las variantes disponibles:
      {'sup': {fecha: (idx, germ)},   # superficie (TS00) si está
       's10': {fecha: (idx, germ)},   # -10 cm (TS10) si está
       'aire':{fecha: (idx, germ)}}   # aire (siempre, respaldo/comparación)

    Las dos fases del ciclo de Clarkson (acondicionamiento en frío y germinación
    carpogénica) ocurren en el SUELO. Se ofrecen ambas profundidades para
    comparar sensibilidad: la SUPERFICIE (TS00) es donde germinan los esclerocios
    pero es más ruidosa (extremos día/noche); -10 cm (TS10) es más estable. La
    ventana de infección de las ascosporas usa T de aire (proceso aéreo).
    """
    d = daily.copy()
    res = {}
    if 'Tsoil0' in d.columns:
        res['sup'] = _sclerotinia_una_variante(d, 'Tsoil0')
    if 'Tsoil10' in d.columns:
        res['s10'] = _sclerotinia_una_variante(d, 'Tsoil10')
    # Aire siempre disponible: respaldo y término de comparación
    res['aire'] = _sclerotinia_una_variante(d, None)
    return res


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


def compute_all(station_dfs, window_days=None, station_meta=None):
    """
    station_dfs: dict {nombre_estacion: DataFrame crudo (Date,T,P,HR)}.
    window_days: si se indica, recorta la salida a los últimos N días.
    station_meta: dict opcional {nombre: {region, lat, lon}} para estaciones no
      predefinidas en STATIONS. Si una estación no está ni en STATIONS ni en
      station_meta, se usan coordenadas por defecto de Chile central (el cálculo
      astronómico del mildiú es poco sensible a pequeñas diferencias de lat/lon).
    Devuelve la estructura de datos lista para el artefacto.
    """
    mildew, alternaria, botrytis, roya, stemph = {}, {}, {}, {}, {}
    station_meta = station_meta or {}

    for st, raw in station_dfs.items():
        # Resolver metadata: STATIONS predefinidas > station_meta > default
        if st in STATIONS:
            cfg = STATIONS[st]
        elif st in station_meta:
            m = station_meta[st]
            cfg = dict(region=m.get('region', ''),
                       lat=m.get('lat', -35.0), lon=m.get('lon', -71.3))
        else:
            # Estación sin metadata: usar Chile central como aproximación.
            cfg = dict(region='', lat=-35.0, lon=-71.3)
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
        # Si la estación trae temperatura de suelo (Tsoil, TS10 de Agromet),
        # se agrega al 'daily' para que Sclerotinia la use.
        if 'Tsoil' in df.columns:
            daily = df.groupby('date').agg(Tmean=('T', 'mean'),
                                           HRmean=('HR', 'mean'),
                                           Tsoil=('Tsoil', 'mean'))
        else:
            daily = df.groupby('date').agg(Tmean=('T', 'mean'),
                                           HRmean=('HR', 'mean'))
        scl = compute_sclerotinia(daily)

        a_rows, b_rows, r_rows, st_rows = [], [], [], []
        for ds in dias:
            dd = pd.to_datetime(ds).date()
            dur, Tm = wev.get(dd, (0, None))
            a_rows.append(dict(f=ds, wet=dur, tm=Tm,
                               porri=alt_porri(Tm, dur),
                               dauci=alt_dauci_dsv(Tm, dur),
                               bras=alt_brassicae(Tm, dur)))
            # Sclerotinia: variantes por profundidad de suelo (sup / -10cm / aire)
            sc_sup = scl.get('sup', {}).get(ds, (0, 0))
            sc_s10 = scl.get('s10', {}).get(ds, (0, 0))
            sc_air = scl.get('aire', {}).get(ds, (0, 0))
            # Preferida para el índice principal: -10cm > superficie > aire
            if 's10' in scl:
                sidx, sready = sc_s10
            elif 'sup' in scl:
                sidx, sready = sc_sup
            else:
                sidx, sready = sc_air
            b_rows.append(dict(f=ds, wet=dur, tm=Tm,
                               squa=bot_squamosa(Tm, dur),
                               cin=bot_cinerea(Tm, dur),
                               scl=sidx, scl_ready=sready,
                               scl_sup=sc_sup[0], scl_sup_r=sc_sup[1],
                               scl_s10=sc_s10[0], scl_s10_r=sc_s10[1],
                               scl_air=sc_air[0], scl_air_r=sc_air[1]))
            r_rows.append(dict(f=ds, wet=dur, tm=Tm,
                               allii=puccinia_allii(Tm, dur)))
            st_rows.append(dict(f=ds, wet=dur, tm=Tm,
                                dsv=stemphylium_dsv(Tm, dur)))

        # DSV acumulado de Stemphylium (STEMcast 2.0), como TOM-CAST
        acc = 0
        for row in st_rows:
            acc += row['dsv']
            row['cum'] = acc

        # Recorte de ventana (para la vista diaria de N días)
        if window_days:
            m_rows = m_rows[-window_days:]
            a_rows = a_rows[-window_days:]
            b_rows = b_rows[-window_days:]
            r_rows = r_rows[-window_days:]
            st_rows = st_rows[-window_days:]

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
        stemph[st] = dict(region=cfg['region'], data=st_rows)

    return dict(mildew=mildew, alternaria=alternaria, botrytis=botrytis,
                roya=roya, stemph=stemph)
