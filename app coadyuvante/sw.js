/* Service Worker — Receta Pesticidas y Coadyuvantes SPS
   Estrategia: "stale-while-revalidate".
   - Offline: sirve desde caché lo ya visitado.
   - Online: entrega rápido lo cacheado y, en segundo plano, baja la versión nueva
     y la guarda. Así, tras cada actualización que subamos, la app toma los cambios
     en la siguiente apertura con conexión. Sube CACHE_VERSION en cambios grandes.
*/
const CACHE_VERSION = "receta-sps-v5.0";
const PRECACHE = [
  "./",
  "manifest.json",
  "icon-192.png",
  "icon-512.png"
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_VERSION)
      .then((cache) => cache.addAll(PRECACHE).catch(() => {}))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE_VERSION).map((k) => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return;

  event.respondWith(
    caches.match(req).then((cached) => {
      const network = fetch(req)
        .then((resp) => {
          if (resp && resp.status === 200 && (resp.type === "basic" || resp.type === "cors")) {
            const clone = resp.clone();
            caches.open(CACHE_VERSION).then((c) => c.put(req, clone));
          }
          return resp;
        })
        .catch(() => cached);
      return cached || network;
    })
  );
});
