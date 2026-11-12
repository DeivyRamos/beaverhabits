const CACHE_NAME = 'beaverhabits_v1';
const CACHE_URLS = [
];

// WebSocket connections to be excluded from the fetch handler
const WEBSOCKET_URLS = [
    'wss://',
    'ws://'
];

self.addEventListener('install', (event) => {
    event.waitUntil(
        caches.open(CACHE_NAME).then((cache) => {

            return Promise.all(
                CACHE_URLS.map(url => {
                    return cache.add(url).catch(error => {
                        console.error('Failed to cache:', url, error);
                    });
                })
            );
        })
    );
});

self.addEventListener('fetch', (event) => {
    // Check if the request is for a WebSocket
    if (WEBSOCKET_URLS.some(wsUrl => event.request.url.startsWith(wsUrl))) {
        // Don't interfere with WebSocket connections
        return;
    }

    event.respondWith(
        caches.match(event.request).then((response) => {
            return response || fetch(event.request);
        })
    );
});

self.addEventListener('activate', (event) => {
    const cacheWhitelist = [CACHE_NAME];
    event.waitUntil(
        caches.keys().then((cacheNames) => {
            return Promise.all(
                cacheNames.map((cacheName) => {
                    if (cacheWhitelist.indexOf(cacheName) === -1) {
                        return caches.delete(cacheName);
                    }
                })
            );
        })
    );
});

// Handle WebSocket keep-alive
self.addEventListener('message', (event) => {
    if (event.data === 'keepalive') {
        // Respond to keep-alive messages
        event.ports[0].postMessage('alive');
    }
});

// Daily reminders (Web Push)
self.addEventListener('push', (event) => {
    let data = {};
    try { data = event.data ? event.data.json() : {}; } catch (e) { data = { body: event.data && event.data.text() }; }
    const title = data.title || 'MenosClick Hábitos';
    event.waitUntil(self.registration.showNotification(title, {
        body: data.body || '',
        icon: '/statics/images/apple-touch-icon-v4.png',
        badge: '/statics/images/apple-touch-icon.png',
        tag: 'daily-reminder',
        renotify: true,
        data: { url: data.url || '/gui' },
    }));
});

self.addEventListener('notificationclick', (event) => {
    event.notification.close();
    const url = (event.notification.data && event.notification.data.url) || '/gui';
    event.waitUntil(clients.matchAll({ type: 'window', includeUncontrolled: true }).then((list) => {
        for (const client of list) {
            if (client.url.includes('/gui') && 'focus' in client) return client.focus();
        }
        return clients.openWindow(url);
    }));
});
