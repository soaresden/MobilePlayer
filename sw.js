// AlbaFrancia FM — Service Worker
// Rôle : cache l'app shell (HTML, JS, CSS, icônes) pour que la page charge hors-ligne.
// L'audio est géré par IndexedDB directement depuis la page (pas besoin de HTTPS).

const CACHE = 'albafm-shell-v1';

const APP_SHELL = [
    '/',
    '/index.html',
    '/config.js',
    '/playlist.js',
    '/jingles.js',
    '/cover.png',
    'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css',
    'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/webfonts/fa-solid-900.woff2',
    'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/webfonts/fa-brands-400.woff2',
];

self.addEventListener('install', e => {
    e.waitUntil(
        caches.open(CACHE)
            .then(c => Promise.allSettled(APP_SHELL.map(u => c.add(u))))
            .then(() => self.skipWaiting())
    );
});

self.addEventListener('activate', e => {
    e.waitUntil(
        caches.keys()
            .then(keys => Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k))))
            .then(() => self.clients.claim())
    );
});

self.addEventListener('fetch', e => {
    // Ne pas intercepter les requêtes audio (blobs gérés par IndexedDB côté page)
    const url = e.request.url;
    if (url.includes('/music/') || url.includes('/suno/') || url.includes('/jingles/')) return;

    e.respondWith(
        caches.match(e.request).then(cached => {
            if (cached) return cached;
            return fetch(e.request).then(resp => {
                if (!resp || resp.status !== 200 || resp.type === 'opaque') return resp;
                const clone = resp.clone();
                caches.open(CACHE).then(c => c.put(e.request, clone));
                return resp;
            }).catch(() => new Response('', { status: 503 }));
        })
    );
});
