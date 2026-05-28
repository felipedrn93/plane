// Service Worker dedicado para Web Push (notificações no navegador).
// Registrado em runtime pelo hook use-browser-push.

self.addEventListener("install", (event) => {
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(self.clients.claim());
});

self.addEventListener("push", (event) => {
  let payload = {};
  if (event.data) {
    try {
      payload = event.data.json();
    } catch (e) {
      payload = { title: "Plane", body: event.data.text() };
    }
  }

  const title = payload.title || "Plane";
  const options = {
    body: payload.body || "",
    tag: payload.tag,
    data: { url: payload.url || "/" },
    icon: "/favicon/android-chrome-192x192.png",
  };

  event.waitUntil(self.registration.showNotification(title, options));
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const target = (event.notification.data && event.notification.data.url) || "/";

  event.waitUntil(
    (async () => {
      const allClients = await self.clients.matchAll({ type: "window", includeUncontrolled: true });
      for (const client of allClients) {
        const url = new URL(client.url);
        if (client.focus) {
          await client.focus();
          if ("navigate" in client) {
            try {
              await client.navigate(target);
            } catch (e) {
              // ignore cross-origin navigate errors
            }
          }
          return;
        }
      }
      if (self.clients.openWindow) {
        await self.clients.openWindow(target);
      }
    })()
  );
});
