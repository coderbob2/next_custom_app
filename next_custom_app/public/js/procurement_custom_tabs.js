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
window.next_custom_app.__procurement_tabs_cache = window.next_custom_app.__procurement_tabs_cache || {
    next_step_by_doctype: {},
};

{

    // Log script initialization
    console.log('=== Procurement Custom Tabs Script Initializing ===');
    console.log('Script file loaded at:', new Date().toISOString());

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
    const CACHE_DURATION = 30000; // 30 seconds

    // Throttle linked docs calls per form instance
    const LINKED_DOCS_THROTTLE_MS = 600;

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
     * Add the "Create" button(s) directly in the page header.
     * These are primary action buttons for the next workflow step.
     */
    function add_next_step_buttons(frm) {
        if (frm.doc.docstatus !== 1) return;

        console.log('>>> add_next_step_buttons() called for:', frm.doctype);

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
            const next_doctypes = cached.next_doctypes || [];
            if (next_doctypes.length) {
                console.log('*** Using cached next steps:', next_doctypes);
                _add_next_step_buttons_to_form(frm, next_doctypes, get_next_step_label);
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
                console.log('*** get_next_steps API response:', r);

                if (r.message && Array.isArray(r.message) && r.message.length) {
                    const next_doctypes = r.message.map(step => step.doctype_name);

                    // Cache for 30s
                    window.next_custom_app.__procurement_tabs_cache.next_step_by_doctype[cache_key] = {
                        next_doctypes,
                        expires_at: Date.now() + CACHE_DURATION
                    };

                    console.log('*** Next doctypes found:', next_doctypes);
                    _add_next_step_buttons_to_form(frm, next_doctypes, get_next_step_label);
                } else {
                    console.log('*** No next step found in workflow - this is the final step');
                }
            },
            error: function (err) {
                console.error('*** Error getting next step:', err);
            }
        });
    }

    /**
     * Actually add the next step buttons to the form.
     * If there's only one next step, add it as a primary button.
     * If there are multiple (parallel steps), add them in a group.
     */
    function _add_next_step_buttons_to_form(frm, next_doctypes, get_next_step_label) {
        if (!next_doctypes || !next_doctypes.length) return;

        // Remove any previously added next-step buttons
        $(frm.page.wrapper).find('.procurement-next-step-btn').remove();

        // Allow our workflow buttons through the button interceptor
        // (set by procurement_button_override.js to block default ERPNext buttons)
        frm._procurement_allow_buttons = true;

        if (next_doctypes.length === 1) {
            // Single next step - add as a prominent primary button
            const next_doctype = next_doctypes[0];
            const label = get_next_step_label(next_doctype);

            frm.add_custom_button(
                __('Create {0}', [label]),
                function () {
                    console.log('*** Next Step button clicked for:', next_doctype);
                    show_custom_create_dialog(frm, next_doctype);
                }
            );

            // Style the button to make it prominent
            if (frm.custom_buttons[__('Create {0}', [label])]) {
                frm.custom_buttons[__('Create {0}', [label])]
                    .addClass('btn-primary-dark procurement-next-step-btn')
                    .removeClass('btn-default btn-secondary');
            }
        } else {
            // Multiple next steps (parallel) - add each as a button in a "Create" group
            next_doctypes.forEach(function (next_doctype) {
                const label = get_next_step_label(next_doctype);

                frm.add_custom_button(
                    __(label),
                    function () {
                        console.log('*** Create button clicked for:', next_doctype);
                        show_custom_create_dialog(frm, next_doctype);
                    },
                    __('Create')
                );
            });

            // Style the "Create" group button
            $(frm.page.wrapper).find('.inner-group-button').each(function () {
                const $group = $(this);
                const $mainBtn = $group.find('> button').first();
                if (($mainBtn.text() || '').trim() === 'Create') {
                    $mainBtn.addClass('btn-primary-dark procurement-next-step-btn')
                        .removeClass('btn-default btn-secondary');
                }
            });
        }

        // Reset the flag so future non-workflow button additions are still blocked
        frm._procurement_allow_buttons = false;

        console.log('*** Next step button(s) added successfully');
    }

    // Register event handlers for relevant procurement doctypes (idempotent per doctype)
    DOCTYPES_TO_REGISTER.forEach(function (doctype) {
        if (window.next_custom_app.__procurement_custom_tabs_registered_doctypes[doctype]) {
            console.log(`=== Procurement Custom Tabs already registered for ${doctype}; skipping ===`);
            return;
        }
        window.next_custom_app.__procurement_custom_tabs_registered_doctypes[doctype] = true;

        frappe.ui.form.on(doctype, {
            refresh: function (frm) {
                console.log(`=== ${doctype} REFRESH Event ===`);
                console.log('Document Name:', frm.doc.name);
                console.log('Document Status:', frm.doc.status);
                console.log('Document docstatus:', frm.doc.docstatus);
                console.log('Doctype:', frm.doctype);

                // Add a custom section with button (debounced)
                add_custom_section_debounced(frm);

                // If document is submitted, add next step button(s)
                // NOTE: Default ERPNext "Create" buttons are suppressed by
                // procurement_button_override.js (loaded globally via app_include_js)
                // which overrides make_custom_buttons — no DOM hacks needed.
                if (frm.doc.docstatus === 1) {
                    console.log('=== Document is SUBMITTED, adding next step button ===');

                    // Always re-add buttons on refresh because Frappe's
                    // page.clear_custom_actions() removes them each cycle.
                    add_next_step_buttons(frm);
                } else {
                    console.log('=== Document NOT submitted (docstatus: ' + frm.doc.docstatus + '), skipping button ===');
                }
            },

            onload: function (frm) {
                console.log(`=== ${doctype} ONLOAD Event ===`);
                console.log('Form loaded for:', frm.doc.name);
                console.log('Is new document (local):', frm.doc.__islocal);

                // Get form root for cleanup
                const $form_root = (frm.layout && frm.layout.wrapper) ? $(frm.layout.wrapper) : $(frm.wrapper);

                // Remove ALL existing custom sections from the DOM (cleanup from previous documents)
                const $existing_sections = $form_root.find('.custom-tab-section');
                if ($existing_sections.length > 0) {
                    console.log(`>>> Removing ${$existing_sections.length} existing custom section(s) from previous form`);
                    $existing_sections.remove();
                }

                // Clear any leftover references from previous form
                frm.custom_section_wrapper = null;
                frm.linked_docs_container = null;
                frm._adding_custom_section = false;
                frm._linked_docs_request_inflight = false;
                frm._linked_docs_last_requested_at = null;
            },

            before_save: function (frm) {
                console.log(`=== ${doctype} BEFORE SAVE ===`);
            },

            after_save: function (frm) {
                console.log(`=== ${doctype} AFTER SAVE - Refreshing linked documents ===`);
                // Only refresh the data, not recreate the whole section
                if (frm.custom_section_wrapper && frm.linked_docs_container && frm.linked_docs_container.length > 0) {
                    const container = frm.linked_docs_container;
                    container.html(`
                    <div style="display: flex; gap: 8px; align-items: center;">
                        <div style="width: 120px; height: 28px; background: linear-gradient(90deg, #e0e0e0 25%, #f0f0f0 50%, #e0e0e0 75%); background-size: 200% 100%; animation: loading 1.5s ease-in-out infinite; border-radius: 4px;"></div>
                    </div>
                `);
                    load_linked_documents(frm, container);
                }
            },

            onload_post_render: function (frm) {
                // Cleanup any duplicate sections that might have been created
                const sections = $('.custom-tab-section');
                if (sections.length > 1) {
                    console.log(`>>> Found ${sections.length} sections, removing duplicates`);
                    sections.slice(1).remove();
                    // Update frm reference to point to the remaining section
                    frm.custom_section_wrapper = sections.first();
                    frm.linked_docs_container = sections.first().find('.linked-docs-container');
                }
            }
        });
    });

    // Create debounced version of add_custom_section
    const add_custom_section_debounced = debounce(add_custom_section, 150);

    function show_custom_create_dialog(frm, next_doctype) {
        console.log('*** Showing custom create dialog for:', next_doctype);

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
                console.log('*** Creating document:', next_doctype);

                // Call the standard procurement workflow method
                frappe.call({
                    method: "next_custom_app.next_custom_app.utils.procurement_workflow.make_procurement_document",
                    args: {
                        source_name: frm.docname,
                        target_doctype: next_doctype
                    },
                    callback: function (r) {
                        if (r.message) {
                            console.log('*** Document created successfully:', r.message.name);
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
        console.log('*** Dialog displayed');
    }

    function add_custom_section(frm) {
        console.log('>>> add_custom_section() function called');
        console.log('>>> Form object:', frm);
        console.log('>>> Document name:', frm.doc.name);

        // Skip for new documents
        if (frm.doc.__islocal) {
            console.log('>>> Skipping custom section for new document');
            return;
        }

        // Work ONLY within this form's DOM to avoid interfering with other open tabs
        const $form_root = (frm.layout && frm.layout.wrapper) ? $(frm.layout.wrapper) : $(frm.wrapper);

        // Cleanup duplicates inside this form only
        const $existing_sections = $form_root.find('.custom-tab-section');
        if ($existing_sections.length > 1) {
            console.log(`>>> Found ${$existing_sections.length} sections in this form, removing duplicates`);
            $existing_sections.slice(1).remove();
        }

        // Prevent multiple simultaneous calls
        if (frm._adding_custom_section) {
            console.log('>>> Already adding custom section, skipping duplicate call');
            return;
        }

        // Reuse existing section when available (avoid repeated API calls on multiple refreshes)
        const existing_section = $form_root.find('.custom-tab-section').first();
        const existing_matches_doc = existing_section.length
            && existing_section.attr('data-doctype') === frm.doctype
            && existing_section.attr('data-docname') === frm.docname;

        if (existing_section.length > 0 && existing_matches_doc && !existing_section.hasClass('is-loading')) {
            console.log('>>> Section already exists in DOM, refreshing data only');
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
            console.log('>>> Using cached active flow result');
            frm._adding_custom_section = false;

            if (active_flow_cache) {
                create_custom_section_ui(frm);
            } else {
                console.log('>>> No active procurement workflow (cached) - skipping custom section');
            }
            return;
        }

        // Check if there's an active procurement workflow before showing the section
        console.log('>>> Checking for active procurement workflow...');
        frappe.call({
            method: "next_custom_app.next_custom_app.utils.procurement_workflow.get_active_flow",
            callback: function (r) {
                console.log('>>> Active flow check response:', r);

                // Cache the result
                active_flow_cache = r.message || null;
                active_flow_cache_time = Date.now();

                // Clear the flag
                frm._adding_custom_section = false;

                if (!r.message) {
                    console.log('>>> No active procurement workflow found - skipping custom section');
                    return;
                }

                console.log('>>> Active procurement workflow found:', r.message);
                // Proceed with creating the custom section
                create_custom_section_ui(frm);
            },
            error: function (err) {
                console.error('>>> Error checking active flow:', err);
                // Clear the flag
                frm._adding_custom_section = false;
                // Don't show the section if there's an error
            }
        });
    }

    function create_custom_section_ui(frm) {
        console.log('>>> create_custom_section_ui() function called');

        const $form_root = (frm.layout && frm.layout.wrapper) ? $(frm.layout.wrapper) : $(frm.wrapper);

        // Remove existing section only if it belongs to a different doc (stale UI)
        const $existing = $form_root.find('.custom-tab-section').first();
        if ($existing.length) {
            const matches_doc = $existing.attr('data-doctype') === frm.doctype && $existing.attr('data-docname') === frm.docname;
            if (!matches_doc) {
                $existing.remove();
                console.log('>>> Removed stale custom section (different document)');
            }
        }

        // Create a compact custom section in the form layout
        let wrapper = $('<div class="custom-tab-section is-loading"></div>')
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
                'min-height': '60px',
                'opacity': '1',
                'transition': 'opacity 0.2s ease-in-out'
            });

        // Create container for linked documents (horizontal layout) with loading skeleton
        let linked_docs_container = $('<div class="linked-docs-container"></div>').css({
            'display': 'flex',
            'flex-wrap': 'wrap',
            'gap': '8px',
            'align-items': 'center',
            'min-height': '30px'
        });

        // Add loading skeleton
        linked_docs_container.html(`
        <div class="loading-skeleton" style="display: flex; gap: 8px; align-items: center;">
            <div style="width: 120px; height: 28px; background: linear-gradient(90deg, #e0e0e0 25%, #f0f0f0 50%, #e0e0e0 75%); background-size: 200% 100%; animation: loading 1.5s ease-in-out infinite; border-radius: 4px;"></div>
            <div style="width: 140px; height: 28px; background: linear-gradient(90deg, #e0e0e0 25%, #f0f0f0 50%, #e0e0e0 75%); background-size: 200% 100%; animation: loading 1.5s ease-in-out infinite; border-radius: 4px; animation-delay: 0.1s;"></div>
            <div style="width: 100px; height: 28px; background: linear-gradient(90deg, #e0e0e0 25%, #f0f0f0 50%, #e0e0e0 75%); background-size: 200% 100%; animation: loading 1.5s ease-in-out infinite; border-radius: 4px; animation-delay: 0.2s;"></div>
        </div>
        <style>
            @keyframes loading {
                0% { background-position: 200% 0; }
                100% { background-position: -200% 0; }
            }
        </style>
    `);

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
                console.log('Document flow button clicked');
                show_custom_tab_dialog(frm);
            });

        button_container.append(open_tab_button);

        // Check if this is a source document (no procurement_source_name) and add View Analysis button
        if (!frm.doc.procurement_source_name && frm.doc.docstatus === 1) {
            let analysis_button = $('<button class="btn btn-default btn-sm"></button>')
                .html('<i class="fa fa-chart-line"></i> View Analysis')
                .on('click', function () {
                    console.log('View Analysis button clicked');
                    show_analysis_dialog(frm);
                });

            button_container.prepend(analysis_button);
        }

        wrapper.append(button_container);

        // Insert the section right after the form header
        if (frm.layout && frm.layout.wrapper) {
            $(frm.layout.wrapper).prepend(wrapper);
            console.log('>>> Custom section added successfully to layout wrapper');
        } else {
            // Fallback: add to form wrapper
            $(frm.wrapper).find('.form-layout').prepend(wrapper);
            console.log('>>> Custom section added to form wrapper (fallback)');
        }

        // Store references
        frm.custom_section_wrapper = wrapper;
        frm.linked_docs_container = linked_docs_container;

        // Load and display linked documents
        load_linked_documents(frm, linked_docs_container);

        console.log('>>> create_custom_section_ui() completed successfully');
    }

    function load_linked_documents(frm, container) {
        console.log('>>> load_linked_documents() called');
        console.log('>>> Document:', frm.doctype, frm.docname);
        console.log('>>> Document docstatus:', frm.doc.docstatus);

        // Throttle repeated refresh calls that happen during rapid form refresh cycles
        const now = Date.now();
        if (frm._linked_docs_request_inflight) {
            console.log('>>> Linked documents request already inflight; skipping');
            return;
        }
        if (frm._linked_docs_last_requested_at && (now - frm._linked_docs_last_requested_at) < LINKED_DOCS_THROTTLE_MS) {
            console.log('>>> Linked documents request throttled');
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
                console.log('*** Linked documents API response:', r);
                console.log('*** Response data:', JSON.stringify(r.message, null, 2));

                frm._linked_docs_request_inflight = false;

                // Remove loading state
                if (frm.custom_section_wrapper) {
                    frm.custom_section_wrapper.removeClass('is-loading');
                }

                if (r.message) {
                    const linked_docs = r.message;
                    const has_backward = linked_docs.backward && linked_docs.backward.length > 0;
                    const has_forward = linked_docs.forward && linked_docs.forward.length > 0;

                    console.log('*** Backward docs:', linked_docs.backward);
                    console.log('*** Forward docs:', linked_docs.forward);
                    console.log('*** Has backward:', has_backward, 'Has forward:', has_forward);

                    if (!has_backward && !has_forward) {
                        container.html(`
                        <span style="color: #6c757d; font-size: 12px;">
                            <i>No connected documents</i>
                        </span>
                    `);
                        return;
                    }

                    // Clear container
                    container.empty();

                    // Add all buttons horizontally - backward first, then forward
                    if (has_backward) {
                        linked_docs.backward.forEach(function (link) {
                            let btn = create_linked_doc_button(link, 'backward');
                            container.append(btn);
                        });
                    }

                    if (has_forward) {
                        linked_docs.forward.forEach(function (link) {
                            let btn = create_linked_doc_button(link, 'forward');
                            container.append(btn);
                        });
                    }

                    console.log('*** Linked documents displayed successfully');
                } else {
                    container.html('<span style="color: #6c757d; font-size: 12px;"><i>No connected documents</i></span>');
                }
            },
            error: function (err) {
                console.error('*** Error loading linked documents:', err);

                frm._linked_docs_request_inflight = false;

                // Remove loading state
                if (frm.custom_section_wrapper) {
                    frm.custom_section_wrapper.removeClass('is-loading');
                }

                container.html('<span style="color: #dc3545; font-size: 12px;"><i>Error loading</i></span>');
            }
        });
    }

    function create_linked_doc_button(link, direction) {
        console.log('*** Creating button for:', link.doctype, 'Count:', link.count);

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
                console.log('*** Linked doc button clicked:', link.doctype, 'Documents:', link.documents);

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
        console.log('*** BUTTON CLICKED - Opening custom tab dialog ***');
        console.log('*** Current document:', frm.doc.name);

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
        console.log('*** Calling get_document_flow_with_statuses for:', frm.doctype, frm.docname);
        frappe.call({
            method: "next_custom_app.next_custom_app.utils.procurement_workflow.get_document_flow_with_statuses",
            args: {
                doctype: frm.doctype,
                docname: frm.docname
            },
            callback: function (r) {
                console.log('*** Flow API response:', r);
                console.log('*** Flow data:', r.message);
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
        console.log('*** View Analysis button clicked ***');

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
        console.log('*** Calling get_procurement_analysis for:', frm.doctype, frm.docname);
        frappe.call({
            method: "next_custom_app.next_custom_app.utils.procurement_workflow.get_procurement_analysis",
            args: {
                doctype: frm.doctype,
                docname: frm.docname
            },
            callback: function (r) {
                console.log('*** Analysis API response:', r);
                console.log('*** Analysis data:', r.message);
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
        console.log('*** Rendering document flow:', flow_data);

        // Color mapping for different doctypes
        const doctypeColors = {
            'Material Request': { main: '#8e44ad', light: '#e8d5f0', border: '#8e44ad' },
            'Purchase Requisition': { main: '#3498db', light: '#d6eaf8', border: '#3498db' },
            'Request for Quotation': { main: '#e67e22', light: '#fdebd0', border: '#e67e22' },
            'Supplier Quotation': { main: '#16a085', light: '#d1f2eb', border: '#16a085' },
            'Purchase Order': { main: '#2c3e50', light: '#d5dbdb', border: '#2c3e50' },
            'Purchase Receipt': { main: '#27ae60', light: '#d5f4e6', border: '#27ae60' },
            'Purchase Invoice': { main: '#c0392b', light: '#f5d6d3', border: '#c0392b' }
        };

        function getDoctypeColor(doctype, is_current, is_grayed) {
            if (is_grayed) {
                return { main: '#9e9e9e', light: '#f5f5f5', border: '#e0e0e0' };
            }
            if (is_current) {
                return { main: '#0d6efd', light: '#e7f1ff', border: '#0d6efd' };
            }
            return doctypeColors[doctype] || { main: '#6c757d', light: '#f8f9fa', border: '#dee2e6' };
        }

        function renderCompactNode(node) {
            const colors = getDoctypeColor(node.doctype, node.is_current, node.is_grayed);
            const status = node.workflow_state || node.status || 'Draft';

            return `
            <div class="doc-node-compact" style="
                display: flex;
                align-items: center;
                gap: 6px;
                padding: 6px 12px;
                background: ${colors.light};
                border: 1.5px solid ${colors.border};
                border-radius: 20px;
                cursor: pointer;
                font-size: 12px;
                transition: all 0.2s;
                margin: 3px;
                min-width: 200px;
                max-width: 250px;
            " onclick="frappe.set_route('Form', '${node.doctype}', '${node.name}')"
               onmouseover="this.style.transform='scale(1.05)'; this.style.boxShadow='0 2px 8px rgba(0,0,0,0.15)'"
               onmouseout="this.style.transform='scale(1)'; this.style.boxShadow='none'">
                <span style="
                    background: ${colors.main};
                    color: white;
                    padding: 2px 8px;
                    border-radius: 12px;
                    font-size: 9px;
                    font-weight: 700;
                    text-transform: uppercase;
                    letter-spacing: 0.5px;
                ">${node.doctype.split(' ').map(w => w[0]).join('')}</span>
                <span style="
                    color: ${colors.main};
                    font-weight: 600;
                    overflow: hidden;
                    text-overflow: ellipsis;
                    white-space: nowrap;
                    flex: 1;
                ">${node.name}</span>
                <span style="
                    background: ${colors.main}15;
                    color: ${colors.main};
                    padding: 2px 6px;
                    border-radius: 8px;
                    font-size: 9px;
                    font-weight: 600;
                ">${status}</span>
            </div>
        `;
        }

        // Build grid structure: rows and columns
        function buildGridStructure(nodes, colIndex = 0, parentCol = null) {
            const grid = [];
            let currentCol = colIndex;

            nodes.forEach((node, idx) => {
                // Assign column to node
                node._gridCol = currentCol;
                node._gridRow = parentCol !== null ? parentCol._gridRow + 1 : 0;

                // Store parent reference for centering calculation
                node._parent = parentCol;

                // Add node to grid
                if (!grid[node._gridRow]) {
                    grid[node._gridRow] = [];
                }
                grid[node._gridRow].push(node);

                // Process children recursively
                if (node.children && node.children.length > 0) {
                    const childGrid = buildGridStructure(node.children, currentCol, node);
                    // Merge child grid into main grid
                    childGrid.forEach((row, rowIdx) => {
                        const actualRow = node._gridRow + 1 + rowIdx;
                        if (!grid[actualRow]) {
                            grid[actualRow] = [];
                        }
                        grid[actualRow].push(...row);
                    });

                    // Calculate how many columns this branch used
                    // Find the maximum column used by any descendant
                    let maxColUsed = currentCol;
                    childGrid.forEach(row => {
                        row.forEach(childNode => {
                            maxColUsed = Math.max(maxColUsed, childNode._gridCol);
                        });
                    });

                    // Move current column to after all descendants of this node
                    currentCol = maxColUsed + 1;
                } else {
                    // No children, just move to next column for next sibling
                    currentCol++;
                }
            });

            return grid;
        }

        function renderGrid(nodes) {
            if (!nodes || nodes.length === 0) return '';

            // Build grid structure
            const grid = buildGridStructure(nodes);

            // Calculate max columns needed
            let maxCol = 0;
            grid.forEach(row => {
                row.forEach(node => {
                    maxCol = Math.max(maxCol, node._gridCol);
                });
            });
            const numCols = maxCol + 1;

            // Get doctype for each row
            const rowDoctypes = grid.map(row => {
                if (row.length > 0) {
                    return row[0].doctype;
                }
                return '';
            });

            let html = '';

            // Render each row with its label
            grid.forEach((row, rowIdx) => {
                const doctype = rowDoctypes[rowIdx];
                const colors = getDoctypeColor(doctype, false, false);

                // Row container
                html += '<div style="display: flex; align-items: flex-start; margin-bottom: 25px; min-width: fit-content;">';

                // Row label (doctype)
                html += `<div style="
                min-width: 150px;
                padding: 8px 12px;
                background: ${colors.main}15;
                border-left: 4px solid ${colors.main};
                border-radius: 4px;
                margin-right: 20px;
                position: sticky;
                left: 0;
                background: #f8f9fa;
                z-index: 1;
            ">
                <div style="font-weight: 700; color: ${colors.main}; font-size: 12px; text-transform: uppercase; letter-spacing: 0.5px;">
                    ${doctype}
                </div>
                <div style="font-size: 10px; color: #6c757d; margin-top: 2px;">
                    ${row.length} document${row.length > 1 ? 's' : ''}
                </div>
            </div>`;

                // Documents in this row
                html += '<div style="display: flex; gap: 15px; flex-wrap: nowrap; align-items: flex-start; position: relative;">';

                // Create a map of column to node for this row
                const colMap = {};
                row.forEach(node => {
                    colMap[node._gridCol] = node;
                });

                // Check if there are siblings (multiple nodes with same parent)
                const siblingGroups = {};
                row.forEach(node => {
                    const parentKey = node._parent ? `${node._parent.doctype}::${node._parent.name}` : 'root';
                    if (!siblingGroups[parentKey]) {
                        siblingGroups[parentKey] = [];
                    }
                    siblingGroups[parentKey].push(node);
                });

                // Draw horizontal connector lines for sibling groups
                Object.values(siblingGroups).forEach(siblings => {
                    if (siblings.length > 1) {
                        const firstCol = siblings[0]._gridCol;
                        const lastCol = siblings[siblings.length - 1]._gridCol;
                        const parentNode = siblings[0]._parent;

                        if (parentNode) {
                            const nodeColors = getDoctypeColor(parentNode.doctype, parentNode.is_current, parentNode.is_grayed);
                            const lineColor = nodeColors.border;

                            // Calculate positions
                            const cellWidth = 260 + 15; // min-width + gap
                            const leftPos = firstCol * cellWidth + 130; // center of first cell
                            const lineWidth = (lastCol - firstCol) * cellWidth;

                            // Top horizontal line connecting siblings
                            html += `<div style="
                            position: absolute;
                            top: -15px;
                            left: ${leftPos}px;
                            width: ${lineWidth}px;
                            height: 2px;
                            background: ${lineColor};
                            z-index: 0;
                        "></div>`;

                            // Vertical lines dropping down from horizontal line to each sibling
                            siblings.forEach(sibling => {
                                const siblingPos = sibling._gridCol * cellWidth + 130;
                                html += `<div style="
                                position: absolute;
                                top: -15px;
                                left: ${siblingPos}px;
                                width: 2px;
                                height: 15px;
                                background: ${lineColor};
                                z-index: 0;
                            "></div>`;
                            });
                        }
                    }
                });

                // Render cells for each column
                for (let col = 0; col < numCols; col++) {
                    html += '<div style="min-width: 260px; display: flex; flex-direction: column; align-items: center; position: relative; z-index: 1;">';

                    if (colMap[col]) {
                        // Node exists in this position
                        html += renderCompactNode(colMap[col]);

                        // Add connector line to children if any
                        if (colMap[col].children && colMap[col].children.length > 0) {
                            const nodeColors = getDoctypeColor(colMap[col].doctype, colMap[col].is_current, colMap[col].is_grayed);
                            html += '<div style="width: 2px; height: 20px; background: ' + nodeColors.border + '; margin: 5px auto;"></div>';
                            html += '<div style="text-align: center; color: ' + nodeColors.border + '; font-size: 16px; line-height: 1;">▼</div>';
                        }
                    } else {
                        // Empty cell to maintain grid alignment
                        html += '<div style="height: 50px;"></div>';
                    }

                    html += '</div>';
                }

                html += '</div>'; // Close documents container
                html += '</div>'; // Close row container
            });

            return html;
        }

        // Direct scrollable container without nested cards - use full dialog space
        let html = '<div style="overflow-x: auto; overflow-y: auto; height: 100%; padding: 20px; background: #f8f9fa;">';

        if (flow_data.nodes && flow_data.nodes.length > 0) {
            html += renderGrid(flow_data.nodes);
        } else {
            html += '<p style="color: #6c757d; text-align: center; padding: 40px;">No document flow available</p>';
        }

        html += '</div>';

        container.html(html);
    }

    function render_analysis(analysis_data, container) {
        console.log('*** Rendering analysis:', analysis_data);

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
    console.log('=== Procurement Custom Tabs Script Loaded Successfully ===');
    console.log('=== Registered for doctypes:', DOCTYPES_TO_REGISTER.join(', '), '===');
}
