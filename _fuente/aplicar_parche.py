#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
aplicar_parche.py — v1.0 · 30-07-2026
Convierte index.html en PWA instalable SIN alterar una sola linea de contenido.

(c) 2026 Winston Colvin - South Pacific Seeds Chile S.A.

POR QUE UN SCRIPT Y NO UNA EDICION A MANO
-----------------------------------------
index.html mide 870.428 bytes y los tres modulos viajan inline dentro del
atributo data-doc de sus iframes. Como consecuencia:

    '</body>' aparece 4 veces en el archivo
    '</head>' aparece 4 veces en el archivo

Solo UNA de cada cuatro pertenece al documento contenedor; las otras tres estan
dentro de los documentos embebidos. Un buscar-y-reemplazar sobre '</body>'
insertaria el registro del service worker DENTRO del data-doc de un modulo,
rompiendolo. Este script ancla en dos cadenas verificadas como UNICAS:

    ANCLA_HEAD  = '</style></head>'                      -> 1 ocurrencia
    ANCLA_FINAL = "  show('malezas');\\n})();\\n</script>\\n</body></html>"
                                                          -> 1 ocurrencia

PRUEBA DE INTEGRIDAD
--------------------
Tras insertar, el script REVIERTE los dos bloques en memoria y compara el
resultado con el original byte a byte y por SHA-256. Si no coincide, aborta y no
escribe nada. Es la garantia formal de que el parche es puramente aditivo.
"""

import hashlib
import os
import shutil
import sys

VERSION = "1.0"
FECHA = "2026-07-30"

ENTRADA = "index_orig.html"
SALIDA = "index.html"

ANCLA_HEAD = "</style></head>"
ANCLA_FINAL = "  show('malezas');\n})();\n</script>\n</body></html>"

# --------------------------------------------------------------------------
# BLOQUE 1 — cabecera PWA. Se inserta INMEDIATAMENTE ANTES de </head>.
# --------------------------------------------------------------------------
BLOQUE_HEAD = """
<!-- ==== PWA · Fitosanitario SPS · v1.0 · 2026-07-30 · bloque aditivo ==== -->
<link rel="manifest" href="manifest.json">
<meta name="theme-color" content="#14366E">
<meta name="color-scheme" content="light">
<link rel="icon" type="image/png" sizes="32x32" href="favicon-32.png">
<link rel="icon" type="image/png" sizes="192x192" href="icon-192.png">
<link rel="apple-touch-icon" sizes="180x180" href="apple-touch-icon.png">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="default">
<meta name="apple-mobile-web-app-title" content="Fitosanitario">
<meta name="application-name" content="Fitosanitario SPS">
<!-- ==== fin bloque PWA (cabecera) ==== -->
"""

# --------------------------------------------------------------------------
# BLOQUE 2 — registro del service worker. Se inserta ANTES de </body></html>.
# Envuelto en IIFE y try/catch: si el navegador no soporta service workers
# (o la pagina se abre por file://), no lanza y la app sigue funcionando igual.
# --------------------------------------------------------------------------
BLOQUE_FINAL = """
<!-- ==== PWA · Fitosanitario SPS · registro del service worker · bloque aditivo ==== -->
<script>
(function(){
  "use strict";
  if (!('serviceWorker' in navigator)) return;
  if (location.protocol !== 'https:' && location.hostname !== 'localhost') return;

  window.addEventListener('load', function(){
    navigator.serviceWorker.register('sw.js', { scope: './' })
      .then(function(reg){
        /* Si ya hay un SW controlando y aparece uno nuevo en espera, se le
           ordena tomar el control de inmediato. La version nueva queda activa
           al siguiente arranque en frio (cerrar por completo y reabrir). */
        reg.addEventListener('updatefound', function(){
          var nuevo = reg.installing;
          if (!nuevo) return;
          nuevo.addEventListener('statechange', function(){
            if (nuevo.state === 'installed' && navigator.serviceWorker.controller) {
              nuevo.postMessage({ tipo: 'SKIP_WAITING' });
            }
          });
        });
        /* Comprobacion de actualizacion al abrir y cada 60 min de uso. */
        try { reg.update(); } catch(e){}
        setInterval(function(){ try { reg.update(); } catch(e){} }, 3600000);
      })
      .catch(function(){ /* sin service worker la app funciona online igual */ });

    /* Purga manual de cache: se engancha al boton existente
       "Actualizaciones" solo con Alt/Option pulsado, para no interferir con su
       funcion normal de abrir el panel de fuentes. */
    var b = document.getElementById('shellupd');
    if (b) b.addEventListener('click', function(ev){
      if (!ev.altKey) return;
      ev.stopImmediatePropagation();
      if (navigator.serviceWorker.controller) {
        navigator.serviceWorker.controller.postMessage({ tipo: 'PURGAR' });
      }
      if (window.caches && caches.keys) {
        caches.keys().then(function(ks){ return Promise.all(ks.map(function(k){ return caches.delete(k); })); })
              .then(function(){ location.reload(); });
      } else { location.reload(); }
    }, true);
  });
})();
</script>
<!-- ==== fin bloque PWA (registro) ==== -->
"""


def sha(texto):
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def main():
    if not os.path.exists(ENTRADA):
        sys.exit("No se encuentra %s" % ENTRADA)

    with open(ENTRADA, encoding="utf-8") as fh:
        original = fh.read()

    print("aplicar_parche.py v%s - %s" % (VERSION, FECHA))
    print("Origen : %s  (%d bytes, sha256 %s)"
          % (ENTRADA, len(original.encode("utf-8")), sha(original)[:16]))

    # --- verificacion de unicidad de anclas -------------------------------
    for nombre, ancla in (("ANCLA_HEAD", ANCLA_HEAD), ("ANCLA_FINAL", ANCLA_FINAL)):
        n = original.count(ancla)
        print("  %-12s ocurrencias = %d %s" % (nombre, n, "OK" if n == 1 else "ABORTA"))
        if n != 1:
            sys.exit("Ancla no unica. No se escribe nada.")

    # --- insercion --------------------------------------------------------
    parcheado = original.replace(ANCLA_HEAD, BLOQUE_HEAD + ANCLA_HEAD, 1)
    parcheado = parcheado.replace(
        ANCLA_FINAL,
        ANCLA_FINAL.replace("</body></html>", "") + BLOQUE_FINAL + "</body></html>",
        1)

    # --- prueba de integridad: revertir y comparar ------------------------
    revertido = parcheado.replace(BLOQUE_HEAD, "", 1).replace(BLOQUE_FINAL, "", 1)
    if revertido != original or sha(revertido) != sha(original):
        sys.exit("PRUEBA DE INTEGRIDAD FALLIDA. No se escribe nada.")

    add = len(parcheado.encode("utf-8")) - len(original.encode("utf-8"))
    print("\nPRUEBA DE INTEGRIDAD: superada (revertido == original, sha256 identico)")
    print("Bytes anadidos: %d  (+%.3f %% sobre el original)"
          % (add, 100.0 * add / len(original.encode("utf-8"))))
    print("Lineas anadidas: %d" % (parcheado.count("\n") - original.count("\n")))
    print("Contenido tecnico modificado: NINGUNO (parche estrictamente aditivo)")

    if os.path.abspath(ENTRADA) != os.path.abspath(SALIDA):
        shutil.copyfile(ENTRADA, ENTRADA + ".bak")
    with open(SALIDA, "w", encoding="utf-8") as fh:
        fh.write(parcheado)
    print("\nEscrito: %s  (%d bytes, sha256 %s)"
          % (SALIDA, len(parcheado.encode("utf-8")), sha(parcheado)[:16]))


if __name__ == "__main__":
    main()
