/**
 * Procurement Button Override
 * ===========================
 * This script is loaded globally via app_include_js BEFORE any doctype-specific
 * JS files. It intercepts ERPNext's `make_custom_buttons` method on procurement
 * doctypes so that the default "Create" dropdown buttons are never added to
 * submitted documents.
 *
 * This eliminates UI flicker entirely — no setTimeout, no MutationObserver,
 * no DOM manipulation hacks.
 *
 * For draft documents (docstatus === 0), ERPNext's default behaviour is preserved.
 *
 * The overrides are registered synchronously for all procurement doctypes to
 * ensure they are in place before ERPNext's controllers run. However, the
 * actual button suppression only takes effect when an active Procurement Flow
 * exists. The active flow status is checked asynchronously and cached.
 *
 * Copyright (c) 2025, Nextcore Technologies and contributors
 * For license information, please see license.txt
 */

(function () {
    'use strict';

    // Guard: only apply once per page load
    if (window.__procurement_button_override_applied) return;
    window.__procurement_button_override_applied = true;

    // ── Procurement doctypes to register overrides for ──
    const FALLBACK_PROCUREMENT_DOCTYPES = [
        'Material Request',
        'Purchase Requisition',
        'Request for Quotation',
        'Supplier Quotation',
        'Purchase Order',
        'Purchase Receipt',
        'Purchase Invoice',
        'Stock Entry',
        'Payment Request',
        'Payment Entry'
    ];

    // ── Active flow state ──
    // null = not yet checked, true = active, false = not active
    window.__procurement_flow_active = null;

    // Check active flow status asynchronously and cache the result
    frappe.call({
        method: 'next_custom_app.next_custom_app.utils.procurement_workflow.get_active_flow',
        async: true,
        callback: function (r) {
            window.__procurement_flow_active = !!(r && r.message);
            if (!window.__procurement_flow_active) {
                console.log('[Procurement] No active procurement flow — button suppression disabled.');
            } else {
                console.log('[Procurement] Active procurement flow detected — button suppression enabled.');
            }
        },
        error: function () {
            // On error, assume no active flow to avoid blocking default buttons
            window.__procurement_flow_active = false;
            console.warn('[Procurement] Could not check active flow; button suppression disabled.');
        }
    });

    /**
     * Check if the procurement flow is active.
     * Returns true if active, false if not active or not yet checked.
     * When not yet checked (null), we default to true (suppress) to avoid
     * flicker — the async check will update the state shortly.
     */
    function is_flow_active() {
        // If not yet checked, assume active to prevent flicker
        if (window.__procurement_flow_active === null) return true;
        return window.__procurement_flow_active;
    }

    // Track which doctypes have already been patched so we don't double-register
    const _patched_doctypes = {};

    /**
     * Register the make_custom_buttons override for a single doctype.
     *
     * Core strategy
     * -------------
     * ERPNext form controllers define a `make_custom_buttons` method in their
     * `frappe.ui.form.on(doctype, { ... })` events. During `refresh`, ERPNext
     * calls `frm.events.make_custom_buttons(frm)` which adds the default
     * "Create ▼" dropdown items (Request for Quotation, Purchase Order, etc.).
     *
     * We use `frappe.ui.form.on(doctype, { setup(frm) { ... } })` to
     * monkey-patch `frm.events.make_custom_buttons` the very first time the
     * form is set up. Because `setup` fires before `refresh`, our patched
     * version is in place before ERPNext ever calls it.
     *
     * The patched version:
     *   - If no active procurement flow: delegates to original ERPNext implementation
     *   - For draft docs (docstatus === 0): delegates to the original ERPNext implementation
     *   - For submitted docs (docstatus === 1): does nothing (buttons suppressed)
     *   - For cancelled docs (docstatus === 2): does nothing
     */
    function register_override(doctype) {
        if (_patched_doctypes[doctype]) return;
        _patched_doctypes[doctype] = true;

        frappe.ui.form.on(doctype, {
            setup: function (frm) {
                // Only patch once per form instance
                if (frm._procurement_btn_override_applied) return;
                frm._procurement_btn_override_applied = true;

                // Capture the original make_custom_buttons (may be undefined if
                // ERPNext hasn't registered its controller yet — that's fine,
                // we'll also try to capture it lazily on first call).
                var original_fn = frm.events && frm.events.make_custom_buttons;

                frm.events.make_custom_buttons = function (form) {
                    // Lazy capture: if the original wasn't available at setup time
                    if (!original_fn && form.events && form.events.__original_make_custom_buttons) {
                        original_fn = form.events.__original_make_custom_buttons;
                    }

                    // If no active procurement flow, run original ERPNext behaviour
                    if (!is_flow_active()) {
                        if (original_fn) {
                            return original_fn.call(this, form);
                        }
                        return;
                    }

                    // For submitted / cancelled documents: suppress default buttons entirely
                    if (form.doc.docstatus >= 1) {
                        return;
                    }

                    // For draft documents: run the original ERPNext behaviour
                    if (original_fn) {
                        return original_fn.call(this, form);
                    }
                };

                // Store the original so other scripts can access it if needed
                frm.events.__original_make_custom_buttons = original_fn;
            },

            // Belt-and-suspenders: also intercept in `refresh` which fires
            // alongside ERPNext's own refresh handler. This catches cases where
            // ERPNext re-registers make_custom_buttons after our setup ran.
            refresh: function (frm) {
                if (!frm._procurement_btn_override_applied) return;

                // If no active procurement flow, skip all overrides
                if (!is_flow_active()) return;

                // Re-check: if ERPNext replaced our patched function, re-patch it
                if (frm.events.make_custom_buttons &&
                    !frm.events.make_custom_buttons.__is_procurement_override) {

                    var current_fn = frm.events.make_custom_buttons;
                    // Don't re-capture if it's already our wrapper
                    if (current_fn !== frm.events.__patched_make_custom_buttons) {
                        frm.events.__original_make_custom_buttons = current_fn;

                        var patched = function (form) {
                            // If no active flow, run original
                            if (!is_flow_active()) {
                                if (frm.events.__original_make_custom_buttons) {
                                    return frm.events.__original_make_custom_buttons.call(this, form);
                                }
                                return;
                            }
                            if (form.doc.docstatus >= 1) {
                                return;
                            }
                            if (frm.events.__original_make_custom_buttons) {
                                return frm.events.__original_make_custom_buttons.call(this, form);
                            }
                        };
                        patched.__is_procurement_override = true;

                        frm.events.make_custom_buttons = patched;
                        frm.events.__patched_make_custom_buttons = patched;
                    }
                }

                // For submitted documents: install an add_custom_button interceptor
                // that blocks default ERPNext buttons while allowing our own workflow
                // buttons to pass through. This prevents flicker because buttons are
                // never added to the DOM in the first place.
                if (frm.doc.docstatus === 1) {
                    _install_button_interceptor(frm);
                }
            }
        });
    }

    /**
     * Install an interceptor on frm.add_custom_button that blocks default
     * ERPNext buttons on submitted procurement documents.
     *
     * This is the zero-flicker approach: instead of removing buttons after
     * they're added (which causes flicker), we prevent them from being added
     * in the first place.
     *
     * Our own procurement workflow buttons are allowed through because they
     * are added AFTER this interceptor is installed, and we mark them with
     * a special flag.
     *
     * If no active procurement flow exists, the interceptor is a no-op.
     */
    function _install_button_interceptor(frm) {
        // If no active flow, don't install the interceptor
        if (!is_flow_active()) return;

        // Only install once per form refresh cycle
        if (frm._procurement_btn_interceptor_installed) return;
        frm._procurement_btn_interceptor_installed = true;

        // Reset on next refresh
        var _orig_clear = frm.page.clear_custom_actions;
        if (_orig_clear && !_orig_clear.__procurement_wrapped) {
            frm.page.clear_custom_actions = function () {
                frm._procurement_btn_interceptor_installed = false;
                frm._procurement_allow_buttons = false;
                return _orig_clear.apply(this, arguments);
            };
            frm.page.clear_custom_actions.__procurement_wrapped = true;
        }

        // Labels of buttons that ERPNext adds by default on submitted procurement docs.
        var BLOCKED_LABELS = new Set([
            // Purchase Order default buttons
            'Purchase Receipt', 'Purchase Invoice', 'Payment',
            'Payment Request', 'Return', 'Subcontract',
            'Update Items', 'Close', 'Re-open',
            // Material Request default buttons
            'Request for Quotation', 'Supplier Quotation',
            'Purchase Order', 'Stock Entry', 'Pick List',
            'Material Transfer', 'Material Issue',
            // Purchase Receipt default buttons
            'Purchase Return', 'Make Stock Entry',
            'Retention Stock Entry',
            // Purchase Invoice default buttons
            'Debit Note', 'Payment',
            // Supplier Quotation default buttons
            'Purchase Order',
            // Payment Request default buttons (ERPNext uses "Create Payment Entry")
            'Payment Entry', 'Create Payment Entry',
            // Payment Entry default buttons
            'Resend Payment Email',
        ]);

        // Save original add_custom_button
        if (!frm.__original_add_custom_button) {
            frm.__original_add_custom_button = frm.add_custom_button.bind(frm);
        }

        frm.add_custom_button = function (label, click, group) {
            // Allow our own procurement workflow buttons through
            if (frm._procurement_allow_buttons) {
                return frm.__original_add_custom_button(label, click, group);
            }

            // If no active flow, allow all buttons through
            if (!is_flow_active()) {
                return frm.__original_add_custom_button(label, click, group);
            }

            // Strip translation wrapper for comparison
            var clean_label = (label || '').replace(/^__\(["']|["']\)$/g, '').trim();
            var clean_group = (group || '').toString().trim();

            // Strict PO rule: in submitted Purchase Order, only allow
            // Purchase Receipt + Payment Request inside Create group.
            if (frm.doctype === 'Purchase Order' && frm.doc.docstatus === 1 && clean_group === 'Create') {
                var ALLOWED_PO_CREATE = new Set(['Purchase Receipt', 'Payment Request']);
                if (!ALLOWED_PO_CREATE.has(clean_label)) {
                    return $('<button style="display:none">');
                }
            }

            // Block known default ERPNext buttons (exact match)
            if (BLOCKED_LABELS.has(clean_label)) {
                // Return a dummy jQuery object so callers don't crash
                return $('<button style="display:none">');
            }

            // Also block any button whose label starts with "Create " followed
            // by a known procurement doctype — catches ERPNext patterns like
            // "Create Payment Entry", "Create Purchase Receipt", etc.
            if (clean_label.indexOf('Create ') === 0) {
                var target_doctype = clean_label.substring(7); // Remove "Create "
                if (BLOCKED_LABELS.has(target_doctype)) {
                    return $('<button style="display:none">');
                }
            }

            // Allow unknown buttons through (could be from other apps)
            return frm.__original_add_custom_button(label, click, group);
        };
    }

    // ── Register overrides synchronously for all procurement doctypes ──
    // This ensures the overrides are in place BEFORE ERPNext's controllers run.
    // The actual suppression is gated by is_flow_active() inside each handler.
    FALLBACK_PROCUREMENT_DOCTYPES.forEach(register_override);

    // Also fetch the actual doctypes from the active flow to cover any extras
    frappe.call({
        method: 'next_custom_app.next_custom_app.utils.procurement_workflow.get_procurement_doctypes',
        async: true,
        callback: function (r) {
            if (r && r.message && Array.isArray(r.message)) {
                r.message.forEach(register_override);
            }
        },
        error: function () {
            // Fallback list is already registered — nothing to do
        }
    });

    console.log('[Procurement] Button override initialised for doctypes:', FALLBACK_PROCUREMENT_DOCTYPES.join(', '));
})();
