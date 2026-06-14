// AlbaFrancia FM — Service Worker
// Stratégie : cache-first pour tout ce qui est déjà mis en cache,
// network-first + mise en cache pour les MP3/LRC au premier accès.

const CACHE = 'albafm-v1';

// Fichiers de l'app à mettre en cache immédiatement
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
        caches.open(CACHE).then(c => c.addAll(APP_SHELL)).then(() => self.skipWaiting())
    );
});

self.addEventListener('activate', e => {
    e.waitUntil(
        caches.keys().then(keys =>
            Promise.all(keys.filter(k=>k!==CACHE).map(k=>caches.delete(k)))
        ).then(() => self.clients.claim())
    );
});

self.addEventListener('fetch', e => {
    const url = new URL(e.request.url);

    // Cache-first pour tout ce qui est déjà en cache
    e.respondWith(
        caches.match(e.request).then(cached => {
            if (cached) return cached;
            // Network + mise en cache automatique
            return fetch(e.request).then(resp => {
                if (!resp || resp.status !== 200 || resp.type === 'opaque') return resp;
                const clone = resp.clone();
                caches.open(CACHE).then(c => c.put(e.request, clone));
                return resp;
            }).catch(() => {
                // Hors-ligne et pas en cache : réponse vide pour les MP3 (audio gère ça)
                return new Response('', { status: 503 });
            });
        })
    );
});

// ── Message "precache" envoyé par le player ─────────────────────────────
// Le player envoie { type:'PRECACHE', urls:[...] } avec la liste des MP3
self.addEventListener('message', e => {
    if (e.data?.type !== 'PRECACHE') return;
    const urls = e.data.urls || [];
    precacheList(urls, e.source);
});

async function precacheList(urls, client) {
    const cache = await caches.open(CACHE);
    let done = 0;
    for (const url of urls) {
        try {
            const already = await cache.match(url);
            if (!already) {
                const resp = await fetch(url);
                if (resp.ok) await cache.put(url, resp);
            }
        } catch {}
        done++;
        client?.postMessage({ type:'PRECACHE_PROGRESS', done, total:urls.length });
    }
    client?.postMessage({ type:'PRECACHE_DONE', total:urls.length });
}
