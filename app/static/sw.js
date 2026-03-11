const CACHE_NAME = 'queue-v1';

self.addEventListener('install', (event) => {
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(clients.claim());
});

// ── Push notification handler ─────────────────────────────────────────────────

self.addEventListener('push', (event) => {
  let data = { title: 'Queue Update', body: 'Your number has been called!' };
  try {
    data = event.data.json();
  } catch (e) {}

  event.waitUntil(
    self.registration.showNotification(data.title, {
      body: data.body,
      icon: '/static/icon-192.png',
      badge: '/static/icon-192.png',
      vibrate: [200, 100, 200],
      data: { url: '/status' },
    })
  );
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then((clientList) => {
      for (const client of clientList) {
        if (client.url.includes('/status') && 'focus' in client) {
          return client.focus();
        }
      }
      if (clients.openWindow) {
        return clients.openWindow('/status');
      }
    })
  );
});
