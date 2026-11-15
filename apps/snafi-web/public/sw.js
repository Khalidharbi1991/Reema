/* Snafi service worker (steps 1 and 5).
 * Caches only public static files (icons, manifest, offline page, built JS/CSS/fonts).
 * Pages and anything signed-in always go to the network and are never cached,
 * so no personal data is stored on the phone by this worker.
 *
 * Step 5, Web Push: a push carries only {k: kind, l: language, n: id} (the PC worker never sends
 * more). The notification shows FIXED text for that kind, so the lock screen never shows anything
 * private: no sender, subject, reminder text or brief. Tapping it opens Today, where the card
 * with the details waits behind sign-in.
 */
const VERSION = "snafi-v3";
const STATIC_CACHE = `${VERSION}-static`;
const PRECACHE = ["/offline.html", "/manifest.webmanifest", "/icons/icon.svg", "/icons/icon-192.png", "/icons/icon-512.png"];

// Each file is cached on its own: one that fails to load is skipped, never the whole install. (Live bug,
// Nov 15, 2026: /offline.html was missing on Vercel, cache.addAll failed, the worker never installed,
// and push could not start on any phone.)
self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(STATIC_CACHE)
      .then((cache) => Promise.all(PRECACHE.map((url) => cache.add(url).catch(() => undefined))))
      .then(() => self.skipWaiting()),
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => !k.startsWith(VERSION)).map((k) => caches.delete(k))))
      .then(() => self.clients.claim()),
  );
});

function isStaticAsset(url) {
  return url.pathname.startsWith("/_next/static/") || url.pathname.startsWith("/icons/");
}

self.addEventListener("fetch", (event) => {
  const request = event.request;
  if (request.method !== "GET") return;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;

  if (isStaticAsset(url)) {
    // Built files are content-hashed, so cache-first is safe.
    event.respondWith(
      caches.match(request).then((hit) => hit || fetch(request).then((res) => {
        if (res.ok) {
          const copy = res.clone();
          caches.open(STATIC_CACHE).then((cache) => cache.put(request, copy));
        }
        return res;
      })),
    );
    return;
  }

  if (request.mode === "navigate") {
    // Network only; show the offline page if the network is down.
    event.respondWith(fetch(request).catch(() => caches.match("/offline.html")));
  }
});

// ---------- step 5: Web Push ----------
const PUSH_TEXT = {
  en: {
    reminder: ["Snafi", "You have a reminder"],
    brief: ["Snafi", "Your morning brief is ready"],
    mail: ["Snafi", "Ahmad has an update for you"],
    test: ["Snafi", "Test notification: push works"],
  },
  ar: {
    reminder: ["سنافي", "لديك تذكير"],
    brief: ["سنافي", "ملخص صباحك جاهز"],
    mail: ["سنافي", "لدى أحمد جديد لك"],
    test: ["سنافي", "إشعار تجريبي: الإشعارات تعمل"],
  },
};

/** Fixed, private-free text for a push. Anything unknown gets the generic "update" text. */
function pushText(data) {
  const lang = data && data.l === "ar" ? "ar" : "en";
  const kind = data && Object.prototype.hasOwnProperty.call(PUSH_TEXT[lang], data.k) ? data.k : "mail";
  const [title, body] = PUSH_TEXT[lang][kind];
  const tag = data && typeof data.n === "string" && /^[0-9a-f-]{36}$/.test(data.n) ? data.n : "snafi";
  return { title, body, tag, lang, dir: lang === "ar" ? "rtl" : "ltr" };
}

self.addEventListener("push", (event) => {
  let data = null;
  try {
    data = event.data ? event.data.json() : null;
  } catch {
    data = null;
  }
  const n = pushText(data);
  event.waitUntil(self.registration.showNotification(n.title, {
    body: n.body, tag: n.tag, lang: n.lang, dir: n.dir,
    icon: "/icons/icon-192.png", badge: "/icons/icon-192.png", data: { url: "/today" },
  }));
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  event.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((windows) => {
      for (const w of windows) {
        if (new URL(w.url).origin === self.location.origin && "focus" in w) {
          if ("navigate" in w) w.navigate("/today");
          return w.focus();
        }
      }
      return self.clients.openWindow("/today");
    }),
  );
});
