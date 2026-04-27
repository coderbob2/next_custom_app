// Copyright (c) 2025, Nextcore Technologies and contributors
// Custom Tab Enhancement for All Procurement Workflow Doctypes

/**
 * IMPORTANT (Desk SPA / production):
 * This file is included via `doctype_js` for multiple doctypes.
 * In Frappe Desk (single-page app), each doctype JS bundle can be loaded
 * without a full page reload. If we register `frappe.ui.form.on(...)` handlers
 * every time this file is evaluated, handlers will accumulate and cause
 * duplicate server calls (get_active_flow / get_next_step / get_linked_documents...).
 *
 * To make this script idempotent, we guard against double-registration.
 */

window.next_custom_app = window.next_custom_app || {};

// Keep per-doctype registration state to avoid duplicate handlers in Desk SPA.
// (Do NOT use a single global boolean, because we still need to register
// handlers when the user opens a different doctype.)
window.next_custom_app.__procurement_custom_tabs_registered_doctypes =
    window.next_custom_app.__procurement_custom_tabs_registered_doctypes || {};

// Global caches to avoid repeated API calls across rapid refreshes / SPA navigation
// Cache version: bump this when the cache structure changes to force invalidation
const _CACHE_VERSION = 2; // v2: added role field to next_steps
if (!window.next_custom_app.__procurement_tabs_cache
    || window.next_custom_app.__procurement_tabs_cache._version !== _CACHE_VERSION) {
    window.next_custom_app.__procurement_tabs_cache = {
        _version: _CACHE_VERSION,
        next_step_by_doctype: {},
    };
}

{

    // List of procurement doctypes this applies to
    const PROCUREMENT_DOCTYPES = [
        'Material Request',
        'Purchase Requisition',
        'Request for Quotation',
        'Supplier Quotation',
        'Purchase Order',
        'Purchase Receipt',
        'Purchase Invoice',
        'Payment Request',
        'Payment Entry'
    ];


    /**
     * IMPORTANT:
     * This script is sometimes deployed as multiple "Client Script" records
     * (one per doctype). In Frappe Desk (SPA), client scripts from previously
     * visited doctypes remain loaded, and their handlers remain active.
     *
     * If a client script registers handlers for *all* PROCUREMENT_DOCTYPES,
     * you end up with duplicates (e.g. Material Request script still listening
     * when you open Purchase Requisition).
     *
     * To prevent that, we register handlers ONLY for the current form doctype
     * when we can detect it.
     */
    function get_current_form_doctype() {
        try {
            if (typeof cur_frm !== 'undefined' && cur_frm && cur_frm.doctype) {
                return cur_frm.doctype;
            }
            if (frappe.get_route) {
                const route = frappe.get_route();
                if (route && route[0] === 'Form' && route[1]) {
                    return route[1];
                }
            }
        } catch (e) {
            // ignore
        }
        return null;
    }

    const CURRENT_DOCTYPE = get_current_form_doctype();

    // Prefer registering ONLY for the current doctype to avoid the "Client Script per doctype"
    // duplication problem. If we can't detect it (rare), fall back to all.
    const DOCTYPES_TO_REGISTER = (CURRENT_DOCTYPE && PROCUREMENT_DOCTYPES.includes(CURRENT_DOCTYPE))
        ? [CURRENT_DOCTYPE]
        : PROCUREMENT_DOCTYPES;

    // Cache for active flow check (session-level cache)
    let active_flow_cache = null;
    let active_flow_cache_time = null;
    const CACHE_DURATION = 60000; // 60 seconds

    // Throttle linked docs calls per form instance
    const LINKED_DOCS_THROTTLE_MS = 2000;

    // Debounce helper
    function debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    }

    /**
     * Check if the current user has a specific role.
     * Uses frappe.user_roles which is available client-side.
     */
    function user_has_role(role) {
        if (!role) return true; // No role restriction means all users can see it
        const user_roles = frappe.user_roles || (frappe.boot && frappe.boot.user && frappe.boot.user.roles) || [];
        return user_roles.includes(role) || user_roles.includes('Administrator');
    }

    /**
     * Remove default ERPNext buttons that slipped through the interceptor.
     * This is a DOM-based fallback for buttons added via mechanisms that
     * bypass our add_custom_button interceptor (e.g. set_primary_action,
     * or buttons added by ERPNext refresh handlers that run after ours).
     */
    function _remove_default_erpnext_buttons(frm) {
        // Only remove when procurement flow is active
        if (window.__procurement_flow_active === false) return;

        // Labels to remove (ERPNext default buttons on submitted procurement docs)
        const REMOVE_LABELS = [
            'Create Payment Entry',
            'Payment', 'Payment Request',
            'Purchase Receipt', 'Purchase Invoice',
            'Request for Quotation', 'Supplier Quotation',
            'Purchase Order', 'Stock Entry', 'Pick List',
            'Material Transfer', 'Material Issue',
            'Purchase Return', 'Make Stock Entry',
            'Retention Stock Entry', 'Debit Note',
            'Return', 'Subcontract', 'Update Items',
        ];

        const $wrapper = $(frm.page.wrapper);

        // Remove matching custom buttons (not inside our procurement-next-step-btn group)
        $wrapper.find('.btn-custom, .btn-secondary-dark, .btn-primary-dark, .btn-primary').each(function () {
            const $btn = $(this);
            // Skip our own workflow buttons
            if ($btn.hasClass('procurement-next-step-btn')) return;
            // Skip buttons inside our Create dropdown
            if ($btn.closest('.procurement-next-step-btn').length) return;

            const label = ($btn.text() || '').trim();
            if (REMOVE_LABELS.includes(label)) {
                $btn.remove();
            }
        });

        // Also check for standalone buttons in the page actions area
        $wrapper.find('.page-actions .btn').each(function () {
            const $btn = $(this);
            if ($btn.hasClass('procurement-next-step-btn')) return;
            const label = ($btn.text() || '').trim();
            if (REMOVE_LABELS.includes(label)) {
                $btn.remove();
            }
        });
    }

    /**
     * Enforce strict Purchase Order Create menu options.
     * Keep only: Payment Request, Purchase Receipt.
     *
     * This is a DOM-level hard-stop for cases where ERPNext adds menu items
     * through code paths that bypass frm.add_custom_button interception.
     */
    function _enforce_po_create_menu_options(frm) {
        if (frm.doctype !== 'Purchase Order' || frm.doc.docstatus !== 1) return;

        const ALLOWED = new Set(['Payment Request', 'Purchase Receipt']);
        const $wrapper = $(frm.page.wrapper);

        // Inner-group dropdown items (Create menu)
        $wrapper.find('.inner-group-button').each(function () {
            const $group = $(this);
            const $mainBtn = $group.find('> button').first();
            const groupLabel = ($mainBtn.text() || '').trim();
            if (groupLabel !== 'Create') return;

            $group.find('.dropdown-menu .dropdown-item, .dropdown-menu a').each(function () {
                const $item = $(this);
                const label = ($item.text() || '').trim();
                if (!ALLOWED.has(label)) {
                    const $li = $item.closest('li');
                    if ($li.length) {
                        $li.remove();
                    } else {
                        $item.remove();
                    }
                }
            });
        });

        // Fallback: remove any standalone action items for blocked labels
        $wrapper.find('.page-actions .dropdown-item, .page-actions a, .actions-menu .dropdown-item').each(function () {
            const $item = $(this);
            const label = ($item.text() || '').trim();
            if (['Payment', 'Purchase Invoice', 'Create Payment Entry'].includes(label)) {
                const $li = $item.closest('li');
                if ($li.length) {
                    $li.remove();
                } else {
                    $item.remove();
                }
            }
        });
    }

    /**
     * Add the "Create" button(s) directly in the page header.
     * These are primary action buttons for the next workflow step.
     * Buttons are filtered by the role defined on each flow step —
     * only users with the matching role will see the corresponding button.
     */
    function add_next_step_buttons(frm) {
        if (frm.doc.docstatus !== 1) return;


        function get_next_step_label(next_doctype) {
            if (next_doctype === 'Stock Entry') {
                const purpose = frm.doc && (frm.doc.material_request_type || frm.doc.purchase_requisition_type || frm.doc.purpose)
                    ? String(frm.doc.material_request_type || frm.doc.purchase_requisition_type || frm.doc.purpose)
                    : '';
                if (purpose === 'Material Transfer' || purpose === 'Material Issue') {
                    return purpose;
                }
            }
            return next_doctype;
        }

        // Avoid repeated server calls for the same doctype within a session
        const cache_key = frm.doctype;
        const cached = window.next_custom_app.__procurement_tabs_cache.next_step_by_doctype[cache_key];
        if (cached && cached.expires_at > Date.now()) {
            const next_steps = cached.next_steps || [];
            if (next_steps.length) {
                _add_next_step_buttons_to_form(frm, next_steps, get_next_step_label);
            }
            return;
        }

        // Get the next step in workflow
        frappe.call({
            method: "next_custom_app.next_custom_app.utils.procurement_workflow.get_next_steps",
            args: {
                current_doctype: frm.doctype
            },
            callback: function (r) {

                if (r.message && Array.isArray(r.message) && r.message.length) {
                    const next_steps = r.message; // Full step objects with role info

                    // Cache for 30s
                    window.next_custom_app.__procurement_tabs_cache.next_step_by_doctype[cache_key] = {
                        next_steps,
                        // Keep backward-compatible key for any other code that reads it
                        next_doctypes: next_steps.map(s => s.doctype_name),
                        expires_at: Date.now() + CACHE_DURATION
                    };

                    _add_next_step_buttons_to_form(frm, next_steps, get_next_step_label);
                } else {
                }
            },
            error: function (err) {
                console.error('*** Error getting next step:', err);
            }
        });
    }

    /**
     * Actually add the next step buttons to the form.
     * Accepts an array of step objects (each with doctype_name and role).
     * Filters out steps whose role the current user does not have.
     * Always renders buttons inside a "Create" dropdown group.
     */
    function _add_next_step_buttons_to_form(frm, next_steps, get_next_step_label) {
        if (!next_steps || !next_steps.length) return;

        // Filter steps by role; if nothing matches, fall back to all steps so
        // the Create button is still visible for submitted/ready documents.
        let visible_steps = next_steps.filter(function (step) {
            return user_has_role(step.role);
        });

        if (!visible_steps.length) {
            visible_steps = next_steps;
        }

        // Purchase Order strict rule:
        // only allow Purchase Receipt and Payment Request from Create menu.
        if (frm.doctype === 'Purchase Order') {
            visible_steps = visible_steps.filter(function (step) {
                return ['Purchase Receipt', 'Payment Request'].includes(step.doctype_name);
            });

            // If role-filtered result is empty, still enforce the same PO allow-list
            // against full next_steps to keep behavior deterministic.
            if (!visible_steps.length) {
                visible_steps = next_steps.filter(function (step) {
                    return ['Purchase Receipt', 'Payment Request'].includes(step.doctype_name);
                });
            }
        }

        if (!visible_steps.length) return;

        // Do NOT remove the Create button element by CSS class.
        // Removing by class causes race conditions where the button briefly
        // appears then disappears when multiple refresh/onload handlers fire.

        // Allow our workflow buttons through the button interceptor
        // (set by procurement_button_override.js to block default ERPNext buttons)
        frm._procurement_allow_buttons = true;

        // Always use the "Create" dropdown group, even for a single button
        visible_steps.forEach(function (step) {
            const next_doctype = step.doctype_name;
            const label = get_next_step_label(next_doctype);

            frm.add_custom_button(
                __(label),
                function () {
                    show_custom_create_dialog(frm, next_doctype);
                },
                __('Create')
            );
        });

        // Style the "Create" group button (apply now + deferred to handle async DOM timing)
        style_create_group_button(frm);
        setTimeout(function () {
            style_create_group_button(frm);
        }, 0);

        // Reset the flag so future non-workflow button additions are still blocked
        frm._procurement_allow_buttons = false;

    }

    function style_create_group_button(frm) {
        $(frm.page.wrapper).find('.inner-group-button').each(function () {
            const $group = $(this);
            const $mainBtn = $group.find('> button').first();
            if (($mainBtn.text() || '').trim() === 'Create') {
                $mainBtn.addClass('btn-primary-dark procurement-create-main-btn')
                    .removeClass('btn-default btn-secondary');
            }
        });
    }

    function get_notification_help_steps() {
        const ua = (navigator.userAgent || '').toLowerCase();
        const is_windows = ua.includes('windows');
        const is_mac = ua.includes('mac os');
        const is_chrome = ua.includes('chrome') && !ua.includes('edg');

        if (is_windows && is_chrome) {
            return __('Windows + Chrome checks:<br>1) If site is <b>http://IP:PORT</b> (for example 192.168.x.x), switch to <b>HTTPS</b>; Chrome will not reliably allow desktop notifications on insecure origins.<br>2) In Chrome, click the lock icon in the address bar → Site settings → Notifications → Allow.<br>3) Windows Settings → System → Notifications → turn ON notifications and allow Google Chrome.<br>4) Turn OFF Focus Assist / Do Not Disturb.<br>5) Reload the ERPNext tab and test again.');
        }

        if (is_mac && is_chrome) {
            return __('macOS + Chrome checks:<br>1) macOS System Settings → Notifications → Google Chrome → Allow Notifications ON.<br>2) Disable Focus mode / Do Not Disturb.<br>3) In Chrome site settings, allow notifications for this ERPNext site.<br>4) Reload the ERPNext tab and test again.');
        }

        return __('Check browser site notification permission, OS notification permission for your browser, and disable any Focus/Do Not Disturb mode.');
    }

    function show_notification_diagnostics(frm) {
        const secure_context = window.isSecureContext;
        const permission = (typeof Notification !== 'undefined') ? Notification.permission : 'unsupported';
        const protocol = window.location.protocol;
        const site = window.location.origin;

        let secure_context_note = '';
        if (!secure_context) {
            secure_context_note = __('This origin is not a secure context for notifications. Use HTTPS for this site. <br>Example: <b>https://your-domain</b> or local HTTPS reverse proxy.');
        }

        let denied_note = '';
        if (permission === 'denied') {
            denied_note = __('Browser permission is currently <b>denied</b>. Chrome will not show the permission popup again until you manually change it from the address-bar lock icon → Site settings → Notifications.');
        }

        const html = `
            <div style="line-height:1.6;">
                <div><b>Site:</b> ${frappe.utils.escape_html(site)}</div>
                <div><b>Protocol:</b> ${frappe.utils.escape_html(protocol)}</div>
                <div><b>Secure Context:</b> ${secure_context ? 'Yes' : 'No'}</div>
                <div><b>Browser Permission:</b> ${frappe.utils.escape_html(permission)}</div>
                ${secure_context_note ? `<div style="margin-top:8px;color:#8a6d3b;">${secure_context_note}</div>` : ''}
                ${denied_note ? `<div style="margin-top:8px;color:#8a6d3b;">${denied_note}</div>` : ''}
                <hr>
                <div>${get_notification_help_steps()}</div>
            </div>
        `;

        frappe.msgprint({
            title: __('Desktop Notification Diagnostics'),
            message: html
        });
    }

    async function dispatch_browser_notification(title, body) {
        return new Promise(function (resolve, reject) {
            try {
                const notification = new Notification(title, {
                    body: body,
                    icon: '/assets/frappe/images/frappe-framework-logo.svg',
                    tag: 'material-request-test-notification',
                    renotify: true,
                    requireInteraction: true,
                    silent: false
                });

                let resolved = false;

                notification.onshow = function () {
                    if (resolved) return;
                    resolved = true;
                    resolve('shown');
                };

                notification.onerror = function () {
                    if (resolved) return;
                    resolved = true;
                    reject(new Error('notification-error'));
                };

                // Some environments never fire onshow; treat as dispatched.
                setTimeout(function () {
                    if (resolved) return;
                    resolved = true;
                    resolve('dispatched');
                }, 1600);
            } catch (e) {
                reject(e);
            }
        });
    }

    async function show_desktop_notification(title, body, frm) {
        if (!('Notification' in window)) {
            frappe.show_alert({
                message: __('Desktop notifications are not supported in this browser.'),
                indicator: 'orange'
            });
            return;
        }

        if (!window.isSecureContext) {
            frappe.msgprint({
                title: __('Secure Context Required'),
                message: __('Desktop notifications require HTTPS or localhost. Current site is not a secure context.'),
                indicator: 'red'
            });
            show_notification_diagnostics(frm);
            return;
        }

        if (Notification.permission === 'granted') {
            try {
                const result = await dispatch_browser_notification(title, body);
                if (result === 'shown') {
                    frappe.show_alert({
                        message: __('Desktop notification displayed.'),
                        indicator: 'green'
                    });
                } else {
                    frappe.msgprint({
                        title: __('Notification Sent (Not Confirmed Visible)'),
                        message: __('The browser accepted the notification, but OS-level notification settings may still suppress popup display.<br><br>{0}', [get_notification_help_steps()]),
                        indicator: 'orange'
                    });
                }
            } catch (e) {
                frappe.msgprint({
                    title: __('Notification Error'),
                    message: __('Could not show desktop notification: {0}', [e.message || e]),
                    indicator: 'red'
                });
                show_notification_diagnostics(frm);
            }
            return;
        }

        if (Notification.permission === 'default') {
            const permission = await Notification.requestPermission();
            if (permission === 'granted') {
                await show_desktop_notification(title, body, frm);
            } else {
                frappe.msgprint({
                    title: __('Notification Permission Not Granted'),
                    message: __('Permission was not granted by browser. {0}', [get_notification_help_steps()]),
                    indicator: 'orange'
                });
                show_notification_diagnostics(frm);
            }
            return;
        }

        frappe.msgprint({
            title: __('Notifications Blocked'),
            message: __('Desktop notifications are blocked for this site. Enable them in browser settings.<br><br>{0}', [get_notification_help_steps()]),
            indicator: 'orange'
        });
        show_notification_diagnostics(frm);
    }

    function add_material_request_notification_test_button(frm) {
        if (frm.doctype !== 'Material Request') return;

        function fallback_test_notification() {
            try {
                const AudioCtx = window.AudioContext || window.webkitAudioContext;
                if (AudioCtx) {
                    const ctx = new AudioCtx();
                    const master = ctx.createGain();
                    master.gain.value = 0.28;
                    master.connect(ctx.destination);

                    const now = ctx.currentTime;
                    const notes = [
                        { at: 0.00, d: 0.12, f: 880 },
                        { at: 0.15, d: 0.12, f: 1174 },
                        { at: 0.32, d: 0.18, f: 1568 }
                    ];

                    notes.forEach((n) => {
                        const osc = ctx.createOscillator();
                        const gain = ctx.createGain();
                        osc.type = 'triangle';
                        osc.frequency.value = n.f;
                        gain.gain.setValueAtTime(0.0001, now + n.at);
                        gain.gain.exponentialRampToValueAtTime(0.9, now + n.at + 0.01);
                        gain.gain.exponentialRampToValueAtTime(0.0001, now + n.at + n.d);
                        osc.connect(gain);
                        gain.connect(master);
                        osc.start(now + n.at);
                        osc.stop(now + n.at + n.d);
                    });

                    setTimeout(() => {
                        try { ctx.close(); } catch (e) { /* no-op */ }
                    }, 1000);
                }
            } catch (e) {
                // no-op
            }

            if ('Notification' in window && Notification.permission === 'granted') {
                const notification = new Notification(__('Material Request Notification'), {
                    body: __('Test alert for Material Request: {0}', [frm.doc.name || frm.docname || 'New']),
                    icon: '/assets/next_custom_app/images/notification-icon.png',
                    tag: `mr-test-${frm.doc.name || frm.docname || 'new'}`
                });

                notification.onclick = function () {
                    window.focus();
                    if (frm.doc.name) {
                        frappe.set_route(['Form', frm.doctype, frm.doc.name]);
                    }
                    notification.close();
                };
            } else if ('Notification' in window && Notification.permission === 'default') {
                Notification.requestPermission().then((permission) => {
                    if (permission === 'granted') {
                        new Notification(__('Material Request Notification'), {
                            body: __('Test alert for Material Request: {0}', [frm.doc.name || frm.docname || 'New']),
                            icon: '/assets/next_custom_app/images/notification-icon.png'
                        });
                    }
                });
            }

            frappe.show_alert({
                message: __('Desktop notification test triggered.'),
                indicator: 'blue'
            });
        }

        frm._procurement_allow_buttons = true;
        frm.add_custom_button(__('Test Desktop Notification + Sound'), function () {
            frappe.show_alert({
                message: __('Test notification will trigger in 5 seconds...'),
                indicator: 'orange'
            });

            const payload = {
                title: __('Material Request Notification'),
                body: __('Test alert for Material Request: {0}', [frm.doc.name || frm.docname || 'New']),
                doctype: frm.doctype,
                docname: frm.doc.name || frm.docname,
                workflow_state: frm.doc.workflow_state || 'Pending',
                route: frm.doc.name ? ['Form', frm.doctype, frm.doc.name] : null
            };

            // Always queue backend push so closed-tab delivery is possible.
            // Service worker suppresses duplicate card while Desk is open.
            frappe.call({
                method: 'next_custom_app.next_custom_app.push_notifications.service.send_test_push_notification',
                args: {
                    delay_seconds: 5,
                    doctype: frm.doctype,
                    docname: frm.doc.name || frm.docname
                }
            }).then(() => {
                if (frappe.show_alert) {
                    frappe.show_alert({
                        message: __('Background push test queued. Close this tab now and wait 5 seconds.'),
                        indicator: 'green'
                    });
                }
            }).catch(() => {
                if (frappe.show_alert) {
                    frappe.show_alert({
                        message: __('Could not queue backend push test.'),
                        indicator: 'orange'
                    });
                }
            });

            // In-tab sound test only if the tab is still active at trigger time.
            // If tab is closed/background, rely on backend push card.
            setTimeout(function () {
                const isActiveNow = (document.visibilityState === 'visible') && document.hasFocus();
                if (!isActiveNow) return;

                if (
                    window.next_custom_app &&
                    window.next_custom_app.workflow_notifications &&
                    typeof window.next_custom_app.workflow_notifications.test === 'function'
                ) {
                    window.next_custom_app.workflow_notifications.test(payload);
                } else {
                    fallback_test_notification();
                }
            }, 5000);
        }, __('Actions'));
        frm._procurement_allow_buttons = false;
    }

    // Register event handlers for relevant procurement doctypes (idempotent per doctype)
    DOCTYPES_TO_REGISTER.forEach(function (doctype) {
        if (window.next_custom_app.__procurement_custom_tabs_registered_doctypes[doctype]) {
            return;
        }
        window.next_custom_app.__procurement_custom_tabs_registered_doctypes[doctype] = true;

        frappe.ui.form.on(doctype, {
            refresh: function (frm) {

                add_material_request_notification_test_button(frm);

                // Skip custom section entirely for new unsaved documents
                if (!frm.doc.__islocal) {
                    // Add a custom section with button (debounced)
                    add_custom_section_debounced(frm);
                }

                // If document is submitted, add next step button(s)
                // NOTE: Default ERPNext "Create" buttons are suppressed by
                // procurement_button_override.js (loaded globally via app_include_js)
                // which overrides make_custom_buttons — no DOM hacks needed.
                if (frm.doc.docstatus === 1) {
                    // Always re-add buttons on refresh because Frappe's
                    // page.clear_custom_actions() removes them each cycle.
                    add_next_step_buttons(frm);

                    // Hard enforce final Create menu options for submitted PO
                    _remove_default_erpnext_buttons(frm);
                    _enforce_po_create_menu_options(frm);

                    // Some controllers clear/replace actions after refresh handlers run.
                    // Re-apply once more to ensure Create remains visible without manual reload.
                    setTimeout(function () {
                        add_next_step_buttons(frm);
                        _remove_default_erpnext_buttons(frm);
                        _enforce_po_create_menu_options(frm);
                    }, 300);

                    // One extra delayed pass for late async ERPNext menu injection.
                    setTimeout(function () {
                        _remove_default_erpnext_buttons(frm);
                        _enforce_po_create_menu_options(frm);
                    }, 900);
                }
            },

            onload: function (frm) {

                // Get form root for cleanup
                const $form_root = (frm.layout && frm.layout.wrapper) ? $(frm.layout.wrapper) : $(frm.wrapper);

                // Remove ALL existing custom sections from the DOM (cleanup from previous documents)
                const $existing_sections = $form_root.find('.custom-tab-section');
                if ($existing_sections.length > 0) {
                    $existing_sections.remove();
                }

                // Clear any leftover references from previous form
                frm.custom_section_wrapper = null;
                frm.linked_docs_container = null;
                frm._adding_custom_section = false;
                frm._linked_docs_request_inflight = false;
                frm._linked_docs_last_requested_at = null;
            },

            after_save: function (frm) {
                // After first save, the document is no longer __islocal.
                // If the section doesn't exist yet, create it now.
                if (!frm.custom_section_wrapper || frm.custom_section_wrapper.length === 0) {
                    add_custom_section(frm);
                    return;
                }
                // Otherwise, just refresh the data
                if (frm.linked_docs_container && frm.linked_docs_container.length > 0) {
                    // Reset throttle so the refresh happens immediately
                    frm._linked_docs_last_requested_at = null;
                    frm._linked_docs_request_inflight = false;
                    load_linked_documents(frm, frm.linked_docs_container);
                }
            },

            onload_post_render: function (frm) {
                // Cleanup any duplicate sections that might have been created
                const $form_root = (frm.layout && frm.layout.wrapper) ? $(frm.layout.wrapper) : $(frm.wrapper);
                const sections = $form_root.find('.custom-tab-section');
                if (sections.length > 1) {
                    sections.slice(1).remove();
                    // Update frm reference to point to the remaining section
                    frm.custom_section_wrapper = sections.first();
                    frm.linked_docs_container = sections.first().find('.linked-docs-container');
                }

                // Ensure Create button is visible as soon as document is submitted/ready
                // even if this script loaded late in Desk SPA lifecycle.
                if (frm.doc.docstatus === 1) {
                    setTimeout(function () {
                        add_next_step_buttons(frm);
                        _remove_default_erpnext_buttons(frm);
                        _enforce_po_create_menu_options(frm);
                    }, 50);
                }
            }
        });
    });

    // Create debounced version of add_custom_section
    const add_custom_section_debounced = debounce(add_custom_section, 300);

    // If this script is loaded after a form is already open (Desk SPA timing),
    // apply immediately so users don't need a manual page refresh to see buttons.
    if (typeof cur_frm !== 'undefined' && cur_frm && PROCUREMENT_DOCTYPES.includes(cur_frm.doctype)) {
        setTimeout(function () {
            try {
                if (!cur_frm.doc.__islocal) {
                    add_custom_section_debounced(cur_frm);
                }

                if (cur_frm.doc.docstatus === 1) {
                    add_next_step_buttons(cur_frm);
                }
            } catch (e) {
                console.warn('Failed immediate procurement UI apply:', e);
            }
        }, 0);
    }

    function show_custom_create_dialog(frm, next_doctype) {

        // For Payment Request, verify the current user is a valid purchaser
        // BEFORE showing the creation dialog. If not, show an error and stop.
        if (next_doctype === 'Payment Request') {
            frappe.call({
                method: "next_custom_app.next_custom_app.utils.payment_request_utils.get_purchase_user_defaults",
                args: { user: frappe.session.user },
                callback: function (r) {
                    const result = r.message || {};
                    if (!result.ok) {
                        frappe.msgprint({
                            title: __('Cannot Create Payment Request'),
                            message: result.message || __('You are not marked as a Purchaser. Please contact your administrator to enable the "Is Purchaser" flag on your User profile and assign a Suspense Account.'),
                            indicator: 'red',
                        });
                        return; // Do NOT open the dialog or redirect
                    }
                    // User is a valid purchaser – proceed with the dialog
                    _show_create_dialog_inner(frm, next_doctype);
                },
                error: function () {
                    frappe.msgprint({
                        title: __('Cannot Create Payment Request'),
                        message: __('Unable to verify purchaser status. Please try again.'),
                        indicator: 'red',
                    });
                }
            });
            return;
        }

        // For all other doctypes, show the dialog directly
        _show_create_dialog_inner(frm, next_doctype);
    }

    function _show_create_dialog_inner(frm, next_doctype) {
        // Build source document chain
        let source_chain_html = '';

        // Fetch the backward document chain
        frappe.call({
            method: "next_custom_app.next_custom_app.utils.procurement_workflow.get_linked_documents_with_counts",
            args: {
                doctype: frm.doctype,
                docname: frm.docname
            },
            async: false, // Make it synchronous to get the chain before showing dialog
            callback: function (r) {
                if (r.message && r.message.backward && r.message.backward.length > 0) {
                    // Show the chain from earliest to current
                    const chain = r.message.backward.reverse();
                    const chain_items = chain.map(doc => {
                        const docs_list = doc.documents.slice(0, 3).join(', ') + (doc.documents.length > 3 ? '...' : '');
                        return `<div style="display: inline-flex; align-items: center; gap: 8px; padding: 6px 12px; background: #e3f2fd; border-radius: 6px; font-size: 12px; color: #1976d2; font-weight: 500;">
                        <span style="font-size: 10px; opacity: 0.7;">${doc.doctype}</span>
                        <span>${docs_list}</span>
                    </div>`;
                    }).join('<div style="margin: 0 4px; color: #90a4ae;">→</div>');

                    source_chain_html = `
                    <div style="margin-top: 15px; padding: 12px; background: #f8f9fa; border-radius: 8px; border-left: 3px solid #1976d2;">
                        <div style="font-size: 11px; color: #6c757d; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 8px; font-weight: 600;">Source Document Chain</div>
                        <div style="display: flex; flex-wrap: wrap; align-items: center; gap: 4px;">
                            ${chain_items}
                            <div style="margin: 0 4px; color: #90a4ae;">→</div>
                            <div style="display: inline-flex; align-items: center; gap: 8px; padding: 6px 12px; background: #e8f5e9; border-radius: 6px; font-size: 12px; color: #2e7d32; font-weight: 600;">
                                <span style="font-size: 10px; opacity: 0.7;">${frm.doctype}</span>
                                <span>${frm.doc.name}</span>
                            </div>
                        </div>
                    </div>
                `;
                }
            }
        });

        let dialog = new frappe.ui.Dialog({
            title: __('Create {0} from {1}', [next_doctype, frm.doc.name]),
            fields: [
                {
                    fieldtype: 'HTML',
                    fieldname: 'info',
                    options: `
                    <div style="padding: 20px 0;">
                        <div style="display: flex; align-items: center; gap: 15px; padding: 20px; background: linear-gradient(135deg, #e3f2fd 0%, #bbdefb 100%); border-radius: 8px; border-left: 4px solid #2196f3;">
                            <div style="font-size: 48px; line-height: 1;">📋</div>
                            <div style="flex: 1;">
                                <div style="font-size: 16px; font-weight: 600; margin-bottom: 6px; color: #1565c0;">Create ${next_doctype}</div>
                                <div style="font-size: 13px; color: #424242;">This will create a new <strong>${next_doctype}</strong> document based on <strong>${frm.doc.name}</strong></div>
                            </div>
                        </div>
                        ${source_chain_html}
                    </div>
                `
                }
            ],
            primary_action_label: __('Create {0}', [next_doctype]),
            primary_action: function () {

                // Call the standard procurement workflow method
                frappe.call({
                    method: "next_custom_app.next_custom_app.utils.procurement_workflow.make_procurement_document",
                    args: {
                        source_name: frm.docname,
                        target_doctype: next_doctype
                    },
                    callback: function (r) {
                        if (r.message) {
                            frappe.model.sync(r.message);
                            frappe.set_route("Form", r.message.doctype, r.message.name);
                            dialog.hide();
                        }
                    },
                    error: function (err) {
                        console.error('*** Error creating document:', err);
                    }
                });
            }
        });

        dialog.show();
    }

    function add_custom_section(frm) {
        // Skip for new documents
        if (frm.doc.__islocal) {
            return;
        }

        // Work ONLY within this form's DOM to avoid interfering with other open tabs
        const $form_root = (frm.layout && frm.layout.wrapper) ? $(frm.layout.wrapper) : $(frm.wrapper);

        // Cleanup duplicates inside this form only
        const $existing_sections = $form_root.find('.custom-tab-section');
        if ($existing_sections.length > 1) {
            $existing_sections.slice(1).remove();
        }

        // Prevent multiple simultaneous calls
        if (frm._adding_custom_section) {
            return;
        }

        // Reuse existing section when available (avoid repeated API calls on multiple refreshes)
        const existing_section = $form_root.find('.custom-tab-section').first();
        const existing_matches_doc = existing_section.length
            && existing_section.attr('data-doctype') === frm.doctype
            && existing_section.attr('data-docname') === frm.docname;

        if (existing_section.length > 0 && existing_matches_doc) {
            // Section already exists for this document — just refresh data
            // (even if it's still loading, don't recreate it)
            frm.custom_section_wrapper = existing_section.first();
            frm.linked_docs_container = existing_section.first().find('.linked-docs-container');
            if (frm.linked_docs_container.length > 0) {
                load_linked_documents(frm, frm.linked_docs_container);
            }
            return;
        }

        // Set flag to prevent duplicate calls
        frm._adding_custom_section = true;

        // Check cache first
        const now = Date.now();
        if (active_flow_cache !== null && active_flow_cache_time && (now - active_flow_cache_time) < CACHE_DURATION) {
            frm._adding_custom_section = false;

            if (active_flow_cache) {
                create_custom_section_ui(frm);
            }
            return;
        }

        // Check if there's an active procurement workflow before showing the section
        frappe.call({
            method: "next_custom_app.next_custom_app.utils.procurement_workflow.get_active_flow",
            callback: function (r) {
                // Cache the result
                active_flow_cache = r.message || null;
                active_flow_cache_time = Date.now();

                // Clear the flag
                frm._adding_custom_section = false;

                if (!r.message) {
                    return;
                }

                // Proceed with creating the custom section
                create_custom_section_ui(frm);
            },
            error: function (err) {
                console.error('>>> Error checking active flow:', err);
                // Clear the flag
                frm._adding_custom_section = false;
            }
        });
    }

    function create_custom_section_ui(frm) {
        const $form_root = (frm.layout && frm.layout.wrapper) ? $(frm.layout.wrapper) : $(frm.wrapper);

        // If a section already exists for this exact document, don't recreate it
        const $existing = $form_root.find('.custom-tab-section').first();
        if ($existing.length) {
            const matches_doc = $existing.attr('data-doctype') === frm.doctype
                && $existing.attr('data-docname') === frm.docname;
            if (matches_doc) {
                // Already exists — just update references and load data
                frm.custom_section_wrapper = $existing;
                frm.linked_docs_container = $existing.find('.linked-docs-container');
                load_linked_documents(frm, frm.linked_docs_container);
                return;
            }
            // Stale section from a different document — remove it
            $existing.remove();
        }

        // Create a compact custom section in the form layout
        let wrapper = $('<div class="custom-tab-section"></div>')
            .attr('data-doctype', frm.doctype)
            .attr('data-docname', frm.docname)
            .css({
                'margin': '10px 0',
                'padding': '12px 15px',
                'background-color': '#f8f9fa',
                'border': '1px solid #dee2e6',
                'border-radius': '4px',
                'display': 'flex',
                'flex-direction': 'column',
                'gap': '10px',
                'min-height': '60px'
            });

        // Create container for linked documents (horizontal layout)
        let linked_docs_container = $('<div class="linked-docs-container"></div>').css({
            'display': 'flex',
            'flex-wrap': 'wrap',
            'gap': '8px',
            'align-items': 'center',
            'min-height': '30px'
        });

        // Show a subtle placeholder (not a flashy skeleton)
        linked_docs_container.html(
            '<span style="color: #adb5bd; font-size: 12px;">Loading documents…</span>'
        );

        wrapper.append(linked_docs_container);

        // Create button container aligned to right bottom
        let button_container = $('<div class="button-container"></div>').css({
            'display': 'flex',
            'justify-content': 'flex-end',
            'align-items': 'center',
            'gap': '8px'
        });

        // Create the custom tab button
        let open_tab_button = $('<button class="btn btn-primary btn-sm"></button>')
            .text('Document Flow')
            .on('click', function () {
                show_custom_tab_dialog(frm);
            });

        button_container.append(open_tab_button);

        // Keep only Document Flow action in smart buttons section

        wrapper.append(button_container);

        // Insert the section right after the form header
        if (frm.layout && frm.layout.wrapper) {
            $(frm.layout.wrapper).prepend(wrapper);
        } else {
            // Fallback: add to form wrapper
            $(frm.wrapper).find('.form-layout').prepend(wrapper);
        }

        // Store references
        frm.custom_section_wrapper = wrapper;
        frm.linked_docs_container = linked_docs_container;

        // Load and display linked documents
        load_linked_documents(frm, linked_docs_container);
    }

    /**
     * Cache for linked documents per document.
     * Key: "doctype::docname", Value: { data, timestamp }
     */
    const _linked_docs_cache = {};
    const LINKED_DOCS_CACHE_DURATION = 10000; // 10 seconds

    function load_linked_documents(frm, container) {
        // Throttle repeated refresh calls that happen during rapid form refresh cycles
        const now = Date.now();
        if (frm._linked_docs_request_inflight) {
            return;
        }
        if (frm._linked_docs_last_requested_at && (now - frm._linked_docs_last_requested_at) < LINKED_DOCS_THROTTLE_MS) {
            return;
        }

        // Check local cache first — render immediately from cache to avoid flicker
        const cache_key = frm.doctype + '::' + frm.docname;
        const cached = _linked_docs_cache[cache_key];
        if (cached && (now - cached.timestamp) < LINKED_DOCS_CACHE_DURATION) {
            _render_linked_docs(container, cached.data);
            return;
        }

        frm._linked_docs_last_requested_at = now;
        frm._linked_docs_request_inflight = true;

        // Get linked documents with counts
        frappe.call({
            method: "next_custom_app.next_custom_app.utils.procurement_workflow.get_linked_documents_with_counts",
            args: {
                doctype: frm.doctype,
                docname: frm.docname
            },
            callback: function (r) {
                frm._linked_docs_request_inflight = false;

                if (r.message) {
                    // Cache the result
                    _linked_docs_cache[cache_key] = {
                        data: r.message,
                        timestamp: Date.now()
                    };
                    _render_linked_docs(container, r.message);
                } else {
                    container.html('<span style="color: #6c757d; font-size: 12px;"><i>No connected documents</i></span>');
                }
            },
            error: function () {
                frm._linked_docs_request_inflight = false;
                container.html('<span style="color: #dc3545; font-size: 12px;"><i>Error loading</i></span>');
            }
        });
    }

    /**
     * Render linked document buttons into the container.
     * Only updates the DOM if the content has actually changed,
     * preventing unnecessary reflows and visual flicker.
     */
    function _render_linked_docs(container, linked_docs) {
        const has_backward = linked_docs.backward && linked_docs.backward.length > 0;
        const has_forward = linked_docs.forward && linked_docs.forward.length > 0;

        if (!has_backward && !has_forward) {
            container.html(
                '<span style="color: #6c757d; font-size: 12px;"><i>No connected documents</i></span>'
            );
            return;
        }

        // Build a fingerprint of the current data to detect changes
        const new_fingerprint = JSON.stringify(linked_docs);
        if (container.attr('data-fingerprint') === new_fingerprint) {
            // Data hasn't changed — skip DOM update entirely
            return;
        }
        container.attr('data-fingerprint', new_fingerprint);

        // Clear container and rebuild
        container.empty();

        if (has_backward) {
            linked_docs.backward.forEach(function (link) {
                container.append(create_linked_doc_button(link, 'backward'));
            });
        }

        if (has_forward) {
            linked_docs.forward.forEach(function (link) {
                container.append(create_linked_doc_button(link, 'forward'));
            });
        }
    }

    function create_linked_doc_button(link, direction) {

        let btn = $('<button class="btn btn-default btn-xs"></button>')
            .css({
                'padding': '4px 10px',
                'border': '1px solid #dee2e6',
                'border-radius': '3px',
                'background-color': direction === 'backward' ? '#e3f2fd' : '#fff3cd',
                'cursor': 'pointer',
                'font-size': '12px',
                'white-space': 'nowrap'
            })
            .html(`
            <span style="font-weight: 500;">${link.doctype}</span>
            <span style="background: #fff; padding: 1px 6px; margin-left: 4px; border-radius: 8px; font-size: 10px; font-weight: 600;">${link.count}</span>
        `)
            .on('click', function () {

                if (link.count === 1) {
                    // Single document - navigate directly
                    frappe.set_route('Form', link.doctype, link.documents[0]);
                } else {
                    // Multiple documents - show list
                    frappe.set_route('List', link.doctype, {
                        name: ['in', link.documents]
                    });
                }
            })
            .on('mouseenter', function () {
                $(this).css('opacity', '0.8');
            })
            .on('mouseleave', function () {
                $(this).css('opacity', '1');
            });

        return btn;
    }

    function show_custom_tab_dialog(frm) {

        // Create a dialog to display document flow
        let dialog = new frappe.ui.Dialog({
            title: __('Document Flow - {0}: {1}', [frm.doctype, frm.doc.name]),
            size: 'large',
            fields: [
                {
                    fieldtype: 'HTML',
                    fieldname: 'flow_content'
                }
            ],
            primary_action_label: __('Close'),
            primary_action: function () {
                dialog.hide();
            }
        });

        dialog.show();

        // Get the container element after dialog is shown and remove default padding
        let container = dialog.fields_dict.flow_content.$wrapper;
        container.css({
            'margin': '0',
            'padding': '0'
        });
        container.html('<div style="padding: 15px; min-height: 300px;"><p>Loading document flow...</p></div>');

        // Load document flow with statuses
        frappe.call({
            method: "next_custom_app.next_custom_app.utils.procurement_workflow.get_document_flow_with_statuses",
            args: {
                doctype: frm.doctype,
                docname: frm.docname
            },
            callback: function (r) {
                if (r.message) {
                    render_document_flow(r.message, container);
                } else {
                    console.error('*** No message in response:', r);
                    container.html('<div style="padding: 20px;"><p style="color: #999;">No flow data available.</p></div>');
                }
            },
            error: function (err) {
                console.error('*** Error loading flow:', err);
                const error_msg = err ? (err.message || JSON.stringify(err)) : 'Unknown error';
                container.html('<div style="padding: 20px;"><p style="color: #dc3545;">Error: ' + error_msg + '</p></div>');
            }
        });
    }

    function show_analysis_dialog(frm) {

        let dialog = new frappe.ui.Dialog({
            title: __('Procurement Analysis - {0}: {1}', [frm.doctype, frm.doc.name]),
            size: 'large',
            fields: [
                {
                    fieldtype: 'HTML',
                    fieldname: 'analysis_content'
                }
            ],
            primary_action_label: __('Close'),
            primary_action: function () {
                dialog.hide();
            }
        });

        dialog.show();

        // Get the container element after dialog is shown and remove default padding
        let container = dialog.fields_dict.analysis_content.$wrapper;
        container.css({
            'margin': '0',
            'padding': '0'
        });
        container.html('<div style="padding: 15px; min-height: 300px;"><p>Loading analysis...</p></div>');

        // Load analysis data
        frappe.call({
            method: "next_custom_app.next_custom_app.utils.procurement_workflow.get_procurement_analysis",
            args: {
                doctype: frm.doctype,
                docname: frm.docname
            },
            callback: function (r) {
                if (r.message) {
                    render_analysis(r.message, container);
                } else {
                    console.error('*** No message in analysis response:', r);
                    container.html('<div style="padding: 20px;"><p style="color: #999;">No analysis data available.</p></div>');
                }
            },
            error: function (err) {
                console.error('*** Error loading analysis:', err);
                const error_msg = err ? (err.message || JSON.stringify(err)) : 'Unknown error';
                container.html('<div style="padding: 20px;"><p style="color: #dc3545;">Error: ' + error_msg + '</p></div>');
            }
        });
    }

    function render_document_flow(flow_data, container) {
        const doctypeColors = {
            'Material Request': { main: '#8e44ad', light: '#f4ecf8' },
            'Purchase Requisition': { main: '#3498db', light: '#ebf5fb' },
            'Request for Quotation': { main: '#e67e22', light: '#fef5e7' },
            'Supplier Quotation': { main: '#16a085', light: '#e8f8f5' },
            'Purchase Order': { main: '#2c3e50', light: '#eef2f5' },
            'Purchase Receipt': { main: '#27ae60', light: '#eafaf1' },
            'Purchase Invoice': { main: '#c0392b', light: '#fdedec' },
            'Payment Request': { main: '#6f42c1', light: '#f3effd' },
            'Payment Entry': { main: '#0d6efd', light: '#e7f1ff' },
            'Stock Entry': { main: '#6c757d', light: '#f8f9fa' }
        };

        function getDoctypeColor(doctype, isCurrent, isGrayed) {
            const base = doctypeColors[doctype] || { main: '#495057', light: '#f8f9fa' };
            // Keep colors consistent even when node is outside focused path.
            if (isGrayed) return { main: base.main, light: base.light };
            if (isCurrent) return { main: '#0d6efd', light: '#e7f1ff' };
            return base;
        }

        function getStatusStyle(statusText) {
            const status = (statusText || '').toLowerCase();
            if (status.includes('complete')) return { bg: '#e8f8f0', color: '#198754' };
            if (status.includes('approve') || status.includes('submit')) return { bg: '#e7f1ff', color: '#0d6efd' };
            if (status.includes('bill')) return { bg: '#fff8e1', color: '#b7791f' };
            if (status.includes('unpaid')) return { bg: '#fff1f2', color: '#dc3545' };
            return { bg: '#eef2f7', color: '#475569' };
        }

        function flattenByLevel(rootNodes) {
            const levels = [];
            const queue = [];
            (rootNodes || []).forEach(node => queue.push({ node, level: 0 }));

            while (queue.length) {
                const { node, level } = queue.shift();
                if (!levels[level]) levels[level] = [];
                levels[level].push(node);
                (node.children || []).forEach(child => queue.push({ node: child, level: level + 1 }));
            }

            return levels;
        }

        function nodeKey(node) {
            return `${node.doctype}::${node.name}`;
        }

        function renderNodeCard(node) {
            const c = getDoctypeColor(node.doctype, node.is_current, node.is_grayed);
            const status = node.workflow_state || node.status || 'Draft';
            const statusStyle = getStatusStyle(status);
            const key = nodeKey(node);
            const sourceKey = (node.source_doctype && node.source_name)
                ? `${node.source_doctype}::${node.source_name}`
                : '';
            const sourceLabel = (node.source_doctype && node.source_name)
                ? `${node.source_doctype}: ${node.source_name}`
                : '';

            return `
                <div
                    data-node-key="${frappe.utils.escape_html(key)}"
                    data-source-key="${frappe.utils.escape_html(sourceKey)}"
                    data-doctype="${frappe.utils.escape_html(node.doctype)}"
                    data-source-label="${frappe.utils.escape_html(sourceLabel)}"
                    style="
                        min-width: 210px;
                        max-width: 240px;
                        background: #fff;
                        border: 1px solid ${c.main}33;
                        border-left: 3px solid ${c.main};
                        border-radius: 7px;
                        padding: 6px 8px;
                        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
                        cursor: pointer;
                        position: relative;
                        z-index: 4;
                    "
                    onclick="frappe.set_route('Form', '${node.doctype}', '${node.name}')"
                >
                    <div style="display:flex; align-items:center; justify-content:space-between; gap:6px; margin-bottom:4px;">
                        <div style="font-size:9px; font-weight:700; text-transform:uppercase; color:${c.main}; letter-spacing:.3px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">
                            ${node.doctype}
                        </div>
                        <div style="font-size:9px; font-weight:700; padding:1px 6px; border-radius:999px; background:${statusStyle.bg}; color:${statusStyle.color}; white-space:nowrap;">
                            ${status}
                        </div>
                    </div>
                    <div style="font-size:11px; font-weight:600; color:#1f2937; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">
                        ${node.name}
                    </div>
                    ${sourceLabel ? `
                        <div style="
                            margin-top: 4px;
                            border-top: 1px dashed #e2e8f0;
                            padding-top: 3px;
                            font-size: 9px;
                            color: #64748b;
                            white-space: nowrap;
                            overflow: hidden;
                            text-overflow: ellipsis;
                        ">↳ from ${sourceLabel}</div>
                    ` : ''}
                </div>
            `;
        }

        function renderLevel(levelNodes, levelNo) {
            const lanes = {};
            levelNodes.forEach(n => {
                if (!lanes[n.doctype]) lanes[n.doctype] = [];
                lanes[n.doctype].push(n);
            });

            const laneHtml = Object.entries(lanes)
                .map(([dt, docs]) => {
                    const c = getDoctypeColor(dt, false, false);
                    return `
                        <div style="
                            background: #ffffffd9;
                            border: 1px solid #e5e7eb;
                            border-top: 3px solid ${c.main};
                            border-radius: 8px;
                            padding: 6px;
                            min-width: 230px;
                        ">
                            <div style="display:flex; align-items:center; justify-content:space-between; margin-bottom:6px; gap:6px;">
                                <div style="font-size:10px; font-weight:700; color:${c.main}; text-transform:uppercase; letter-spacing:.3px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">
                                    ${dt}
                                </div>
                                <div style="font-size:9px; font-weight:700; color:${c.main}; background:${c.light}; border:1px solid ${c.main}33; border-radius:999px; padding:1px 6px;">
                                    ${docs.length}
                                </div>
                            </div>
                            <div style="display:flex; flex-direction:column; gap:6px;">
                                ${docs.map(renderNodeCard).join('')}
                            </div>
                        </div>
                    `;
                })
                .join('');

            return `
                <div style="margin-bottom:16px; position:relative;">
                    <div style="display:flex; align-items:center; gap:7px; margin-bottom:6px;">
                        <div style="font-size:11px; font-weight:700; color:#111827;">Step ${levelNo + 1}</div>
                        <div style="height:1px; background:#e5e7eb; flex:1;"></div>
                    </div>
                    <div style="display:flex; flex-wrap:wrap; gap:12px; align-items:flex-start; justify-content:center;">
                        ${laneHtml}
                    </div>
                </div>
            `;
        }

        function drawConnections(wrapperEl) {
            const cards = wrapperEl.querySelectorAll('[data-node-key]');
            if (!cards.length) return;

            const keyMap = {};
            cards.forEach(card => {
                keyMap[card.getAttribute('data-node-key')] = card;
            });

            const svgNS = 'http://www.w3.org/2000/svg';
            const svg = document.createElementNS(svgNS, 'svg');

            svg.setAttribute('width', wrapperEl.scrollWidth);
            svg.setAttribute('height', wrapperEl.scrollHeight);

            svg.style.position = 'absolute';
            svg.style.left = '0';
            svg.style.top = '0';
            svg.style.pointerEvents = 'none';
            svg.style.zIndex = '1';

            // Arrow marker
            const defs = document.createElementNS(svgNS, 'defs');
            const marker = document.createElementNS(svgNS, 'marker');

            marker.setAttribute('id', 'arrow');
            marker.setAttribute('markerWidth', '8');
            marker.setAttribute('markerHeight', '8');
            marker.setAttribute('refX', '7');
            marker.setAttribute('refY', '3.5');
            marker.setAttribute('orient', 'auto');

            const arrowPath = document.createElementNS(svgNS, 'path');
            arrowPath.setAttribute('d', 'M0,0 L7,3.5 L0,7 Z');
            arrowPath.setAttribute('fill', '#6b7280');

            marker.appendChild(arrowPath);
            defs.appendChild(marker);
            svg.appendChild(defs);

            // Track branching per source
            const usage = {};

            cards.forEach(target => {
                const sourceKey = target.getAttribute('data-source-key');
                if (!sourceKey || !keyMap[sourceKey]) return;

                const source = keyMap[sourceKey];

                const s = source.getBoundingClientRect();
                const t = target.getBoundingClientRect();
                const w = wrapperEl.getBoundingClientRect();

                // Base positions
                let x1 = (s.left + s.width / 2) - w.left;
                let y1 = (s.bottom) - w.top;

                let x2 = (t.left + t.width / 2) - w.left;
                let y2 = (t.top) - w.top;

                // Spread siblings (VERY IMPORTANT)
                usage[sourceKey] = (usage[sourceKey] || 0) + 1;
                const idx = usage[sourceKey] - 1;

                const spacing = 20;
                const offset = (idx * spacing) - spacing;

                x1 += offset;

                // Define routing levels
                const verticalGap = 25;
                const midY = y1 + verticalGap;

                // Build ORTHOGONAL path
                const path = document.createElementNS(svgNS, 'path');

                const d = `
                    M ${x1} ${y1}
                    L ${x1} ${midY}
                    L ${x2} ${midY}
                    L ${x2} ${y2}
                `;

                path.setAttribute('d', d);
                path.setAttribute('fill', 'none');
                path.setAttribute('stroke', '#94a3b8');
                path.setAttribute('stroke-width', '1.6');
                path.setAttribute('stroke-linecap', 'round');
                path.setAttribute('stroke-linejoin', 'round');
                path.setAttribute('marker-end', 'url(#arrow)');

                svg.appendChild(path);
            });

            const old = wrapperEl.querySelector('svg.doc-flow-connections');
            if (old) old.remove();

            svg.classList.add('doc-flow-connections');
            wrapperEl.appendChild(svg);
        }

        const levels = flattenByLevel(flow_data.nodes || []);
        const wrapperId = `doc-flow-${frappe.utils.get_random(6)}`;

        let html = `<div id="${wrapperId}" style="height:100%; overflow:auto; padding:12px; background:linear-gradient(180deg,#f9fafb 0%, #f5f7fb 100%); position:relative;">
            <div style="max-width:1320px; margin:0 auto; position:relative; z-index:2;">`;
        if (!levels.length) {
            html += '<div style="text-align:center; color:#6b7280; padding:24px 8px;">No document flow available</div>';
        } else {
            html += levels.map((nodes, idx) => renderLevel(nodes, idx)).join('');
        }
        html += '</div></div>';

        container.html(html);

        setTimeout(() => {
            const wrapperEl = container.find(`#${wrapperId}`)[0];
            if (wrapperEl) drawConnections(wrapperEl);
        }, 30);
    }

    function render_analysis(analysis_data, container) {

        // Remove any default padding/margin from container
        container.css({
            'margin': '0',
            'padding': '0'
        });

        // Direct content without nested cards - use full dialog space
        let html = '<div style="font-family: -apple-system, BlinkMacSystemFont, \'Segoe UI\', Roboto, sans-serif; padding: 20px; height: 100%; overflow-y: auto;">';

        // Summary section
        html += '<h4 style="margin: 0 0 15px 0; color: #495057;">Procurement Summary</h4>';
        html += '<div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin-bottom: 25px;">';

        const metrics = [
            { label: 'Total Child Documents', value: analysis_data.total_children || 0, color: '#0d6efd' },
            { label: 'Total Items', value: analysis_data.total_items || 0, color: '#198754' },
            { label: 'Total Quantity', value: analysis_data.total_quantity || 0, color: '#ffc107' },
            { label: 'Completion Rate', value: (analysis_data.completion_rate || 0) + '%', color: '#0dcaf0' }
        ];

        metrics.forEach(metric => {
            html += `
            <div style="padding: 15px; background: linear-gradient(135deg, ${metric.color}15 0%, ${metric.color}05 100%); border-left: 4px solid ${metric.color}; border-radius: 4px;">
                <div style="font-size: 24px; font-weight: 700; color: ${metric.color}; margin-bottom: 5px;">
                    ${metric.value}
                </div>
                <div style="font-size: 12px; color: #6c757d; text-transform: uppercase; letter-spacing: 0.5px;">
                    ${metric.label}
                </div>
            </div>
        `;
        });

        html += '</div>';

        // Item breakdown
        if (analysis_data.items_breakdown && analysis_data.items_breakdown.length > 0) {
            html += '<h4 style="margin: 25px 0 15px 0; color: #495057;">Items Breakdown</h4>';
            html += '<table style="width: 100%; border-collapse: collapse;">';
            html += '<thead><tr style="background: #f8f9fa; border-bottom: 2px solid #dee2e6;">';
            html += '<th style="padding: 10px; text-align: left; font-size: 12px; color: #6c757d; text-transform: uppercase;">Item</th>';
            html += '<th style="padding: 10px; text-align: right; font-size: 12px; color: #6c757d; text-transform: uppercase;">Source Qty</th>';
            html += '<th style="padding: 10px; text-align: right; font-size: 12px; color: #6c757d; text-transform: uppercase;">Consumed</th>';
            html += '<th style="padding: 10px; text-align: right; font-size: 12px; color: #6c757d; text-transform: uppercase;">Available</th>';
            html += '<th style="padding: 10px; text-align: right; font-size: 12px; color: #6c757d; text-transform: uppercase;">% Used</th>';
            html += '</tr></thead><tbody>';

            analysis_data.items_breakdown.forEach(item => {
                const percent_used = ((item.consumed / item.source_qty) * 100).toFixed(1);
                const bar_color = percent_used >= 100 ? '#dc3545' : percent_used >= 80 ? '#ffc107' : '#198754';

                html += `<tr style="border-bottom: 1px solid #dee2e6;">
                <td style="padding: 10px;">${item.item_code}</td>
                <td style="padding: 10px; text-align: right;">${item.source_qty}</td>
                <td style="padding: 10px; text-align: right;">${item.consumed}</td>
                <td style="padding: 10px; text-align: right; font-weight: 600; color: ${item.available <= 0 ? '#dc3545' : '#198754'};">
                    ${item.available}
                </td>
                <td style="padding: 10px; text-align: right;">
                    <div style="display: flex; align-items: center; justify-content: flex-end; gap: 8px;">
                        <div style="flex: 1; max-width: 100px; height: 8px; background: #e9ecef; border-radius: 4px; overflow: hidden;">
                            <div style="width: ${Math.min(percent_used, 100)}%; height: 100%; background: ${bar_color}; transition: width 0.3s;"></div>
                        </div>
                        <span style="font-weight: 600; color: ${bar_color};">${percent_used}%</span>
                    </div>
                </td>
            </tr>`;
            });

            html += '</tbody></table>';
        }

        html += '</div>';

        container.html(html);
    }

    // Log at the end of the script
}
