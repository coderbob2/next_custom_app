/* eslint-disable no-restricted-globals */

const DEFAULT_ICON = "/assets/next_custom_app/images/notification-icon.png";
const DEFAULT_BADGE = "/assets/frappe/images/frappe-framework-logo.svg";

self.addEventListener("push", function (event) {
    let payload = {
        title: "ERPNext Notification",
        body: "You have a new update.",
        url: "/app",
        icon: DEFAULT_ICON,
    };

    try {
        if (event.data) {
            payload = Object.assign(payload, event.data.json());
        }
    } catch (e) {
        // Keep defaults on malformed payload
    }

    event.waitUntil(
        self.registration.showNotification(payload.title, {
            body: payload.body,
            icon: payload.icon || DEFAULT_ICON,
            badge: payload.badge || DEFAULT_BADGE,
            tag: payload.tag || "erpnext-push",
            data: {
                url: payload.url || "/app",
                route: payload.route || null,
            },
            renotify: true,
            requireInteraction: true,
        })
    );
});

self.addEventListener("notificationclick", function (event) {
    event.notification.close();
    const targetUrl = (event.notification && event.notification.data && event.notification.data.url) || "/app";

    event.waitUntil(
        clients.matchAll({ type: "window", includeUncontrolled: true }).then(function (windowClients) {
            // IMPORTANT: this SW is asset-scoped and may not control /app pages.
            // Avoid client.navigate() which can throw:
            // "This service worker is not the client's active service worker."
            for (const client of windowClients) {
                if (client.url && client.url.includes("/app") && "focus" in client) {
                    return client.focus();
                }
            }

            if (clients.openWindow) {
                return clients.openWindow(targetUrl);
            }
            return null;
        })
    );
});
