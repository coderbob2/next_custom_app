// Web Push subscription bootstrap for Frappe Desk
(function () {
    "use strict";

    if (window.__next_custom_app_push_init_done) return;
    window.__next_custom_app_push_init_done = true;

    function urlBase64ToUint8Array(base64String) {
        const padding = "=".repeat((4 - (base64String.length % 4)) % 4);
        const base64 = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/");
        const rawData = window.atob(base64);
        const outputArray = new Uint8Array(rawData.length);
        for (let i = 0; i < rawData.length; ++i) {
            outputArray[i] = rawData.charCodeAt(i);
        }
        return outputArray;
    }

    async function registerPush() {
        if (!window.frappe || !frappe.session || !frappe.session.user || frappe.session.user === "Guest") {
            return;
        }

        if (!("serviceWorker" in navigator) || !("PushManager" in window) || !("Notification" in window)) {
            console.warn("[Push] Browser does not support ServiceWorker/Push/Notification APIs");
            return;
        }

        if (!window.isSecureContext) {
            console.warn("[Push] Secure context is required (HTTPS/localhost)");
            return;
        }

        const registration = await navigator.serviceWorker.register(
            "/assets/next_custom_app/js/service-worker.js"
        );

        let permission = Notification.permission;
        if (permission === "default") {
            permission = await Notification.requestPermission();
        }

        if (permission !== "granted") {
            console.warn("[Push] Notification permission is not granted:", permission);
            return;
        }

        const keyResponse = await frappe.call({
            method: "next_custom_app.next_custom_app.push_notifications.service.get_push_public_key",
        });

        const vapidPublicKey = keyResponse && keyResponse.message;
        if (!vapidPublicKey) {
            console.warn("[Push] Missing VAPID public key from backend");
            return;
        }

        let subscription = await registration.pushManager.getSubscription();
        if (!subscription) {
            subscription = await registration.pushManager.subscribe({
                userVisibleOnly: true,
                applicationServerKey: urlBase64ToUint8Array(vapidPublicKey),
            });
        }

        await frappe.call({
            method: "next_custom_app.next_custom_app.push_notifications.service.save_push_subscription",
            args: {
                subscription: subscription.toJSON(),
                browser: navigator.userAgent || "",
            },
        });

        console.log("[Push] Subscription saved");
    }

    frappe.ready(function () {
        setTimeout(function () {
            registerPush().catch(function (err) {
                console.error("[Push] Registration failed", err);
            });
        }, 1500);
    });
})();
