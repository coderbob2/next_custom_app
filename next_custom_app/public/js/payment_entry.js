// Payment Entry Customizations
// If created from a Payment Request, force supplier payment flow and
// resolve paid_to by destination (Suspense vs Supplier Payable).
// Document links and smart buttons are handled by procurement_custom_tabs.js.

frappe.ui.form.on("Payment Entry", {
    refresh(frm) {
        _apply_payment_request_purchase_defaults(frm);
    },

    onload(frm) {
        // Apply defaults on load (important for newly created docs)
        if (frm.is_new()) {
            // Use a short delay to ensure ERPNext's own setup has completed
            // before we override the values.
            setTimeout(() => {
                _apply_payment_request_purchase_defaults(frm, true);
            }, 500);
        }
    },

    references_add(frm) {
        _apply_payment_request_purchase_defaults(frm);
    },

    references_remove(frm) {
        _apply_payment_request_purchase_defaults(frm);
    },

    paid_to_account_currency(frm) {
        // Re-resolve when currency changes
        _apply_payment_request_purchase_defaults(frm);
    },
});

/**
 * Apply Payment Request purchase defaults to the Payment Entry.
 *
 * @param {Object} frm - The form object
 * @param {boolean} force - If true, skip the duplicate-call prevention
 */
function _apply_payment_request_purchase_defaults(frm, force) {
    const paymentRequest = _get_payment_request_reference(frm);
    if (!paymentRequest) return;

    // Prevent duplicate calls for the same payment request (unless forced)
    if (!force && frm._pr_defaults_loading === paymentRequest) return;
    frm._pr_defaults_loading = paymentRequest;

    // Determine the currency to resolve the correct child suspense account
    const currency =
        frm.doc.paid_to_account_currency ||
        frm.doc.payment_currency ||
        frm.doc.company_currency;

    frappe.call({
        method: "next_custom_app.next_custom_app.utils.payment_request_utils.get_payment_entry_defaults_from_payment_request",
        args: {
            payment_request: paymentRequest,
            currency: currency,
        },
        callback: function (r) {
            frm._pr_defaults_loading = null;
            const result = r.message || {};
            if (!result.ok) {
                console.warn(
                    "Payment Entry defaults from Payment Request failed:",
                    result.message || "Unknown error"
                );
                return;
            }

            // Keep ERPNext standard behavior for supplier destination
            if (!result.apply_customization) {
                return;
            }

            // Suspense destination: force internal transfer and account override
            frm.set_value("payment_type", result.payment_type || "Internal Transfer").then(() => {
                frm.set_df_property("payment_type", "read_only", 1);

                // Set the resolved child suspense account as paid_to
                if (result.paid_to) {
                    frm.set_value("paid_to", result.paid_to);
                }
                // Set the company cash account as paid_from
                if (result.paid_from) {
                    frm.set_value("paid_from", result.paid_from);
                }

                // Expand the accounts section so it's visible
                _expand_accounts_section(frm);

                // Suspense destination: filter paid_to to suspense children.
                if (result.suspense_parent_account) {
                    frm.set_query("paid_to", function () {
                        return {
                            filters: {
                                parent_account: result.suspense_parent_account,
                                is_group: 0,
                                company: frm.doc.company,
                            },
                        };
                    });
                }
            });
        },
        error: function () {
            frm._pr_defaults_loading = null;
        },
    });
}

/**
 * Expand the Accounts section so it's not collapsed.
 */
function _expand_accounts_section(frm) {
    // Try to find and expand the accounts section
    // In ERPNext Payment Entry, the accounts section contains paid_from and paid_to
    if (frm.fields_dict.paid_from && frm.fields_dict.paid_from.section) {
        const section = frm.fields_dict.paid_from.section;
        if (section && section.collapse) {
            section.collapse(false);
        }
    }

    // Also try the section_break approach
    const sections = frm.layout.sections || [];
    for (const section of sections) {
        // Find the section that contains paid_from or paid_to
        if (section.body) {
            const hasPaidFrom = $(section.body).find('[data-fieldname="paid_from"]').length > 0;
            const hasPaidTo = $(section.body).find('[data-fieldname="paid_to"]').length > 0;
            if (hasPaidFrom || hasPaidTo) {
                if (section.is_collapsed && section.collapse) {
                    section.collapse(false);
                }
                // Also try setting the section as not collapsible
                if (section.head) {
                    $(section.head).click();
                    // Only click if it's collapsed
                    if (section.is_collapsed) {
                        $(section.head).click();
                    }
                }
                break;
            }
        }
    }
}

/**
 * Find the Payment Request name linked to this Payment Entry.
 *
 * ERPNext's standard `make_payment_entry` from Payment Request sets:
 *   - `reference_no` = Payment Request name (e.g. "ACC-PRQ-2025-00001")
 *   - `references` child table = Purchase Order / Purchase Invoice (NOT Payment Request)
 *
 * The procurement workflow sets:
 *   - `procurement_source_doctype` = "Payment Request"
 *   - `procurement_source_name` = Payment Request name
 *
 * We check all possible locations.
 */
function _get_payment_request_reference(frm) {
    // 1. Check procurement workflow source fields
    if (frm.doc.procurement_source_doctype === "Payment Request" && frm.doc.procurement_source_name) {
        return frm.doc.procurement_source_name;
    }

    // 2. Check reference_no — ERPNext standard sets this to the Payment Request name
    //    The server-side API will validate if it's actually a Payment Request
    if (frm.doc.reference_no) {
        return frm.doc.reference_no;
    }

    // 3. Check references child table for Payment Request rows
    const refs = frm.doc.references || [];
    for (const row of refs) {
        if (row.reference_doctype === "Payment Request" && row.reference_name) {
            return row.reference_name;
        }
    }

    return null;
}
