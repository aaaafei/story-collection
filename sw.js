/* 故事收藏屋 · 轻量 PWA Service Worker
 * 仅满足可安装条件：网络透传，不缓存页面/图片/JSON，避免阻碍故事更新。
 */
self.addEventListener("install", function (event) {
  self.skipWaiting();
});

self.addEventListener("activate", function (event) {
  event.waitUntil(self.clients.claim());
});

self.addEventListener("fetch", function (event) {
  event.respondWith(fetch(event.request));
});
