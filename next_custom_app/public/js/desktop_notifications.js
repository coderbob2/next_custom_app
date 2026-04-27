(function () {
    const EVENT_NAME = 'custom_workflow_desktop_notification';
    const ICON_PATH = '/assets/next_custom_app/images/notification-icon.png';
    const DEFAULT_TITLE = __('ERPNext Notification');
    const BADGE_PATH = '/assets/frappe/images/frappe-framework-logo.svg';
    let audioUnlocked = false;

    function unlockAudio() {
        audioUnlocked = true;
        window.removeEventListener('pointerdown', unlockAudio);
        window.removeEventListener('keydown', unlockAudio);
    }

    function setupAudioUnlock() {
        window.addEventListener('pointerdown', unlockAudio, { once: true });
        window.addEventListener('keydown', unlockAudio, { once: true });
    }

    function playNotificationSound() {
        try {
            const AudioCtx = window.AudioContext || window.webkitAudioContext;
            if (!AudioCtx) return;

            const ctx = new AudioCtx();
            if (!audioUnlocked && ctx.state === 'suspended') {
                return;
            }

            if (ctx.state === 'suspended') {
                ctx.resume().catch(() => null);
            }

            const now = ctx.currentTime;
            const master = ctx.createGain();
            master.gain.value = 0.26;
            master.connect(ctx.destination);

            // Distinct, more audible tri-tone notification pattern (inspired by chat app pings)
            const sequence = [
                { at: 0.00, duration: 0.12, f1: 880, f2: 1320, t1: 'triangle', t2: 'sine', peak: 0.95 },
                { at: 0.16, duration: 0.12, f1: 1174, f2: 1568, t1: 'triangle', t2: 'sine', peak: 0.95 },
                { at: 0.33, duration: 0.18, f1: 1568, f2: 2093, t1: 'triangle', t2: 'square', peak: 1.0 }
            ];

            sequence.forEach((note) => {
                const gain = ctx.createGain();
                gain.gain.setValueAtTime(0.0001, now + note.at);
                gain.gain.exponentialRampToValueAtTime(note.peak, now + note.at + 0.01);
                gain.gain.exponentialRampToValueAtTime(0.25, now + note.at + note.duration * 0.55);
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

            setTimeout(() => {
                try {
                    ctx.close();
                } catch (e) {
                    // no-op
                }
            }, 1200);
        } catch (e) {
            // no-op
        }
    }

    async function triggerLocalNotification(data) {
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

    async function getServiceWorkerRegistration() {
        if (!("serviceWorker" in navigator)) return null;

        try {
            return await navigator.serviceWorker.getRegistration('/assets/next_custom_app/js/service-worker.js')
                || await navigator.serviceWorker.ready;
        } catch (e) {
            return null;
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

        const swReg = await getServiceWorkerRegistration();
        if (swReg && typeof swReg.showNotification === 'function') {
            await swReg.showNotification(title, options);
            return;
        }

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

    frappe.ready(function () {
        requestNotificationPermission();
        setupAudioUnlock();
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
