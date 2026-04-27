# Copyright (c) 2025, Nextcore Technologies and contributors
# For license information, please see license.txt

"""
Centralized Custom Fields Definition
=====================================
ALL custom field definitions for the Next Custom App live here.
This module is the single source of truth for custom fields and is called
from both ``after_install`` and ``after_migrate`` hooks.

To add new custom fields, define them in the appropriate helper and
register the helper inside :func:`setup_all_custom_fields`.

Run manually:
    bench --site <site> execute next_custom_app.next_custom_app.custom_fields.setup_all_custom_fields
"""

import frappe
from frappe import _


# ---------------------------------------------------------------------------
# Procurement doctypes that receive workflow tracking fields
# ---------------------------------------------------------------------------
PROCUREMENT_DOCTYPES = [
    "Material Request",
    "Purchase Requisition",
    "Request for Quotation",
    "Supplier Quotation",
    "Purchase Order",
    "Purchase Receipt",
    "Purchase Invoice",
    "Stock Entry",
    "Payment Request",
    "Payment Entry",
]


# ---------------------------------------------------------------------------
# Field definitions
# ---------------------------------------------------------------------------

def _get_procurement_workflow_fields():
    """
    Return custom field definitions for procurement workflow tracking.
    These fields are added to every doctype listed in ``PROCUREMENT_DOCTYPES``.
    """
    has_doc_link = frappe.db.exists("DocType", "Procurement Document Link")

    if not has_doc_link:
        frappe.log_error(
            title="Procurement Document Link Not Found",
            message="The Procurement Document Link doctype was not found. Table field will be skipped.",
        )

    custom_fields = {}

    for doctype in PROCUREMENT_DOCTYPES:
        if not frappe.db.exists("DocType", doctype):
            frappe.log_error(
                title=f"DocType {doctype} does not exist",
                message=f"Skipping custom field creation for {doctype}",
            )
            continue

        meta = frappe.get_meta(doctype)

        custom_fields[doctype] = [
            {
                "fieldname": "procurement_section",
                "label": "Procurement Workflow",
                "fieldtype": "Section Break",
                "insert_after": "amended_from",
                "collapsible": 0,
            },
            {
                "fieldname": "procurement_source_doctype",
                "label": "Source DocType",
                "fieldtype": "Link",
                "options": "DocType",
                "insert_after": "procurement_section",
                "read_only": 0,
                "no_copy": 1,
                "print_hide": 1,
                "in_list_view": 0,
                "in_standard_filter": 0,
            },
            {
                "fieldname": "procurement_source_name",
                "label": "Source Document",
                "fieldtype": "Dynamic Link",
                "options": "procurement_source_doctype",
                "insert_after": "procurement_source_doctype",
                "read_only": 0,
                "no_copy": 1,
                "print_hide": 1,
                "in_list_view": 0,
                "in_standard_filter": 0,
            },
            {
                "fieldname": "procurement_column_break",
                "fieldtype": "Column Break",
                "insert_after": "procurement_source_name",
            },
        ]

        if has_doc_link:
            custom_fields[doctype].append(
                {
                    "fieldname": "procurement_links",
                    "label": "Child Documents",
                    "fieldtype": "Table",
                    "options": "Procurement Document Link",
                    "insert_after": "procurement_column_break",
                    "read_only": 1,
                    "no_copy": 1,
                    "print_hide": 1,
                    "hidden": 1,
                }
            )
        else:
            custom_fields[doctype].append(
                {
                    "fieldname": "procurement_links_note",
                    "label": "Document Links",
                    "fieldtype": "Small Text",
                    "insert_after": "procurement_column_break",
                    "read_only": 1,
                    "no_copy": 1,
                    "print_hide": 1,
                    "default": "Run setup_all_custom_fields() to enable document tracking",
                    "hidden": 1,
                }
            )

        # Purchase Requisition: ensure header-level accounting dimensions exist.
        # Some deployments store project/cost_center only on Material Request header
        # and expect those values to be copied to the next document at doctype level.
        if doctype == "Purchase Requisition":
            if not meta.has_field("project"):
                custom_fields[doctype].append(
                    {
                        "fieldname": "project",
                        "label": "Project",
                        "fieldtype": "Link",
                        "options": "Project",
                        "insert_after": "company",
                        "in_standard_filter": 1,
                    }
                )

            if not meta.has_field("cost_center"):
                custom_fields[doctype].append(
                    {
                        "fieldname": "cost_center",
                        "label": "Cost Center",
                        "fieldtype": "Link",
                        "options": "Cost Center",
                        "insert_after": "project",
                        "in_standard_filter": 1,
                    }
                )

    return custom_fields


def _get_payment_request_fields():
    """
    Return custom field definitions for the **Payment Request** doctype.
    Fields: custom_procurement_details_section, custom_requested_by,
            custom_purchase_user, custom_procurement_col_break,
            custom_requested_by_email, custom_purchase_suspense_account,
            custom_payment_destination.

    Placed after ``reference_name`` (Party Details section) so they are
    prominently visible near the top of the form.
    """
    fields = [
            # Ensure Company exists (some migrated sites may miss it in Payment Request)
            {
                "fieldname": "company",
                "label": "Company",
                "fieldtype": "Link",
                "options": "Company",
                "insert_after": "reference_name",
                "reqd": 1,
                "in_standard_filter": 1,
                "description": "Company for this payment request",
            },
            # ── Section: Procurement Details ──
            {
                "fieldname": "custom_procurement_details_section",
                "label": "Procurement Details",
                "fieldtype": "Section Break",
                "insert_after": "reference_name",
                "collapsible": 0,
            },
            {
                "fieldname": "custom_payment_destination",
                "label": "Payment Destination",
                "fieldtype": "Select",
                "options": "Suspense\nPayment for Supplier",
                "insert_after": "custom_procurement_details_section",
                "default": "Suspense",
                "reqd": 1,
                "description": "Choose whether payment is posted to purchaser suspense or directly to supplier payable account",
            },
            {
                "fieldname": "custom_requested_by",
                "label": "Requested By",
                "fieldtype": "Data",
                "insert_after": "custom_payment_destination",
                "hidden": 0,
                "read_only": 1,
                "no_copy": 0,
                "print_hide": 0,
                "in_list_view": 0,
                "in_standard_filter": 1,
                "depends_on": "eval:doc.custom_payment_destination=='Suspense'",
                "description": "Full name of the user who created this request",
            },
            {
                "fieldname": "custom_purchase_user",
                "label": "Purchase User",
                "fieldtype": "Link",
                "options": "User",
                "insert_after": "custom_requested_by",
                "hidden": 0,
                "read_only": 0,
                "in_standard_filter": 1,
                "depends_on": "eval:doc.custom_payment_destination=='Suspense'",
                "mandatory_depends_on": "eval:doc.custom_payment_destination=='Suspense'",
                "description": "Purchaser user for this payment request",
            },
            {
                "fieldname": "custom_procurement_col_break",
                "fieldtype": "Column Break",
                "insert_after": "custom_purchase_user",
            },
            {
                "fieldname": "custom_requested_by_email",
                "label": "Requested By (Email)",
                "fieldtype": "Data",
                "options": "Email",
                "insert_after": "custom_procurement_col_break",
                "hidden": 0,
                "read_only": 1,
                "no_copy": 0,
                "print_hide": 0,
                "in_list_view": 0,
                "in_standard_filter": 0,
                "depends_on": "eval:doc.custom_payment_destination=='Suspense'",
                "description": "Email of the user who created this request",
            },
            {
                "fieldname": "custom_purchase_suspense_account",
                "label": "Suspense Account",
                "fieldtype": "Link",
                "options": "Account",
                "insert_after": "custom_requested_by_email",
                "hidden": 0,
                "read_only": 1,
                "depends_on": "eval:doc.custom_payment_destination=='Suspense' && doc.custom_purchase_user",
                "description": "Auto-resolved suspense account for purchase user and currency",
            },
        ]

    # If Payment Request already has a core/company field, don't try to create a duplicate custom field
    try:
        if frappe.get_meta("Payment Request").has_field("company"):
            fields = [f for f in fields if f.get("fieldname") != "company"]
    except Exception:
        pass

    return {
        "Payment Request": fields
    }


def _get_user_fields():
    """
    Return custom field definitions for the **User** doctype.
    Fields: custom_procurement_section, custom_is_purchaser,
            custom_procurement_col_break, custom_suspense_account.
    """
    return {
        "User": [
            {
                "fieldname": "custom_procurement_section",
                "label": "Procurement Settings",
                "fieldtype": "Section Break",
                "insert_after": "thread_notify",
                "collapsible": 1,
            },
            {
                "fieldname": "custom_is_purchaser",
                "label": "Is Purchaser",
                "fieldtype": "Check",
                "insert_after": "custom_procurement_section",
                "default": "0",
                "description": "Check this if the user is a purchaser in the procurement workflow",
            },
            {
                "fieldname": "custom_procurement_col_break",
                "fieldtype": "Column Break",
                "insert_after": "custom_is_purchaser",
            },
            {
                "fieldname": "custom_suspense_account",
                "label": "Suspense Parent Account",
                "fieldtype": "Link",
                "options": "Account",
                "insert_after": "custom_procurement_col_break",
                "depends_on": "eval:doc.custom_is_purchaser==1",
                "mandatory_depends_on": "eval:doc.custom_is_purchaser==1",
                "description": "Parent suspense account used for purchaser-specific suspense accounts",
            },
        ]
    }


# ---------------------------------------------------------------------------
# Public API – called from hooks (after_install / after_migrate)
# ---------------------------------------------------------------------------

def setup_all_custom_fields():
    """
    Create / update **all** custom fields defined by this app.

    This is the single entry-point called from:
    * ``after_install``
    * ``after_migrate``

    It is safe to call repeatedly – existing fields are updated, not duplicated.
    """
    from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

    all_fields = {}

    # 1. Procurement workflow fields (on all procurement doctypes including
    #    Payment Request and Payment Entry – adds procurement_source_doctype,
    #    procurement_source_name, procurement_links, etc.)
    all_fields.update(_get_procurement_workflow_fields())

    # 2. Payment Request additional fields (purchaser details, suspense account)
    #    IMPORTANT: Merge with existing Payment Request fields instead of
    #    overwriting, so that procurement workflow fields are preserved.
    pr_extra_fields = _get_payment_request_fields()
    for dt, fields in pr_extra_fields.items():
        if dt in all_fields:
            all_fields[dt].extend(fields)
        else:
            all_fields[dt] = fields

    # 3. User fields
    all_fields.update(_get_user_fields())

    try:
        create_custom_fields(all_fields, update=True)
        frappe.db.commit()

        # Clear meta cache so has_field() picks up new fields immediately
        for dt in all_fields:
            frappe.clear_cache(doctype=dt)

        frappe.msgprint(
            _("All custom fields for Next Custom App created / updated successfully!"),
            indicator="green",
        )
        return True
    except Exception as e:
        frappe.log_error(
            title="Custom Fields Setup Error",
            message=f"Error creating custom fields: {str(e)}\n{frappe.get_traceback()}",
        )
        frappe.msgprint(
            _("Error setting up custom fields: {0}").format(str(e)),
            indicator="red",
        )
        return False
