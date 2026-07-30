#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_icons.py — v1.0 · 30-07-2026
Generacion del set de iconos PWA para "Herramientas fitosanitarias SPS".

(c) 2026 Winston Colvin - South Pacific Seeds Chile S.A.

FUNDAMENTO DE LAS DECISIONES
----------------------------
1. Fuente. El logo se extrae del propio index.html (data URI PNG, 140x120 px,
   RGBA, monocromo #194F7B sobre transparencia). No se introduce ningun asset
   externo: la marca del icono es exactamente la del encabezado de la app.

2. Escalado por canal alfa. El logo es de dos tonos (transparente / azul solido).
   En vez de reescalar RGBA -- que arrastra franjas de color premultiplicado en
   los bordes -- se reescala SOLO el canal alfa con LANCZOS y se recompone
   pintando un color plano con esa mascara. Resultado: silueta identica,
   antialias limpio recalculado a la resolucion destino. Necesario porque la
   fuente es de 140 px y el destino mayor es 512 px (factor 3,66x).

3. Dos variantes cromaticas.
   - VARIANTE B (por defecto): fondo azul marino institucional #14366E, marca
     en blanco. Se elige por defecto porque a 60 px -- tamano real en pantalla
     de inicio -- un icono de fondo blanco desaparece contra fondos claros de
     iOS/Android, y porque resuelve la discrepancia entre el #194F7B del PNG y
     el #14366E del CSS de la aplicacion: la marca deja de ser azul.
   - VARIANTE A (alternativa, en alt_blanco/): fondo blanco, marca en su
     #194F7B original. Conserva el color corporativo del PNG intacto.

4. "any" vs "maskable". Se generan ambos propositos:
   - any: esquinas redondeadas r = 22 % del lado. Cubre plataformas que NO
     aplican mascara propia y muestran el PNG tal cual.
   - maskable: fondo a sangre, SIN redondeo, marca contenida en el 58 % central.
     Android recorta hasta un circulo de 80 % de diametro; 58 % deja margen
     ante recortes agresivos de lanzadores de terceros.

5. apple-touch-icon 180 px. Cuadrado, OPACO y sin redondeo por diseno: iOS
   aplica su propio squircle y compone cualquier transparencia sobre NEGRO,
   lo que produciria esquinas negras si se entregara con alfa.

6. favicon 32 px. Marca al 82 % sin redondeo; a ese tamano el redondeo se
   pierde y solo consume pixeles utiles.

7. Cuantizacion. Paleta indexada (ADAPTIVE) tras el render. Con 2-3 colores
   reales la perdida es nula y el peso baja un orden de magnitud.
"""

import base64
import os
import re
import sys

from PIL import Image, ImageDraw

VERSION = "1.0"
FECHA = "2026-07-30"

SRC_HTML = "index_orig.html"
OUT = "."
ALT = "alt_blanco"

# Paleta institucional (Restricciones del Proyecto, seccion A.7)
NAVY = (20, 54, 110)        # #14366E
BLANCO = (255, 255, 255)    # #FFFFFF
LOGO_AZUL = (25, 79, 123)   # #194F7B - color nativo del PNG incrustado

# Escala del contenido respecto al lado del icono
ESC_ANY = 0.74      # con fondo redondeado
ESC_MASK = 0.58     # dentro de la zona segura del recorte Android
ESC_APPLE = 0.72
ESC_FAVICON = 0.82

RADIO_ANY = 0.22    # fraccion del lado


def extraer_logo(path_html):
    """Recupera el primer data URI PNG del index y devuelve su canal alfa."""
    with open(path_html, encoding="utf-8") as fh:
        html = fh.read()
    m = re.search(r"data:image/png;base64,([A-Za-z0-9+/=]{40,})", html)
    if not m:
        raise SystemExit("No se encontro el logo incrustado en " + path_html)
    return base64.b64decode(m.group(1))


def cargar_mascara(raw_png):
    import io
    im = Image.open(io.BytesIO(raw_png)).convert("RGBA")
    alfa = im.split()[3]
    # Recorte al contenido real, para que la escala sea sobre la marca y no
    # sobre el lienzo (evita margenes fantasma heredados del PNG original).
    caja = alfa.getbbox()
    return alfa.crop(caja), caja


def render(lado, mascara, color_marca, color_fondo, escala,
           radio=0.0, opaco=True):
    """Compone un icono cuadrado de 'lado' px."""
    w0, h0 = mascara.size
    # Ajuste por el lado mayor de la marca, preservando proporcion.
    if w0 >= h0:
        w = int(round(lado * escala))
        h = int(round(w * h0 / w0))
    else:
        h = int(round(lado * escala))
        w = int(round(h * w0 / h0))

    m = mascara.resize((w, h), Image.LANCZOS)

    lienzo = Image.new("RGBA", (lado, lado), (0, 0, 0, 0))

    if radio > 0:
        r = int(round(lado * radio))
        forma = Image.new("L", (lado, lado), 0)
        ImageDraw.Draw(forma).rounded_rectangle(
            [0, 0, lado - 1, lado - 1], radius=r, fill=255)
    else:
        forma = Image.new("L", (lado, lado), 255)

    fondo = Image.new("RGBA", (lado, lado), color_fondo + (255,))
    fondo.putalpha(forma)
    lienzo.alpha_composite(fondo)

    marca = Image.new("RGBA", (lado, lado), (0, 0, 0, 0))
    capa = Image.new("RGBA", (w, h), color_marca + (255,))
    capa.putalpha(m)
    marca.paste(capa, ((lado - w) // 2, (lado - h) // 2), capa)
    lienzo.alpha_composite(marca)

    if opaco:
        plano = Image.new("RGB", (lado, lado), color_fondo)
        plano.paste(lienzo.convert("RGB"), (0, 0), lienzo.split()[3])
        return plano
    return lienzo


def guardar(im, ruta, colores=16):
    modo = "RGBA" if im.mode == "RGBA" else "RGB"
    if modo == "RGBA":
        q = im.quantize(colors=colores, method=Image.FASTOCTREE)
    else:
        q = im.quantize(colors=colores, method=Image.MEDIANCUT)
    q.save(ruta, optimize=True)
    return os.path.getsize(ruta)


def set_completo(destino, color_marca, color_fondo, etiqueta):
    os.makedirs(destino, exist_ok=True)
    resultados = []

    especificaciones = [
        # nombre,                 lado, escala,       radio,     opaco
        ("icon-192.png",           192, ESC_ANY,      RADIO_ANY, False),
        ("icon-512.png",           512, ESC_ANY,      RADIO_ANY, False),
        ("icon-maskable-192.png",  192, ESC_MASK,     0.0,       True),
        ("icon-maskable-512.png",  512, ESC_MASK,     0.0,       True),
        ("apple-touch-icon.png",   180, ESC_APPLE,    0.0,       True),
        ("favicon-32.png",          32, ESC_FAVICON,  0.0,       True),
    ]

    for nombre, lado, esc, rad, opaco in especificaciones:
        im = render(lado, MASCARA, color_marca, color_fondo, esc,
                    radio=rad, opaco=opaco)
        ruta = os.path.join(destino, nombre)
        peso = guardar(im, ruta)
        resultados.append((nombre, lado, peso, "opaco" if opaco else "alfa"))

    print("\n=== SET %s ===" % etiqueta)
    total = 0
    for nombre, lado, peso, tipo in resultados:
        print("  %-26s %3d px  %6d B  %s" % (nombre, lado, peso, tipo))
        total += peso
    print("  %-26s        %6d B  (%.1f KiB)" % ("TOTAL", total, total / 1024))
    return resultados, total


if __name__ == "__main__":
    RAW = extraer_logo(SRC_HTML)
    MASCARA, CAJA = cargar_mascara(RAW)
    print("build_icons.py v%s - %s" % (VERSION, FECHA))
    print("Logo incrustado: bbox %s -> mascara %s px" % (CAJA, MASCARA.size))

    set_completo(OUT, BLANCO, NAVY, "B - fondo #14366E / marca blanca (POR DEFECTO)")
    set_completo(ALT, LOGO_AZUL, BLANCO, "A - fondo blanco / marca #194F7B")
