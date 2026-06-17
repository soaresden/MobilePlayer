// AlbaFrancia FM — Service Worker v2
// Fix principal : les navigateurs utilisent des Range requests pour l'audio.
// Un SW qui renvoie 200 au lieu de 206 bloque la lecture. On gère ça ici.

const CACHE = 'albafm-v2';

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
            .then(c => c.addAll(APP_SHELL))
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

// ── Fetch handler ─────────────────────────────────────────────────────────────
self.addEventListener('fetch', e => {
    // Range requests (audio streaming) → traitement spécial
    if (e.request.headers.has('Range')) {
        e.respondWith(handleRangeRequest(e.request));
        return;
    }

    // Cache-first pour tout le reste
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

// ── Gestion des Range requests ────────────────────────────────────────────────
// Le navigateur demande e.g. "Range: bytes=0-" ou "bytes=65536-131071"
// On sert la tranche depuis le fichier complet stocké en cache (status 200).
async function handleRangeRequest(request) {
    const cache  = await caches.open(CACHE);
    // Chercher le fichier complet (la clé cache est l'URL sans Range)
    const cached = await cache.match(new Request(request.url));

    if (!cached) {
        // Pas en cache → réseau (online) ou erreur (offline)
        try { return await fetch(request); }
        catch { return new Response('', { status: 503 }); }
    }

    // Parser l'en-tête Range
    const rangeHeader = request.headers.get('Range') || 'bytes=0-';
    const m = /bytes=(\d*)-(\d*)/.exec(rangeHeader);
    const blob  = await cached.blob();
    const total = blob.size;

    let start = m && m[1] !== '' ? parseInt(m[1]) : 0;
    let end   = m && m[2] !== '' ? parseInt(m[2]) : total - 1;
    // Cas "suffix-length" (bytes=-500)
    if (m && m[1] === '' && m[2] !== '') { start = Math.max(0, total - parseInt(m[2])); end = total - 1; }
    end = Math.min(end, total - 1);

    const sliced = blob.slice(start, end + 1);
    return new Response(sliced, {
        status:     206,
        statusText: 'Partial Content',
        headers: {
            'Content-Type':   cached.headers.get('Content-Type') || 'audio/mpeg',
            'Content-Range':  `bytes ${start}-${end}/${total}`,
            'Content-Length': String(sliced.size),
            'Accept-Ranges':  'bytes',
        },
    });
}

// ── Message PRECACHE ──────────────────────────────────────────────────────────
self.addEventListener('message', e => {
    if (e.data?.type !== 'PRECACHE') return;
    precacheList(e.data.urls || [], e.source);
});

async function precacheList(urls, client) {
    const cache = await caches.open(CACHE);
    let done = 0;
    for (const url of urls) {
        try {
            const already = await cache.match(new Request(url));
            if (!already) {
                const resp = await fetch(url);
                if (resp.ok) await cache.put(url, resp);
            }
        } catch {}
        done++;
        client?.postMessage({ type: 'PRECACHE_PROGRESS', done, total: urls.length });
    }
    client?.postMessage({ type: 'PRECACHE_DONE', total: urls.length });
}
