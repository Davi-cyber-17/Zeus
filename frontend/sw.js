/**
 * Zeus AI — Service Worker
 * ===========================
 * Cacheia apenas o "app shell" estático (HTML/CSS/JS/ícone), permitindo
 * instalar o Zeus como app e abrir a interface mesmo offline. Chamadas à
 * API (chat, documentos, etc.) sempre vão direto para a rede — elas
 * dependem do backend estar rodando e nunca devem ser servidas do cache.
 */
const CACHE_NAME = "zeus-shell-v1";
const APP_SHELL = ["./", "./index.html", "./styles.css", "./app.js", "./icon.svg", "./manifest.json"];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(APP_SHELL)).then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);

  // Só intercepta requisições GET para o próprio app shell (mesma origem).
  // Qualquer chamada de API (mesma origem ou não) segue direto para a rede.
  const isAppShellRequest =
    event.request.method === "GET" && url.origin === self.location.origin && !url.pathname.startsWith("/api/");

  if (!isAppShellRequest) return;

  event.respondWith(
    caches.match(event.request).then((cached) => {
      return (
        cached ||
        fetch(event.request)
          .then((response) => {
            const clone = response.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(event.request, clone));
            return response;
          })
          .catch(() => cached)
      );
    })
  );
});
