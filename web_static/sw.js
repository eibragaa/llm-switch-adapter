/**
 * Switch Adapter Dashboard — Service Worker
 * Cache-first for static assets, network-first for API
 * Version: 1.0.0
 */

const CACHE_NAME = 'switch-adapter-v1';
const STATIC_CACHE = 'switch-adapter-static-v1';
const API_CACHE = 'switch-adapter-api-v1';

// Assets to cache on install
const STATIC_ASSETS = [
  '/',
  '/static/css/design.css',
  '/static/js/app.js',
  '/static/manifest.json',
  'https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700&family=Space+Grotesk:wght@400;500;600;700&display=swap',
  'https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js',
];

// API endpoints that should be network-first
const API_PATTERNS = [
  '/api/',
];

// Maximum age for cached API responses (5 minutes)
const API_MAX_AGE = 5 * 60 * 1000;

// ─── Install Event ────────────────────────────────────────────────────────

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(STATIC_CACHE).then((cache) => {
      // Don't fail install if some assets can't be cached
      return Promise.allSettled(
        STATIC_ASSETS.map((url) => 
          cache.add(url).catch((err) => console.warn('SW: Failed to cache', url, err))
        )
      );
    }).then(() => self.skipWaiting())
  );
});

// ─── Activate Event ───────────────────────────────────────────────────────

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames
          .filter((name) => name !== STATIC_CACHE && name !== API_CACHE)
          .map((name) => caches.delete(name))
      );
    }).then(() => self.clients.claim())
  );
});

// ─── Fetch Event ──────────────────────────────────────────────────────────

self.addEventListener('fetch', (event) => {
  const { request } = event;
  const url = new URL(request.url);
  
  // Skip non-GET requests
  if (request.method !== 'GET') return;
  
  // Skip cross-origin requests (except known CDNs)
  if (url.origin !== location.origin && !isKnownCDN(url.origin)) {
    return;
  }
  
  // API requests: network-first with cache fallback
  if (isAPIRequest(url)) {
    event.respondWith(networkFirstAPI(request));
    return;
  }
  
  // Static assets: cache-first
  event.respondWith(cacheFirst(request));
});

// ─── Helper Functions ─────────────────────────────────────────────────────

function isKnownCDN(origin) {
  const knownCDNs = [
    'https://fonts.googleapis.com',
    'https://fonts.gstatic.com',
    'https://cdn.jsdelivr.net',
  ];
  return knownCDNs.includes(origin);
}

function isAPIRequest(url) {
  return API_PATTERNS.some((pattern) => url.pathname.startsWith(pattern));
}

async function cacheFirst(request) {
  const cached = await caches.match(request);
  if (cached) {
    // Check if we should update in background
    if (shouldUpdate(cached)) {
      fetchAndCache(request);
    }
    return cached;
  }
  
  return fetchAndCache(request);
}

async function networkFirstAPI(request) {
  try {
    const response = await fetch(request);
    
    // Only cache successful responses
    if (response.ok) {
      const cache = await caches.open(API_CACHE);
      // Clone before caching since response body can only be read once
      cache.put(request, response.clone());
    }
    
    return response;
  } catch (error) {
    // Network failed, try cache
    const cached = await caches.match(request);
    if (cached) {
      // Add header to indicate stale data
      const staleResponse = cached.clone();
      staleResponse.headers.set('X-SW-Stale', 'true');
      return staleResponse;
    }
    
    // No cache, return offline response
    return new Response(JSON.stringify({ 
      error: 'Offline', 
      message: 'Sem conexão e sem dados em cache',
      cached: false 
    }), {
      status: 503,
      headers: { 'Content-Type': 'application/json' }
    });
  }
}

async function fetchAndCache(request) {
  try {
    const response = await fetch(request);
    if (response.ok) {
      const cache = await caches.open(STATIC_CACHE);
      cache.put(request, response.clone());
    }
    return response;
  } catch (error) {
    // Return a minimal offline page for navigation requests
    if (request.mode === 'navigate') {
      return caches.match('/') || new Response('Offline', { status: 503 });
    }
    throw error;
  }
}

function shouldUpdate(cachedResponse) {
  const dateHeader = cachedResponse.headers.get('date');
  if (!dateHeader) return true;
  
  const cachedTime = new Date(dateHeader).getTime();
  const now = Date.now();
  const age = now - cachedTime;
  
  // Update if older than 1 hour
  return age > 60 * 60 * 1000;
}

// ─── Message Handling ─────────────────────────────────────────────────────

self.addEventListener('message', (event) => {
  if (event.data === 'skipWaiting') {
    self.skipWaiting();
  }
  
  if (event.data === 'getVersion') {
    event.ports[0].postMessage({ version: CACHE_NAME });
  }
  
  if (event.data === 'clearCache') {
    caches.keys().then((names) => 
      Promise.all(names.map((name) => caches.delete(name)))
    ).then(() => event.ports[0].postMessage({ success: true }));
  }
});

// ─── Periodic Cleanup ─────────────────────────────────────────────────────

// Clean up old API cache entries periodically
setInterval(async () => {
  const cache = await caches.open(API_CACHE);
  const keys = await cache.keys();
  const now = Date.now();
  
  for (const request of keys) {
    const response = await cache.match(request);
    const dateHeader = response.headers.get('date');
    if (dateHeader) {
      const cachedTime = new Date(dateHeader).getTime();
      if (now - cachedTime > API_MAX_AGE) {
        await cache.delete(request);
      }
    }
  }
}, 60 * 60 * 1000); // Every hour