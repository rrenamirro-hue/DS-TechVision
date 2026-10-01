'use strict';
const CACHE = 'ds-techvision-public-v03';
const PUBLIC_ASSETS = ['/static/style.css', '/static/login.js', '/static/icons/icon-192.png', '/static/icons/icon-512.png'];
self.addEventListener('install', (event) => event.waitUntil(caches.open(CACHE).then((cache) => cache.addAll(PUBLIC_ASSETS))));
self.addEventListener('activate', (event) => event.waitUntil(caches.keys().then((keys) => Promise.all(keys.filter((key) => key !== CACHE).map((key) => caches.delete(key))))));
self.addEventListener('fetch', (event) => { const url = new URL(event.request.url); if (event.request.method !== 'GET' || url.origin !== self.location.origin || url.pathname.startsWith('/api/') || url.pathname === '/' || url.pathname === '/login') return; if (PUBLIC_ASSETS.includes(url.pathname)) event.respondWith(caches.match(event.request).then((cached) => cached || fetch(event.request))); });
