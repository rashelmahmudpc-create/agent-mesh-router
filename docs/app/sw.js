/* 🛠️ সার্ভিস ওয়ার্কার — অ্যাপ খোলা/অফলাইন থাকলেও কাজ করে
 *
 * নিয়ম:
 *  - অ্যাপের নিজের ফাইল (HTML/CSS/JS/আইকন) → cache-first
 *  - সার্ভার API (/api/...) → কখনো ক্যাশ নয়, সবসময় নেটওয়ার্ক
 */

const VERSION = "mesh-chat-v1";
const SHELL = [
  "./",
  "./index.html",
  "./app.css",
  "./app.js",
  "./js/md.js",
  "./js/api.js",
  "./js/store.js",
  "./manifest.webmanifest",
  "./icons/icon.svg",
  "./icons/icon-180.png",
  "./icons/icon-192.png",
  "./icons/icon-512.png",
  "./icons/icon-maskable-512.png",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(VERSION).then((cache) => cache.addAll(SHELL)).then(() => self.skipWaiting()),
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((key) => key !== VERSION).map((key) => caches.delete(key))))
      .then(() => self.clients.claim()),
  );
});

self.addEventListener("fetch", (event) => {
  const request = event.request;
  if (request.method !== "GET") return;

  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return; // সার্ভার (Worker) কে ছুঁই না
  if (url.pathname.includes("/api/")) return;     // API কখনো ক্যাশ নয়

  // 🧭 পেজ খোলা → নেটওয়ার্ক আগে, না পেলে ক্যাশ
  if (request.mode === "navigate") {
    event.respondWith(
      fetch(request)
        .then((response) => {
          const copy = response.clone();
          caches.open(VERSION).then((cache) => cache.put("./index.html", copy));
          return response;
        })
        .catch(() => caches.match("./index.html").then((hit) => hit || caches.match("./"))),
    );
    return;
  }

  // 🧱 বাকি ফাইল → ক্যাশ আগে, না পেলে নেটওয়ার্ক
  event.respondWith(
    caches.match(request).then((hit) => {
      if (hit) return hit;
      return fetch(request)
        .then((response) => {
          if (response && response.ok) {
            const copy = response.clone();
            caches.open(VERSION).then((cache) => cache.put(request, copy));
          }
          return response;
        })
        .catch(() => hit);
    }),
  );
});
