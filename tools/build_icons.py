#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_icons.py - v2.0 - 30-07-2026
Juego de iconos de aplicacion "Pathology Forecast" derivado de
Pathology_Forecast_Logo_2.png (marca combinada: simbolo lupa-hoja sobre
monograma SPS en filigrana).
(c) 2026 Winston Colvin - South Pacific Seeds Chile
"""
import os
import numpy as np
from PIL import Image, ImageDraw

SRC = "/mnt/user-data/uploads/Pathology_Forecast_Logo_2.png"
OUT = "/home/claude/out"
os.makedirs(OUT, exist_ok=True)

WHITE = (255, 255, 255)

# --- Geometria medida sobre la fuente (no supuesta) -----------------------
# Bandas de contenido por perfil de filas: 135-830 grafico,
# 857-938 "PATHOLOGY", 949-1006 "FORECAST".
BOX_WATERMARK = (221, 135, 1074, 831)   # monograma SPS en filigrana
BOX_SYMBOL    = (417, 339,  848, 813)   # lupa + hoja + esporas

# Encuadre elegido: cuadrado de 760 px centrado en (640, 520).
FRAME_SIDE   = 760
FRAME_CENTER = (640, 558)

RADIUS = 0.225                          # squircle iOS / Android


def _frame(side, center):
    cx, cy = center
    h = side // 2
    return (cx - h, cy - h, cx + h, cy + h)



def clean(img):
    """Reduce el ruido de la fuente sin alterar el diseno:
       - los pixeles casi-blancos pasan a blanco puro (59 % del lienzo);
       - los grises de la filigrana se cuantizan a escalones de 8 niveles.
       Baja el peso del PNG a cerca de un tercio y elimina el moteado
       propio del archivo de origen. No toca los verdes ni el carbon."""
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


def compose(size, rounded, simplified=False):
    """rounded=False   -> cuadrado a sangre (requisito de apple-touch-icon)
       rounded=True    -> squircle con esquinas transparentes
       simplified=True -> solo el simbolo; reservado para 32 px"""
    ss = 4
    S = size * ss
    src = Image.open(SRC).convert("RGB")

    if simplified:
        x0, y0, x1, y1 = BOX_SYMBOL
        pad = int(0.13 * max(x1 - x0, y1 - y0))
        s = max(x1 - x0, y1 - y0) + 2 * pad
        cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
        crop = src.crop(_frame(s, (cx, cy)))
    else:
        crop = src.crop(_frame(FRAME_SIDE, FRAME_CENTER))

    canvas = Image.new("RGB", (S, S), WHITE)
    canvas.paste(clean(crop).resize((S, S), Image.LANCZOS), (0, 0))
    out = canvas.convert("RGBA")

    if rounded:
        m = Image.new("L", (S, S), 0)
        ImageDraw.Draw(m).rounded_rectangle(
            [0, 0, S - 1, S - 1], radius=int(RADIUS * S), fill=255)
        out.putalpha(m)

    return out.resize((size, size), Image.LANCZOS)


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


#          archivo                px  redondeo  colores  aplanar  simplificado
TARGETS = [
    ("apple-touch-icon.png", 180, False,  48, WHITE, False),
    ("icon-192.png",         192, True,   48, None,  False),
    ("icon-512.png",         512, True,   64, None,  False),
    ("favicon-32.png",        32, True,    16, None,  True),
]

if __name__ == "__main__":
    print(f"{'archivo':<22}{'px':>5}{'squircle':>10}{'simpl.':>8}{'bytes':>8}{'KiB':>7}")
    tot = 0
    for name, size, rnd, cols, flat, simp in TARGETS:
        n = save_png8(compose(size, rnd, simp), os.path.join(OUT, name), cols, flat)
        tot += n
        print(f"{name:<22}{size:>5}{('si' if rnd else 'no'):>10}"
              f"{('si' if simp else 'no'):>8}{n:>8}{n/1024:>7.1f}")
    print(f"{'TOTAL':<22}{'':>5}{'':>10}{'':>8}{tot:>8}{tot/1024:>7.1f}")
