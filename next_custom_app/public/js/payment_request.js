// Payment Request Customizations
// Sets defaults, copies fields from PO, and manages custom fields
// Part of the Procurement Workflow Engine

frappe.ui.form.on("Payment Request", {
    setup(frm) {
        // Set payment_request_type to Outward and disable it
        frm.set_value("payment_request_type", "Outward");
        frm.set_df_property("payment_request_type", "read_only", 1);
    },

    onload(frm) {
        if (frm.is_new()) {
            // Set payment_request_type to Outward and disable
            frm.set_value("payment_request_type", "Outward");
            frm.set_df_property("payment_request_type", "read_only", 1);

            // Set requested_by to current user's full name
            frm.set_value("custom_requested_by", frappe.session.user_fullname || frappe.session.user);

            // Set email to current user's email
            frm.set_value("custom_requested_by_email", frappe.session.user);

            // Set mode_of_payment to Cash as default.
            // Use frappe.db.exists which is lighter and works with minimal permissions,
            // wrapped in error handler for users without Mode of Payment access.
            frappe.xcall('frappe.client.get_count', {
                doctype: 'Mode of Payment',
                filters: { name: 'Cash' }
            }).then(function (count) {
                if (count > 0) {
                    frm.set_value("mode_of_payment", "Cash");
                }
            }).catch(function () {
                // User may not have permission for Mode of Payment — just set it
                // and let the server validate on save
                frm.set_value("mode_of_payment", "Cash");
            });

            // Copy project and cost_center from Purchase Order if this was
            // created from a PO (via procurement workflow or standard flow)
            _copy_po_fields(frm);

            // Resolve purchase user defaults (only once on load for new docs)
            _resolve_purchase_user_defaults(frm, true);
        }
    },

    refresh(frm) {
        // Ensure payment_request_type stays Outward and disabled
        frm.set_value("payment_request_type", "Outward");
        frm.set_df_property("payment_request_type", "read_only", 1);

        // Only resolve defaults on refresh if the form is not new
        // (new forms already resolved in onload)
        if (!frm.is_new()) {
            _resolve_purchase_user_defaults(frm, false);
        }
    },

    custom_purchase_user(frm) {
        // When purchase user is explicitly changed, always re-resolve
        _resolve_purchase_user_defaults(frm, true);
    },

    currency(frm) {
        _resolve_purchase_user_defaults(frm, false);
    },

    company(frm) {
        _resolve_purchase_user_defaults(frm, false);
    },
});

/**
 * Copy company, project and cost_center from the linked Purchase Order (if any).
 * Checks both the procurement_source fields and the standard reference fields.
 */
function _copy_po_fields(frm) {
    let po_name = null;

    // Check procurement workflow source
    if (frm.doc.procurement_source_doctype === "Purchase Order" && frm.doc.procurement_source_name) {
        po_name = frm.doc.procurement_source_name;
    }

    // Check standard reference_doctype / reference_name
    if (!po_name && frm.doc.reference_doctype === "Purchase Order" && frm.doc.reference_name) {
        po_name = frm.doc.reference_name;
    }

    if (!po_name) return;

    frappe.call({
        method: "frappe.client.get_value",
        args: {
            doctype: "Purchase Order",
            filters: { name: po_name },
            fieldname: ["company", "project", "cost_center"],
        },
        callback: function (r) {
            if (r.message) {
                if (r.message.company && !frm.doc.company) {
                    frm.set_value("company", r.message.company);
                }
                if (r.message.project && !frm.doc.project) {
                    frm.set_value("project", r.message.project);
                }
                if (r.message.cost_center && !frm.doc.cost_center) {
                    frm.set_value("cost_center", r.message.cost_center);
                }
            }
        },
    });
}

/**
 * Resolve purchase user defaults (suspense account, purchaser validation).
 *
 * @param {Object} frm - The form object
 * @param {boolean} show_errors - If true, show validation errors to the user.
 *   Set to false on passive refresh to avoid spamming the user with repeated
 *   "not a purchaser" messages.
 */
function _resolve_purchase_user_defaults(frm, show_errors) {
    const purchaseUser =
        frm.doc.custom_purchase_user ||
        frm.doc.custom_requested_by_email ||
        frappe.session.user;

    if (!purchaseUser) return;

    frappe.call({
        method: "next_custom_app.next_custom_app.utils.payment_request_utils.get_purchase_user_defaults",
        args: {
            user: purchaseUser,
            currency: frm.doc.currency,
            company: frm.doc.company,
        },
        callback: function (r) {
            const result = r.message || {};

            if (!result.ok) {
                // Only clear the field if it exists on the form
                if (frm.fields_dict.custom_purchase_suspense_account) {
                    frm.set_value("custom_purchase_suspense_account", null);
                }
                // Only show error messages when explicitly requested
                // (e.g. on user change, not on every passive refresh)
                if (show_errors) {
                    frappe.msgprint({
                        title: __("Purchaser Validation"),
                        message:
                            result.message ||
                            __("Selected user is not a valid purchaser."),
                        indicator: "orange",
                    });
                }
                return;
            }

            if (result.user) {
                if (frm.fields_dict.custom_purchase_user && frm.doc.custom_purchase_user !== result.user) {
                    frm.set_value("custom_purchase_user", result.user);
                }
                if (frm.doc.custom_requested_by_email !== result.user) {
                    frm.set_value("custom_requested_by_email", result.user);
                }
            }

            if (result.suspense_account && frm.fields_dict.custom_purchase_suspense_account) {
                frm.set_value("custom_purchase_suspense_account", result.suspense_account);
            }
        },
    });
}
