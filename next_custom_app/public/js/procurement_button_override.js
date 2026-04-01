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
 * The list of procurement doctypes is fetched dynamically from the active
 * Procurement Flow. A hardcoded fallback list is used until the async call
 * completes (or if no active flow exists).
 *
 * Copyright (c) 2025, Nextcore Technologies and contributors
 * For license information, please see license.txt
 */

(function () {
    'use strict';

    // Guard: only apply once per page load
    if (window.__procurement_button_override_applied) return;
    window.__procurement_button_override_applied = true;

    // ── Fallback list — used immediately while the async API call resolves ──
    const FALLBACK_PROCUREMENT_DOCTYPES = [
        'Material Request',
        'Purchase Requisition',
        'Request for Quotation',
        'Supplier Quotation',
        'Purchase Order',
        'Purchase Receipt',
        'Purchase Invoice',
        'Stock Entry'
    ];

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
     *   - For draft docs (docstatus === 0): delegates to the original ERPNext implementation
     *   - For submitted docs (docstatus === 1): does nothing (buttons suppressed)
     *   - For cancelled docs (docstatus === 2): does nothing
     *
     * Additionally, we intercept `frm.page.set_inner_btn_group_as_primary` and
     * `frm.add_custom_button` for submitted docs to prevent ERPNext controllers
     * from adding buttons directly in their refresh handler (bypassing
     * make_custom_buttons). This is the zero-flicker approach.
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

                // Re-check: if ERPNext replaced our patched function, re-patch it
                if (frm.events.make_custom_buttons &&
                    !frm.events.make_custom_buttons.__is_procurement_override) {

                    var current_fn = frm.events.make_custom_buttons;
                    // Don't re-capture if it's already our wrapper
                    if (current_fn !== frm.events.__patched_make_custom_buttons) {
                        frm.events.__original_make_custom_buttons = current_fn;

                        var patched = function (form) {
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
     */
    function _install_button_interceptor(frm) {
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

            // Strip translation wrapper for comparison
            var clean_label = (label || '').replace(/^__\(["']|["']\)$/g, '');

            // Block known default ERPNext buttons
            if (BLOCKED_LABELS.has(clean_label)) {
                // Return a dummy jQuery object so callers don't crash
                return $('<button style="display:none">');
            }

            // Allow unknown buttons through (could be from other apps)
            return frm.__original_add_custom_button(label, click, group);
        };
    }

    // ── Step 1: Register overrides for the fallback list immediately ──
    // This ensures coverage even before the async API call returns.
    FALLBACK_PROCUREMENT_DOCTYPES.forEach(register_override);

    // ── Step 2: Fetch the actual doctypes from the active Procurement Flow ──
    // Any additional doctypes discovered will be registered dynamically.
    frappe.call({
        method: 'next_custom_app.next_custom_app.utils.procurement_workflow.get_procurement_doctypes',
        async: true,
        callback: function (r) {
            if (r && r.message && Array.isArray(r.message)) {
                r.message.forEach(register_override);
                console.log('[Procurement] Button override registered for flow doctypes:', r.message.join(', '));
            }
        },
        error: function () {
            // Fallback list is already registered — nothing to do
            console.warn('[Procurement] Could not fetch flow doctypes; using fallback list.');
        }
    });

    console.log('[Procurement] Button override initialised with fallback doctypes:', FALLBACK_PROCUREMENT_DOCTYPES.join(', '));
})();
