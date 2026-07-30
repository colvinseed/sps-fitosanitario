/*  sw.js — Service Worker · Fitosanitario SPS
 *  v1.0 · 30-07-2026
 *  © 2026 Winston Colvin — South Pacific Seeds Chile S.A.
 *
 *  ---------------------------------------------------------------------------
 *  FUNDAMENTO DE LAS DECISIONES  /  DESIGN RATIONALE
 *  ---------------------------------------------------------------------------
 *  1. CACHE_VERSION es el unico punto a editar en cada despliegue. Al cambiarlo
 *     se crea una cache nueva y se purgan todas las anteriores en 'activate'.
 *     Sin este cambio de nombre el navegador puede servir el index.html viejo
 *     indefinidamente: el truco de anexar ?x=1 a la URL NO evade un service
 *     worker, porque el SW intercepta la peticion antes de que salga a la red.
 *
 *  2. Navegacion = NETWORK-FIRST con respaldo en cache.
 *     La aplicacion es un unico index.html de ~870 KB que contiene TODOS los
 *     datos (los tres modulos viajan inline como data-doc en sus iframes; se
 *     verifico que la app no ejecuta fetch() ni XMLHttpRequest). Por lo tanto
 *     "actualizar los datos" equivale a "descargar un index.html nuevo".
 *     Un cache-first dejaria congelados los registros SAG/APVMA/ACVM hasta un
 *     borrado manual: inaceptable en una herramienta regulatoria. Se resuelve
 *     con red primero y un tope de 6 s, tras el cual se sirve la copia local.
 *
 *  3. Assets estaticos (iconos, manifiesto) = STALE-WHILE-REVALIDATE.
 *     Respuesta inmediata desde cache y refresco en segundo plano. Son bytes
 *     que no cambian entre despliegues; no justifican esperar la red.
 *
 *  4. Solo se cachea el mismo origen y solo peticiones GET. Se excluye
 *     explicitamente el enlace externo de licencia (creativecommons.org), que
 *     no es necesario offline y cuya respuesta opaca ocuparia cache sin uso.
 *
 *  5. skipWaiting() + clients.claim() inmediatos. Se asume el control en el
 *     primer arranque y la version nueva queda activa al siguiente inicio en
 *     frio de la app (cerrar por completo y reabrir). Es el comportamiento ya
 *     validado en terreno para las otras herramientas del departamento.
 *  ---------------------------------------------------------------------------
 */

'use strict';

/* >>> EDITAR EN CADA DESPLIEGUE <<< */
const CACHE_VERSION = 'fito-sps-v2.6.0';

const PRECACHE = [
  './',
  './index.html',
  './manifest.json',
  './icon-192.png',
  './icon-512.png',
  './icon-maskable-192.png',
  './icon-maskable-512.png',
  './apple-touch-icon.png',
  './favicon-32.png'
];

const RED_TIMEOUT_MS = 6000;

/* ---------------------------------------------------------------- install */
self.addEventListener('install', (event) => {
  event.waitUntil((async () => {
    const cache = await caches.open(CACHE_VERSION);
    /* Se cachea pieza por pieza en vez de cache.addAll(): addAll() rechaza el
       lote completo si UN solo recurso devuelve 404, lo que dejaria el SW sin
       instalar y la app sin funcionamiento offline. Asi un asset ausente
       degrada esa pieza, no la instalacion. */
    await Promise.all(PRECACHE.map(async (url) => {
      try {
        const res = await fetch(new Request(url, { cache: 'reload' }));
        if (res && res.ok) await cache.put(url, res.clone());
      } catch (e) {
        /* silencioso: se registra la ausencia, no se aborta la instalacion */
      }
    }));
    await self.skipWaiting();
  })());
});

/* --------------------------------------------------------------- activate */
self.addEventListener('activate', (event) => {
  event.waitUntil((async () => {
    const nombres = await caches.keys();
    await Promise.all(
      nombres.filter((n) => n !== CACHE_VERSION).map((n) => caches.delete(n))
    );
    if (self.registration.navigationPreload) {
      try { await self.registration.navigationPreload.disable(); } catch (e) {}
    }
    await self.clients.claim();
  })());
});

/* ------------------------------------------------------------------ fetch */
function conTimeout(promesa, ms) {
  return new Promise((resolve, reject) => {
    const t = setTimeout(() => reject(new Error('timeout')), ms);
    promesa.then((v) => { clearTimeout(t); resolve(v); },
                 (e) => { clearTimeout(t); reject(e); });
  });
}

async function networkFirst(request) {
  const cache = await caches.open(CACHE_VERSION);
  try {
    const res = await conTimeout(fetch(request), RED_TIMEOUT_MS);
    if (res && res.ok) {
      cache.put(request, res.clone()).catch(() => {});
      return res;
    }
    throw new Error('respuesta no ok: ' + (res && res.status));
  } catch (e) {
    const local = await cache.match(request, { ignoreSearch: true })
               || await cache.match('./index.html')
               || await cache.match('./');
    if (local) return local;
    return new Response(
      '<!DOCTYPE html><meta charset="utf-8">' +
      '<body style="font:15px -apple-system,sans-serif;padding:28px;color:#14366E">' +
      '<h3>Sin conexion y sin copia local</h3>' +
      '<p>Abra la aplicacion una vez con conexion para habilitar el uso offline.</p>' +
      '<p style="color:#5a6b7a;font-size:12px">Fitosanitario SPS · ' + CACHE_VERSION + '</p>',
      { status: 503, headers: { 'Content-Type': 'text/html; charset=utf-8' } }
    );
  }
}

async function staleWhileRevalidate(request) {
  const cache = await caches.open(CACHE_VERSION);
  const local = await cache.match(request, { ignoreSearch: true });
  const refresco = fetch(request).then((res) => {
    if (res && res.ok) cache.put(request, res.clone()).catch(() => {});
    return res;
  }).catch(() => null);
  return local || (await refresco) || Response.error();
}

self.addEventListener('fetch', (event) => {
  const req = event.request;
  if (req.method !== 'GET') return;

  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return;   // externos: sin intervencion

  if (req.mode === 'navigate' || req.destination === 'document') {
    event.respondWith(networkFirst(req));
    return;
  }
  event.respondWith(staleWhileRevalidate(req));
});

/* --------------------------------------------------------------- mensajes */
self.addEventListener('message', (event) => {
  const data = event.data || {};
  if (data.tipo === 'SKIP_WAITING') self.skipWaiting();

  if (data.tipo === 'PURGAR') {
    event.waitUntil((async () => {
      const nombres = await caches.keys();
      await Promise.all(nombres.map((n) => caches.delete(n)));
      const clientes = await self.clients.matchAll({ type: 'window' });
      clientes.forEach((c) => c.postMessage({ tipo: 'PURGADO' }));
    })());
  }

  if (data.tipo === 'VERSION') {
    event.source && event.source.postMessage({ tipo: 'VERSION', valor: CACHE_VERSION });
  }
});
