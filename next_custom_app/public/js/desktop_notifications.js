(function () {
    const EVENT_NAME = 'custom_workflow_desktop_notification';
    const ICON_PATH = '/assets/erpnext/images/erpnext-logo.svg';
    const DEFAULT_TITLE = __('ERPNext Notification');
    const BADGE_PATH = '/assets/frappe/images/frappe-framework-logo.svg';
    let audioUnlocked = false;
    let sharedAudioCtx = null;
    const recentNotificationKeys = new Map();

    function cleanupRecentNotificationKeys() {
        const cutoff = Date.now() - 5000;
        for (const [key, ts] of recentNotificationKeys.entries()) {
            if (ts < cutoff) {
                recentNotificationKeys.delete(key);
            }
        }
    }

    function shouldProcessNotification(data) {
        cleanupRecentNotificationKeys();
        const key = [
            data && data.doctype,
            data && data.docname,
            data && data.workflow_state,
            data && data.title,
            data && data.body,
        ].join('::');

        if (recentNotificationKeys.has(key)) {
            return false;
        }

        recentNotificationKeys.set(key, Date.now());
        return true;
    }

    function getAudioContext() {
        const AudioCtx = window.AudioContext || window.webkitAudioContext;
        if (!AudioCtx) return null;
        if (!sharedAudioCtx) {
            sharedAudioCtx = new AudioCtx();
        }
        return sharedAudioCtx;
    }

    function unlockAudio() {
        const ctx = getAudioContext();
        if (!ctx) return;

        ctx.resume().then(() => {
            audioUnlocked = true;
        }).catch(() => null);

        window.removeEventListener('pointerdown', unlockAudio);
        window.removeEventListener('keydown', unlockAudio);
        window.removeEventListener('touchstart', unlockAudio);
    }

    function setupAudioUnlock() {
        window.addEventListener('pointerdown', unlockAudio, { once: true });
        window.addEventListener('keydown', unlockAudio, { once: true });
        window.addEventListener('touchstart', unlockAudio, { once: true });
    }

    function playNotificationSound() {
        try {
            const ctx = getAudioContext();
            if (!ctx) return;

            if (ctx.state === 'suspended') {
                ctx.resume().catch(() => null);
            }

            // If browser policy still blocks audio, exit quietly.
            if (ctx.state === 'suspended' && !audioUnlocked) {
                return;
            }

            const now = ctx.currentTime;
            const master = ctx.createGain();
            master.gain.value = 0.34;
            master.connect(ctx.destination);

            // Distinct chat-style double-ping + bright tail (more audible)
            const sequence = [
                { at: 0.00, duration: 0.11, f1: 1046, f2: 1568, t1: 'triangle', t2: 'sine', peak: 1.0 },
                { at: 0.14, duration: 0.11, f1: 1174, f2: 1760, t1: 'triangle', t2: 'sine', peak: 1.0 },
                { at: 0.30, duration: 0.22, f1: 1568, f2: 2637, t1: 'triangle', t2: 'square', peak: 0.9 }
            ];

            sequence.forEach((note) => {
                const gain = ctx.createGain();
                gain.gain.setValueAtTime(0.0001, now + note.at);
                gain.gain.exponentialRampToValueAtTime(note.peak, now + note.at + 0.008);
                gain.gain.exponentialRampToValueAtTime(0.34, now + note.at + note.duration * 0.5);
                gain.gain.exponentialRampToValueAtTime(0.0001, now + note.at + note.duration);
                gain.connect(master);

                const oscA = ctx.createOscillator();
                oscA.type = note.t1;
                oscA.frequency.setValueAtTime(note.f1, now + note.at);
                oscA.connect(gain);

                const oscB = ctx.createOscillator();
                oscB.type = note.t2;
                oscB.frequency.setValueAtTime(note.f2, now + note.at);
                oscB.connect(gain);

                oscA.start(now + note.at);
                oscB.start(now + note.at);
                oscA.stop(now + note.at + note.duration);
                oscB.stop(now + note.at + note.duration);
            });
        } catch (e) {
            // no-op
        }
    }

    function setupServiceWorkerMessageRouting() {
        if (!('serviceWorker' in navigator)) return;

        navigator.serviceWorker.addEventListener('message', function (event) {
            const data = event && event.data;
            if (!data) return;

            if (data.type === 'next_custom_app_realtime_push') {
                triggerLocalNotification(data.payload || {});
                return;
            }

            if (data.type !== 'next_custom_app_open_url') return;

            if (data.route && window.frappe && typeof frappe.set_route === 'function') {
                frappe.set_route(data.route);
                return;
            }

            if (data.url) {
                window.location.href = data.url;
            }
        });
    }

    async function triggerLocalNotification(data) {
        if (!shouldProcessNotification(data || {})) {
            return;
        }

        playNotificationSound();
        await showDesktopNotification(data || {
            title: DEFAULT_TITLE,
            body: __('You have a new workflow notification.'),
            doctype: 'Material Request',
            docname: '',
            workflow_state: 'Pending',
            route: null
        });

        if (frappe.show_alert) {
            frappe.show_alert({
                message: (data && data.body) || __('You have a new workflow notification.'),
                indicator: 'blue'
            });
        }
    }

    function browserNotificationsSupported() {
        return 'Notification' in window;
    }

    function requestNotificationPermission() {
        if (!browserNotificationsSupported()) {
            return;
        }

        if (Notification.permission === 'default') {
            Notification.requestPermission().catch(() => null);
        }
    }

    async function showDesktopNotification(data) {
        if (!browserNotificationsSupported()) return;
        if (Notification.permission !== 'granted') return;
        if (!data) return;

        const title = data.title || __('ERPNext Notification');
        const options = {
            body: data.body || '',
            icon: ICON_PATH,
            badge: BADGE_PATH,
            tag: `${data.doctype || ''}-${data.docname || ''}-${data.workflow_state || ''}`,
            renotify: true,
            requireInteraction: true,
            data: {
                route: data.route || null,
                url: data.docname && data.doctype ? `/app/${frappe.router.slug(data.doctype)}/${data.docname}` : '/app'
            }
        };

        const notification = new Notification(title, options);

        notification.onclick = function () {
            window.focus();

            if (data.route && window.frappe && frappe.set_route) {
                frappe.set_route(data.route);
            }

            notification.close();
        };
    }

    function addPermissionUI() {
        if (!window.frappe || !frappe.ui || !frappe.ui.toolbar || !frappe.ui.toolbar.add_dropdown_button) {
            return;
        }

        if (window.__next_custom_app_desktop_notify_button_added) {
            return;
        }
        window.__next_custom_app_desktop_notify_button_added = true;

        try {
            frappe.ui.toolbar.add_dropdown_button(__('Tools'), {
                label: __('Enable Desktop Notifications'),
                click: function () {
                    if (!browserNotificationsSupported()) {
                        frappe.show_alert({ message: __('Browser does not support desktop notifications.'), indicator: 'orange' });
                        return;
                    }

                    Notification.requestPermission().then((permission) => {
                        if (permission === 'granted') {
                            frappe.show_alert({ message: __('Desktop notifications enabled.'), indicator: 'green' });
                        } else {
                            frappe.show_alert({ message: __('Desktop notifications not enabled.'), indicator: 'orange' });
                        }
                    });
                }
            });
        } catch (e) {
            // no-op for older toolbar APIs
        }
    }

    function onReady(callback) {
        if (window.frappe && typeof frappe.ready === 'function') {
            frappe.ready(callback);
            return;
        }

        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', callback, { once: true });
            return;
        }

        callback();
    }

    onReady(function () {
        requestNotificationPermission();
        setupAudioUnlock();
        setupServiceWorkerMessageRouting();
        addPermissionUI();

        if (frappe.realtime) {
            frappe.realtime.on(EVENT_NAME, async function (data) {
                triggerLocalNotification(data);
            });
        }

        window.next_custom_app = window.next_custom_app || {};
        window.next_custom_app.workflow_notifications = window.next_custom_app.workflow_notifications || {};
        window.next_custom_app.workflow_notifications.test = function (data) {
            triggerLocalNotification(data);
        };
    });
})();
