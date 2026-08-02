#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_icons.py - v3.1 - 02-08-2026
Juego de iconos de aplicacion derivado de LOGO_PATOLOGIA.png
(marca combinada: circulo hoja-escudo-esporas sobre monograma SPS en
filigrana, con rotulo FITOSANITARIOS al pie).
(c) 2026 Winston Colvin - South Pacific Seeds Chile

CAMBIOS v3.1 respecto de v3.0:
  - SIN RECORTE. Se usa el lienzo completo de 512x512: simbolo, filigrana SPS
    y rotulo FITOSANITARIOS. La v3.0 recortaba al simbolo y dejaba el rotulo
    fuera; criterio descartado por decision de marca.
  - SIN ESQUINAS REDONDEADAS. Los cuatro archivos son cuadrados opacos sobre
    blanco. iOS y Android aplican por su cuenta la mascara de la plataforma;
    aplicarla ademas en el archivo producia un doble redondeo y recortaba
    contenido.
  - El lienzo de origen ya cumple la zona segura para mascaras de Android:
    el contenido ocupa 409 x 387 px sobre 512, es decir el 80 % del ancho y
    el 75,6 % del alto, centrado. Por eso conservar el lienzo intacto es la
    opcion que mas contenido preserva bajo cualquier recorte del sistema.

CAMBIOS v3.0 respecto de v2.0:
  - Fuente nueva: LOGO_PATOLOGIA.png, 512x512 px, RGBA totalmente opaco.
    La v2.0 trabajaba sobre un lienzo de ~1280 px; todas las constantes de
    geometria se volvieron a medir y no son trasladables.
"""
import os
import numpy as np
from PIL import Image, ImageDraw

SRC = os.path.join(os.path.dirname(__file__), "..", "assets",
                   "logo-patologia-fuente.png")
OUT = os.path.join(os.path.dirname(__file__), "..")
os.makedirs(OUT, exist_ok=True)

WHITE = (255, 255, 255)

# --- Geometria medida sobre la fuente (perfiles de fila y columna) --------
# Simbolo (circulo + escudo + hoja + esporas): 157-345 x, 139-345 y.
# Rotulo "FITOSANITARIOS": filas 369-396.  Filigrana SPS: desde la fila 39.
# Simbolo 157-345 x, 139-345 y. Rotulo 369-396 y. Filigrana desde 39 y.
# Contenido total: filas 39-425, columnas 56-464.
BOX_CONTENT = (56, 39, 464, 425)

# El encuadre es el lienzo completo: no se recorta nada.
FRAME_CENTER = (256, 256)
FRAME_SIDE = 512


def _frame(side, center):
    cx, cy = center
    h = side // 2
    return (cx - h, cy - h, cx + h, cy + h)


def clean(img):
    """Reduce el ruido de la fuente sin alterar el diseno:
       - los pixeles casi-blancos pasan a blanco puro;
       - los grises de la filigrana se cuantizan a escalones de 8 niveles.
       Baja el peso del PNG y elimina el moteado del archivo de origen.
       No toca los verdes ni el carbon."""
    a = np.asarray(img.convert("RGB")).astype(int)
    r, g, b = a[:, :, 0], a[:, :, 1], a[:, :, 2]
    sat = np.abs(r - g) + np.abs(g - b) + np.abs(r - b)
    d = 255 * 3 - a.sum(axis=2)
    near_white = (sat < 12) & (d < 15)
    grey = (sat < 12) & (~near_white)
    snap = (a.sum(axis=2) // 3) // 8 * 8
    for i in range(3):
        a[:, :, i] = np.where(near_white, 255, a[:, :, i])
        a[:, :, i] = np.where(grey, snap, a[:, :, i])
    return Image.fromarray(a.astype("uint8"), "RGB")


def compose(size):
    """Cuadrado opaco sobre blanco, sin recorte ni redondeo, en todos los
       tamanos. El sobremuestreo x4 previo a la reduccion final evita el
       aliaseado en los trazos finos del rotulo."""
    ss = 4
    S = size * ss
    src = Image.open(SRC).convert("RGB")
    crop = src.crop(_frame(FRAME_SIDE, FRAME_CENTER))

    canvas = Image.new("RGB", (S, S), WHITE)
    canvas.paste(clean(crop).resize((S, S), Image.LANCZOS), (0, 0))
    return canvas.resize((size, size), Image.LANCZOS).convert("RGBA")


def save_png8(img, path, colors, flatten_to=None):
    if flatten_to is not None:
        bg = Image.new("RGBA", img.size, flatten_to + (255,))
        bg.alpha_composite(img)
        q = bg.convert("RGB").quantize(colors=colors,
                                       method=Image.MEDIANCUT, dither=Image.NONE)
    else:
        # FASTOCTREE es el unico metodo de Pillow que preserva el canal alfa.
        q = img.quantize(colors=colors, method=Image.FASTOCTREE, dither=Image.NONE)
    q.save(path, optimize=True)
    return os.path.getsize(path)


#          archivo                px  colores
TARGETS = [
    ("apple-touch-icon.png", 180,  64),
    ("icon-192.png",         192,  64),
    ("icon-512.png",         512,  96),
    ("favicon-32.png",        32,  32),
]

if __name__ == "__main__":
    print(f"encuadre: lienzo completo {FRAME_SIDE} px, sin recorte ni redondeo")
    print(f"{'archivo':<22}{'px':>5}{'bytes':>9}{'KiB':>7}")
    tot = 0
    for name, size, cols in TARGETS:
        # Todos se aplanan sobre blanco: sin canal alfa, sin esquinas cortadas.
        n = save_png8(compose(size), os.path.join(OUT, name), cols, WHITE)
        tot += n
        print(f"{name:<22}{size:>5}{n:>9}{n/1024:>7.1f}")
    print(f"{'TOTAL':<22}{'':>5}{tot:>9}{tot/1024:>7.1f}")
