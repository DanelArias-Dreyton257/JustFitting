// Minimal app-shell service worker: caches this site's own static assets
// (stale-while-revalidate) so the PWA installs and opens offline. API
// calls go to a different origin (JUSTFITTING_API_BASE_URL) and are left
// untouched -- this worker never caches or intercepts them.
//
// The cache name is derived from a SHA-256 hash of the shell files' own
// bytes rather than a manually-bumped literal (Phase 5.1): editing any
// shell file changes the hash, which names a new cache, which the next
// `activate` purges every other `justfitting-shell-*` cache for. No
// version bump, ever, going forward.
const CACHE_PREFIX = "justfitting-shell-";

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

// Fetches every shell file fresh (bypassing any HTTP cache) so the hash
// below reflects each file's real current bytes, never a stale copy.
async function fetchShell() {
  return Promise.all(
    APP_SHELL.map(async (url) => ({ url, response: await fetch(url, { cache: "no-store" }) }))
  );
}

async function hashShell(entries) {
  const buffers = await Promise.all(entries.map(({ response }) => response.clone().arrayBuffer()));
  const totalLength = buffers.reduce((sum, buffer) => sum + buffer.byteLength, 0);
  const concatenated = new Uint8Array(totalLength);
  let offset = 0;
  for (const buffer of buffers) {
    concatenated.set(new Uint8Array(buffer), offset);
    offset += buffer.byteLength;
  }
  const digest = await crypto.subtle.digest("SHA-256", concatenated);
  const hex = Array.from(new Uint8Array(digest))
    .map((byte) => byte.toString(16).padStart(2, "0"))
    .join("");
  return CACHE_PREFIX + hex.slice(0, 16);
}

self.addEventListener("install", (event) => {
  event.waitUntil(
    (async () => {
      const entries = await fetchShell();
      const cacheName = await hashShell(entries);
      const cache = await caches.open(cacheName);
      await Promise.all(entries.map(({ url, response }) => cache.put(url, response)));
      self.skipWaiting();
    })()
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    (async () => {
      const currentName = await hashShell(await fetchShell());
      const keys = await caches.keys();
      await Promise.all(
        keys
          .filter((key) => key.startsWith(CACHE_PREFIX) && key !== currentName)
          .map((key) => caches.delete(key))
      );
      self.clients.claim();
    })()
  );
});

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);
  if (event.request.method !== "GET" || url.origin !== self.location.origin) {
    return;
  }

  event.respondWith(
    caches.match(event.request).then((cached) => {
      const network = fetch(event.request)
        .then(async (response) => {
          if (response.ok) {
            const keys = await caches.keys();
            const shellKey = keys.find((key) => key.startsWith(CACHE_PREFIX));
            if (shellKey) {
              const cache = await caches.open(shellKey);
              cache.put(event.request, response.clone());
            }
          }
          return response;
        })
        .catch(() => cached);
      return cached || network;
    })
  );
});
