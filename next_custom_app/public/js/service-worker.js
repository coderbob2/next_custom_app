/* eslint-disable no-restricted-globals */

self.addEventListener("push", function (event) {
    let payload = {
        title: "ERPNext Notification",
        body: "You have a new update.",
        url: "/app",
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
            icon: "/assets/frappe/images/frappe-framework-logo.svg",
            badge: "/assets/frappe/images/frappe-framework-logo.svg",
            tag: payload.tag || "erpnext-push",
            data: {
                url: payload.url || "/app",
            },
            renotify: true,
            requireInteraction: false,
        })
    );
});

self.addEventListener("notificationclick", function (event) {
    event.notification.close();
    const targetUrl = (event.notification && event.notification.data && event.notification.data.url) || "/app";

    event.waitUntil(
        clients.matchAll({ type: "window", includeUncontrolled: true }).then(function (windowClients) {
            for (const client of windowClients) {
                if (client.url && client.url.includes(targetUrl) && "focus" in client) {
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

