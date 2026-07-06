// Minimal app-shell service worker: caches this site's own static assets
// (stale-while-revalidate) so the PWA installs and opens offline. API
// calls go to a different origin (JUSTFITTING_API_BASE_URL) and are left
// untouched -- this worker never caches or intercepts them.
const CACHE_NAME = "justfitting-shell-v13";

const APP_SHELL = [
  "/",
  "/manifest.json",
  "/static/css/style.css",
  "/static/js/api.js",
  "/static/js/session.js",
  "/static/js/views.js",
  "/static/js/app.js",
  "/static/js/charts.js",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(APP_SHELL))
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(
          keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key))
        )
      )
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);
  if (event.request.method !== "GET" || url.origin !== self.location.origin) {
    return;
  }

  event.respondWith(
    caches.match(event.request).then((cached) => {
      const network = fetch(event.request)
        .then((response) => {
          if (response.ok) {
            const copy = response.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(event.request, copy));
          }
          return response;
        })
        .catch(() => cached);
      return cached || network;
    })
  );
});
