self.addEventListener("install", () => {
  self.skipWaiting()
})

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.delete("lorevia-offline-v1").then(() => self.clients.claim())
  )
})
