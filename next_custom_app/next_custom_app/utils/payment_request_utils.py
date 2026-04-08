# Copyright (c) 2025, Nextcore Technologies and contributors
# For license information, please see license.txt

"""
Payment Request & Payment Entry utilities.

Business logic hooks for:
* Payment Request  – validate (set purchaser, resolve suspense account)
* Payment Entry    – validate (force Internal Transfer when linked to PR)
* User             – on_update (link receivable accounts to suspense)

Custom field *definitions* live in
:pymod:`next_custom_app.next_custom_app.custom_fields` (single source of truth).
"""

import frappe
from frappe import _


# ---------------------------------------------------------------------------
# Document-event hooks
# ---------------------------------------------------------------------------

def on_payment_request_validate(doc, method=None):
    """
    Validate hook for Payment Request.
    - Ensures payment_request_type is always "Outward"
    - Sets requested_by and email from current user if not already set
    - Copies project and cost_center from linked Purchase Order
    - Sets mode_of_payment to Cash if available and not already set
    """
    # Force payment_request_type to Outward
    doc.payment_request_type = "Outward"

    # Default purchase user to current session user
    if not doc.get("custom_purchase_user"):
        doc.custom_purchase_user = frappe.session.user

    # Keep legacy requested_by_email synced
    if doc.get("custom_purchase_user"):
        doc.custom_requested_by_email = doc.custom_purchase_user

    # Keep display name synced to selected purchase user
    doc.custom_requested_by = frappe.utils.get_fullname(
        doc.custom_purchase_user or frappe.session.user
    )

    # Set mode_of_payment to Cash if not set and Cash exists
    if not doc.get("mode_of_payment"):
        if frappe.db.exists("Mode of Payment", "Cash"):
            doc.mode_of_payment = "Cash"

    # Copy project and cost_center from Purchase Order if linked
    _copy_fields_from_po(doc)

    # Enforce purchaser user (requested_by_email) and resolve suspense account
    _ensure_purchase_user_and_suspense_account(doc)


def on_payment_entry_validate(doc, method=None):
    """
    If Payment Entry is created from Payment Request and that request has a
    purchase user, force internal transfer and populate accounts.

    The suspense account on the Payment Request is a **parent/group** account.
    We resolve the correct child account based on the Payment Entry currency.
    """
    payment_request_name = _get_payment_request_reference(doc)
    if not payment_request_name:
        return

    pr_fields = ["custom_purchase_user", "custom_requested_by_email", "company"]
    if _payment_request_has_field("custom_purchase_suspense_account"):
        pr_fields.append("custom_purchase_suspense_account")

    pr_data = frappe.db.get_value(
        "Payment Request", payment_request_name, pr_fields, as_dict=True
    )
    purchase_user = pr_data.get("custom_purchase_user") or pr_data.get(
        "custom_requested_by_email"
    )
    if not pr_data or not purchase_user:
        return

    # Determine the currency for resolving the child suspense account
    currency = (
        doc.get("paid_to_account_currency")
        or doc.get("target_exchange_rate_currency")
        or doc.get("payment_currency")
    )
    company = pr_data.get("company")

    # The suspense account stored on Payment Request is the parent/group account.
    # We always resolve the child account by currency.
    parent_suspense = pr_data.get("custom_purchase_suspense_account")
    if not parent_suspense:
        # Fallback: get parent suspense from User profile
        user_data = frappe.db.get_value(
            "User",
            purchase_user,
            ["custom_suspense_account"],
            as_dict=True,
        )
        parent_suspense = (user_data or {}).get("custom_suspense_account")

    suspense_account = _resolve_user_suspense_account(
        purchase_user=purchase_user,
        parent_suspense=parent_suspense,
        currency=currency,
        company=company,
    )

    if not suspense_account:
        frappe.throw(
            _("Payment Request {0} has no suspense account for currency {1}.").format(
                payment_request_name, currency or _("Not Set")
            )
        )

    paid_from_account = _get_company_cash_account(company)
    if not paid_from_account:
        frappe.throw(
            _("No default cash account found for company {0}.").format(
                company or ""
            )
        )

    doc.payment_type = "Internal Transfer"
    doc.paid_to = suspense_account
    doc.paid_from = paid_from_account


def on_user_update(doc, method=None):
    """
    Hook called when a User document is saved.
    If the user is a purchaser and has a suspense_account set,
    automatically link their receivable accounts to the suspense account.
    """
    if not doc.get("custom_is_purchaser") or not doc.get("custom_suspense_account"):
        return

    # Run the linking in the background to avoid slowing down user save
    frappe.enqueue(
        "next_custom_app.next_custom_app.utils.payment_request_utils.link_suspense_account_to_receivables",
        user_email=doc.name,
        queue="short",
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _copy_fields_from_po(doc):
    """
    Copy project and cost_center from the linked Purchase Order.
    Checks both procurement workflow source and standard reference fields.
    """
    po_name = None

    # Check procurement workflow source
    if (
        doc.get("procurement_source_doctype") == "Purchase Order"
        and doc.get("procurement_source_name")
    ):
        po_name = doc.procurement_source_name

    # Check standard reference_doctype / reference_name
    if (
        not po_name
        and doc.get("reference_doctype") == "Purchase Order"
        and doc.get("reference_name")
    ):
        po_name = doc.reference_name

    if not po_name:
        return

    po_data = frappe.db.get_value(
        "Purchase Order",
        po_name,
        ["project", "cost_center"],
        as_dict=True,
    )

    if not po_data:
        return

    if po_data.project and not doc.get("project"):
        doc.project = po_data.project

    if po_data.cost_center and not doc.get("cost_center"):
        doc.cost_center = po_data.cost_center


def _ensure_purchase_user_and_suspense_account(doc):
    """
    Ensure purchase user is a purchaser and set suspense account by payment currency.
    """
    purchase_user = (
        doc.get("custom_purchase_user")
        or doc.get("custom_requested_by_email")
        or frappe.session.user
    )
    doc.custom_purchase_user = purchase_user
    doc.custom_requested_by_email = purchase_user

    user_data = frappe.db.get_value(
        "User",
        purchase_user,
        ["enabled", "custom_is_purchaser", "custom_suspense_account"],
        as_dict=True,
    )

    if not user_data or not user_data.get("enabled"):
        frappe.throw(
            _("Selected request user {0} is disabled or does not exist.").format(
                purchase_user
            )
        )

    if not user_data.get("custom_is_purchaser"):
        frappe.throw(_("User {0} is not marked as Purchaser.").format(purchase_user))

    currency = doc.get("currency") or doc.get("party_account_currency")
    company = doc.get("company")
    suspense_account = _resolve_user_suspense_account(
        purchase_user=purchase_user,
        parent_suspense=user_data.get("custom_suspense_account"),
        currency=currency,
        company=company,
    )

    if not suspense_account:
        frappe.throw(
            _(
                "No suspense account could be resolved for purchaser {0} with currency {1}."
            ).format(purchase_user, currency or _("Not Set"))
        )

    # Safely set the suspense account field – it may not yet exist if
    # ``setup_all_custom_fields`` has not been run after the latest migration.
    if _payment_request_has_field("custom_purchase_suspense_account"):
        doc.custom_purchase_suspense_account = suspense_account
    else:
        frappe.logger().warning(
            "custom_purchase_suspense_account field not found on Payment Request. "
            "Run: bench --site <site> migrate  to create it."
        )


def _resolve_user_suspense_account(
    purchase_user, parent_suspense, currency=None, company=None
):
    """
    Resolve suspense account for a user by currency.

    The ``parent_suspense`` is always a **group** account. We look for a
    non-group child account under it that matches the requested currency
    (and company, if provided).

    If the configured account is NOT a group, return it directly when the
    currency matches.
    """
    if not parent_suspense:
        return None

    parent_data = frappe.db.get_value(
        "Account",
        parent_suspense,
        ["name", "account_currency", "is_group", "company"],
        as_dict=True,
    )
    if not parent_data:
        return None

    # If the configured account is NOT a group, use it directly when currency matches
    if not parent_data.is_group:
        if not currency or parent_data.account_currency == currency:
            return parent_data.name
        return None

    # Parent is a group — always look for a child account
    filters = {
        "is_group": 0,
        "parent_account": parent_suspense,
    }
    if currency:
        filters["account_currency"] = currency
    if company:
        filters["company"] = company

    child_match = frappe.db.get_value("Account", filters, "name")
    if child_match:
        return child_match

    # fallback: no matching child found
    return None


def _get_payment_request_reference(doc):
    """
    Get linked Payment Request name from Payment Entry.

    ERPNext's standard ``make_payment_entry`` from Payment Request sets:
      - ``reference_no`` = Payment Request name
      - ``references`` child table = Purchase Order / Purchase Invoice

    The procurement workflow sets:
      - ``procurement_source_doctype`` = "Payment Request"
      - ``procurement_source_name`` = Payment Request name

    We check all possible locations.
    """
    # 1. Explicit reference_doctype == "Payment Request"
    if doc.get("reference_doctype") == "Payment Request":
        if doc.get("reference_no"):
            return doc.reference_no
        if doc.get("reference_name"):
            return doc.reference_name

    # 2. reference_no set by ERPNext standard flow (verify it's a real Payment Request)
    if doc.get("reference_no"):
        if frappe.db.exists("Payment Request", doc.reference_no):
            return doc.reference_no

    # 3. Procurement workflow source fields
    if (
        doc.get("procurement_source_doctype") == "Payment Request"
        and doc.get("procurement_source_name")
    ):
        return doc.procurement_source_name

    # 4. References child table
    for ref in doc.get("references") or []:
        if ref.reference_doctype == "Payment Request" and ref.reference_name:
            return ref.reference_name

    return None


def _get_company_cash_account(company):
    """Resolve default company cash account."""
    if not company:
        return None

    default_cash_account = frappe.db.get_value(
        "Company", company, "default_cash_account"
    )
    if default_cash_account:
        return default_cash_account

    return frappe.db.get_value(
        "Account",
        {
            "company": company,
            "account_type": "Cash",
            "is_group": 0,
            "disabled": 0,
        },
        "name",
    )


def _payment_request_has_field(fieldname):
    """Safe check for field existence on Payment Request doctype."""
    try:
        return frappe.get_meta("Payment Request").has_field(fieldname)
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Whitelisted API methods
# ---------------------------------------------------------------------------

@frappe.whitelist()
def get_purchase_user_defaults(user=None, currency=None, company=None):
    """Return purchaser validation and resolved suspense account for a user."""
    user = user or frappe.session.user
    user_data = frappe.db.get_value(
        "User",
        user,
        ["enabled", "custom_is_purchaser", "custom_suspense_account"],
        as_dict=True,
    )
    if not user_data:
        return {"ok": False, "message": _("User not found.")}
    if not user_data.get("enabled"):
        return {"ok": False, "message": _("User is disabled.")}
    if not user_data.get("custom_is_purchaser"):
        return {"ok": False, "message": _("User is not marked as Purchaser.")}

    suspense_account = _resolve_user_suspense_account(
        purchase_user=user,
        parent_suspense=user_data.get("custom_suspense_account"),
        currency=currency,
        company=company,
    )

    if not suspense_account:
        return {
            "ok": False,
            "message": _(
                "No suspense account found for selected user and currency."
            ),
        }

    return {
        "ok": True,
        "user": user,
        "suspense_account": suspense_account,
    }


@frappe.whitelist()
def get_payment_entry_defaults_from_payment_request(payment_request, currency=None):
    """
    Return Payment Entry defaults derived from Payment Request purchaser config.

    The suspense account on the Payment Request is a **parent/group** account.
    We resolve the correct child account based on the provided currency.

    Args:
        payment_request: Payment Request name
        currency: Payment currency to resolve the child suspense account
    """
    if not payment_request:
        return {"ok": False}

    pr_fields = ["custom_purchase_user", "custom_requested_by_email", "company", "currency"]
    if _payment_request_has_field("custom_purchase_suspense_account"):
        pr_fields.append("custom_purchase_suspense_account")

    pr_data = frappe.db.get_value(
        "Payment Request", payment_request, pr_fields, as_dict=True
    )
    purchase_user = pr_data.get("custom_purchase_user") or pr_data.get(
        "custom_requested_by_email"
    )
    if not pr_data or not purchase_user:
        return {"ok": False}

    # Use provided currency, fall back to Payment Request currency
    resolve_currency = currency or pr_data.get("currency")

    # The suspense account stored on Payment Request is the parent/group account.
    # Always resolve the child account by currency.
    parent_suspense = pr_data.get("custom_purchase_suspense_account")
    if not parent_suspense:
        # Fallback: get parent suspense from User profile
        user_data = frappe.db.get_value(
            "User",
            purchase_user,
            ["custom_suspense_account"],
            as_dict=True,
        )
        parent_suspense = (user_data or {}).get("custom_suspense_account")

    suspense_account = _resolve_user_suspense_account(
        purchase_user=purchase_user,
        parent_suspense=parent_suspense,
        currency=resolve_currency,
        company=pr_data.get("company"),
    )

    if not suspense_account:
        return {
            "ok": False,
            "message": _(
                "No suspense account resolved for purchaser {0} with currency {1}."
            ).format(purchase_user, resolve_currency or _("Not Set")),
        }

    paid_from_account = _get_company_cash_account(pr_data.get("company"))
    if not paid_from_account:
        return {
            "ok": False,
            "message": _("No default cash account found for company {0}.").format(
                pr_data.get("company") or ""
            ),
        }

    return {
        "ok": True,
        "payment_type": "Internal Transfer",
        "paid_to": suspense_account,
        "paid_from": paid_from_account,
        "suspense_parent_account": parent_suspense,
    }


@frappe.whitelist()
def link_suspense_account_to_receivables(user_email=None):
    """
    For a given user (or all purchaser users), set the suspense_account as the
    parent_account on the user's receivable accounts.

    Args:
        user_email: Optional. If provided, only process this user.
                    If not provided, process all users with is_purchaser=1.

    Run: bench --site <site> execute next_custom_app.next_custom_app.utils.payment_request_utils.link_suspense_account_to_receivables
    """
    filters = {"enabled": 1}
    if user_email:
        filters["name"] = user_email
    else:
        filters["custom_is_purchaser"] = 1

    users = frappe.get_all(
        "User",
        filters=filters,
        fields=["name", "full_name", "custom_suspense_account"],
    )

    if not users:
        frappe.msgprint(
            _("No purchaser users found to process."), indicator="orange"
        )
        return []

    updated_accounts = []

    for user in users:
        suspense_account = user.get("custom_suspense_account")
        if not suspense_account:
            frappe.log_error(
                title="Suspense Account Missing",
                message=f"User {user.name} ({user.full_name}) has is_purchaser=1 but no suspense_account set.",
            )
            continue

        # Verify the suspense account exists
        if not frappe.db.exists("Account", suspense_account):
            frappe.log_error(
                title="Suspense Account Not Found",
                message=f"Suspense account '{suspense_account}' for user {user.name} does not exist.",
            )
            continue

        receivable_accounts = _get_user_receivable_accounts(user)

        for account_name in receivable_accounts:
            try:
                account_doc = frappe.get_doc("Account", account_name)
                if account_doc.parent_account != suspense_account:
                    old_parent = account_doc.parent_account
                    account_doc.parent_account = suspense_account
                    account_doc.flags.ignore_permissions = True
                    account_doc.save()
                    updated_accounts.append(
                        {
                            "account": account_name,
                            "user": user.name,
                            "old_parent": old_parent,
                            "new_parent": suspense_account,
                        }
                    )
                    frappe.logger().info(
                        f"Updated account {account_name}: parent_account changed from "
                        f"'{old_parent}' to '{suspense_account}' for user {user.name}"
                    )
            except Exception as e:
                frappe.log_error(
                    title="Account Parent Update Error",
                    message=f"Error updating parent_account for {account_name}: {str(e)}\n{frappe.get_traceback()}",
                )

    if updated_accounts:
        frappe.db.commit()
        frappe.msgprint(
            _(
                "Updated {0} receivable account(s) with suspense account as parent."
            ).format(len(updated_accounts)),
            indicator="green",
        )
    else:
        frappe.msgprint(
            _("No receivable accounts needed updating."),
            indicator="blue",
        )

    return updated_accounts


@frappe.whitelist()
def get_payment_request_links(payment_request_name):
    """
    Return linked Payment Entries for a given Payment Request.

    Payment Entries can be linked to a Payment Request via:
      1. ``reference_no`` field (ERPNext standard flow sets this to PR name)
      2. ``references`` child table with reference_doctype = "Payment Request"
      3. ``procurement_source_doctype`` / ``procurement_source_name`` custom fields

    Returns:
        dict: {"payment_entries": [{"name": "PE-001", "docstatus": 1, ...}, ...]}
    """
    if not payment_request_name:
        return {"payment_entries": []}

    pe_names = set()

    # 1. Check reference_no
    entries_by_ref = frappe.get_all(
        "Payment Entry",
        filters={
            "reference_no": payment_request_name,
            "docstatus": ["!=", 2],
        },
        fields=["name", "docstatus", "payment_type", "paid_amount", "posting_date", "party_name"],
    )
    for pe in entries_by_ref:
        pe_names.add(pe.name)

    # 2. Check references child table
    ref_rows = frappe.get_all(
        "Payment Entry Reference",
        filters={
            "reference_doctype": "Payment Request",
            "reference_name": payment_request_name,
            "docstatus": ["!=", 2],
        },
        fields=["parent"],
    )
    for row in ref_rows:
        pe_names.add(row.parent)

    # 3. Check procurement_source fields (if they exist on Payment Entry)
    if _doctype_has_field("Payment Entry", "procurement_source_doctype"):
        entries_by_source = frappe.get_all(
            "Payment Entry",
            filters={
                "procurement_source_doctype": "Payment Request",
                "procurement_source_name": payment_request_name,
                "docstatus": ["!=", 2],
            },
            fields=["name"],
        )
        for pe in entries_by_source:
            pe_names.add(pe.name)

    if not pe_names:
        return {"payment_entries": []}

    # Fetch full details for all found Payment Entries
    payment_entries = frappe.get_all(
        "Payment Entry",
        filters={"name": ["in", list(pe_names)]},
        fields=[
            "name", "docstatus", "payment_type", "paid_amount",
            "posting_date", "party_name", "party_type", "party",
            "paid_from", "paid_to", "status",
        ],
        order_by="posting_date desc",
    )

    return {"payment_entries": payment_entries}


@frappe.whitelist()
def get_payment_entry_links(payment_entry_name):
    """
    Return the linked Payment Request for a given Payment Entry.

    Checks:
      1. ``reference_no`` field
      2. ``references`` child table
      3. ``procurement_source_doctype`` / ``procurement_source_name`` custom fields

    Returns:
        dict: {"payment_request": {"name": "PR-001", ...} or None,
               "purchase_order": {"name": "PO-001", ...} or None}
    """
    if not payment_entry_name:
        return {"payment_request": None, "purchase_order": None}

    pe_doc = frappe.get_doc("Payment Entry", payment_entry_name)
    pr_name = _get_payment_request_reference(pe_doc)

    result = {"payment_request": None, "purchase_order": None}

    if pr_name:
        pr_data = frappe.db.get_value(
            "Payment Request",
            pr_name,
            [
                "name", "docstatus", "grand_total", "status",
                "reference_doctype", "reference_name",
                "party_type", "party", "payment_request_type",
            ],
            as_dict=True,
        )
        if pr_data:
            result["payment_request"] = pr_data

            # If the Payment Request references a Purchase Order, include it
            if pr_data.get("reference_doctype") == "Purchase Order" and pr_data.get("reference_name"):
                po_data = frappe.db.get_value(
                    "Purchase Order",
                    pr_data.reference_name,
                    ["name", "docstatus", "grand_total", "status", "supplier", "supplier_name"],
                    as_dict=True,
                )
                if po_data:
                    result["purchase_order"] = po_data

    return result


def _doctype_has_field(doctype, fieldname):
    """Safe check for field existence on any doctype."""
    try:
        return frappe.get_meta(doctype).has_field(fieldname)
    except Exception:
        return False


def _get_user_receivable_accounts(user):
    """
    Get receivable accounts associated with a user.
    Looks for accounts of type 'Receivable' that match the user's full name
    or are linked via employee/user references.
    """
    accounts = []

    # Strategy 1: Find accounts where account_name matches user's full name
    if user.get("full_name"):
        matching = frappe.get_all(
            "Account",
            filters={
                "account_type": "Receivable",
                "account_name": ["like", f"%{user.full_name}%"],
                "is_group": 0,
            },
            pluck="name",
        )
        accounts.extend(matching)

    # Strategy 2: Find accounts where the account name contains the user email prefix
    email_prefix = (
        user.name.split("@")[0] if "@" in user.name else user.name
    )
    if email_prefix:
        matching = frappe.get_all(
            "Account",
            filters={
                "account_type": "Receivable",
                "account_name": ["like", f"%{email_prefix}%"],
                "is_group": 0,
            },
            pluck="name",
        )
        for acc in matching:
            if acc not in accounts:
                accounts.append(acc)

    return accounts
