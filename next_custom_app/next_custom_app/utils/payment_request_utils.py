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
    - Copies company, project and cost_center from linked Purchase Order
    - Sets mode_of_payment to Cash if available and not already set
    """
    # Force payment_request_type to Outward
    doc.payment_request_type = "Outward"

    # Default destination to Suspense when not explicitly selected
    if not doc.get("custom_payment_destination"):
        doc.custom_payment_destination = "Suspense"

    destination = doc.get("custom_payment_destination") or "Suspense"

    # For Suspense destination we require/maintain purchaser fields.
    # For Supplier destination we keep these optional and do not enforce.
    if destination == "Suspense":
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

    # Enforce purchaser user and suspense account only for Suspense destination
    if destination == "Suspense":
        _ensure_purchase_user_and_suspense_account(doc)


def on_payment_entry_validate(doc, method=None):
    """
    If Payment Entry is created from Payment Request and destination is Suspense,
    force internal transfer and populate suspense/cash accounts.

    If destination is Payment for Supplier, do not override ERPNext defaults.

    The suspense account on the Payment Request may be either a parent/group
    account or a direct child account. We resolve the correct child account
    based on the Payment Entry currency.
    """
    try:
        _log_payment_entry_debug("PE_VALIDATE_START", doc)

        payment_request_name = _get_payment_request_reference(doc)
        _log_payment_entry_debug("PE_VALIDATE_REF", doc, {
            "payment_request_name": payment_request_name,
        })

        if not payment_request_name:
            _log_payment_entry_debug("PE_VALIDATE_NO_PR", doc)
            return

        pr_fields = [
            "custom_purchase_user", "custom_requested_by_email",
            "company", "currency", "reference_doctype", "reference_name",
            "custom_payment_destination", "grand_total", "outstanding_amount",
        ]
        if _payment_request_has_field("custom_purchase_suspense_account"):
            pr_fields.append("custom_purchase_suspense_account")

        existing_pr_fields = {df.fieldname for df in frappe.get_meta("Payment Request").fields}
        safe_pr_fields = [f for f in pr_fields if f in existing_pr_fields]

        pr_data = frappe.db.get_value(
            "Payment Request", payment_request_name, safe_pr_fields, as_dict=True
        )
        if not pr_data:
            return

        _ensure_payment_request_reference(doc, payment_request_name)

        payment_destination = (pr_data.get("custom_payment_destination") or "Suspense").strip()
        if payment_destination.lower() not in {"suspense", "internal transfer", "internal_transfer"}:
            supplier = _resolve_supplier_from_pr_data(pr_data)
            amount = _resolve_amount_from_pr_data(pr_data)

            if supplier:
                if not doc.get("party_type"):
                    doc.party_type = "Supplier"
                if not doc.get("party"):
                    doc.party = supplier

            if amount:
                if not doc.get("paid_amount"):
                    doc.paid_amount = amount
                if not doc.get("received_amount"):
                    doc.received_amount = amount

            _validate_payment_entry_total_against_request(doc, payment_request_name, pr_data)
            return

        purchase_user = pr_data.get("custom_purchase_user") or pr_data.get("custom_requested_by_email")
        if not purchase_user:
            frappe.throw(
                _("Payment Request {0} requires a Purchase User for suspense destination.").format(
                    payment_request_name
                )
            )

        currency = (
            doc.get("paid_to_account_currency")
            or doc.get("paid_from_account_currency")
            or doc.get("payment_currency")
            or pr_data.get("currency")
        )

        company = (
            pr_data.get("company")
            or doc.get("company")
            or _get_company_from_reference(pr_data)
        )

        user_data = frappe.db.get_value(
            "User",
            purchase_user,
            ["custom_suspense_account"],
            as_dict=True,
        )
        parent_suspense = (user_data or {}).get("custom_suspense_account")

        if not parent_suspense:
            parent_suspense = pr_data.get("custom_purchase_suspense_account")

        paid_to_account = _resolve_user_suspense_account(
            purchase_user=purchase_user,
            parent_suspense=parent_suspense,
            currency=currency,
            company=company,
        )

        if not paid_to_account:
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
        doc.paid_to = paid_to_account
        doc.paid_from = paid_from_account

        _set_payment_entry_account_currencies(doc)
        _validate_payment_entry_total_against_request(doc, payment_request_name, pr_data)

        frappe.logger().info(
            "PR->PE Suspense mapping: pr=%s pe=%s paid_from=%s (%s) paid_to=%s (%s)",
            payment_request_name,
            doc.get("name") or "NEW",
            doc.get("paid_from"),
            doc.get("paid_from_account_currency"),
            doc.get("paid_to"),
            doc.get("paid_to_account_currency"),
        )
    except Exception:
        frappe.log_error(
            title="Payment Entry Validate Error",
            message=frappe.get_traceback(),
        )
        raise


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

def _log_payment_entry_debug(stage, doc, extra=None):
    """Structured debug logs for Payment Entry save flow."""
    payload = {
        "stage": stage,
        "payment_entry": doc.get("name") or "NEW",
        "payment_type": doc.get("payment_type"),
        "party_type": doc.get("party_type"),
        "party": doc.get("party"),
        "paid_from": doc.get("paid_from"),
        "paid_to": doc.get("paid_to"),
        "paid_from_account_currency": doc.get("paid_from_account_currency"),
        "paid_to_account_currency": doc.get("paid_to_account_currency"),
        "reference_doctype": doc.get("reference_doctype"),
        "reference_no": doc.get("reference_no"),
        "reference_name": doc.get("reference_name"),
        "procurement_source_doctype": doc.get("procurement_source_doctype"),
        "procurement_source_name": doc.get("procurement_source_name"),
    }
    if extra:
        payload.update(extra)
    frappe.logger().info("PE_DEBUG %s", frappe.as_json(payload))


def _copy_fields_from_po(doc):
    """
    Copy company, project and cost_center from the linked Purchase Order.
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
        ["company", "project", "cost_center"],
        as_dict=True,
    )

    if not po_data:
        return

    if po_data.company and not doc.get("company"):
        doc.company = po_data.company

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

    # 4. References child table direct PR row
    for ref in doc.get("references") or []:
        if ref.reference_doctype == "Payment Request" and ref.reference_name:
            return ref.reference_name

    # 5. References row indirect PR link (common in standard PE rows)
    for ref in doc.get("references") or []:
        pr = getattr(ref, "payment_request", None)
        if pr and frappe.db.exists("Payment Request", pr):
            return pr

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


def _resolve_supplier_from_pr_data(pr_data):
    """Resolve supplier code from Payment Request-like data."""
    if not pr_data:
        return None

    if pr_data.get("party_type") == "Supplier" and pr_data.get("party"):
        return pr_data.get("party")

    ref_dt = pr_data.get("reference_doctype")
    ref_dn = pr_data.get("reference_name")
    if ref_dt in {"Purchase Order", "Purchase Invoice", "Purchase Receipt"} and ref_dn:
        try:
            return frappe.db.get_value(ref_dt, ref_dn, "supplier")
        except Exception:
            return None

    return None


def _resolve_amount_from_pr_data(pr_data):
    """Resolve best payment amount from Payment Request-like data."""
    if not pr_data:
        return None
    return (
        pr_data.get("outstanding_amount")
        or pr_data.get("grand_total")
        or pr_data.get("paid_amount")
        or pr_data.get("received_amount")
    )


def _get_company_from_reference(pr_data):
    """
    Resolve company from the Payment Request's reference document
    (e.g. Purchase Order, Purchase Invoice).
    """
    ref_dt = pr_data.get("reference_doctype") if pr_data else None
    ref_dn = pr_data.get("reference_name") if pr_data else None
    if not ref_dt or not ref_dn:
        return None
    try:
        return frappe.db.get_value(ref_dt, ref_dn, "company")
    except Exception:
        return None


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
    Return Payment Entry defaults derived from Payment Request destination config.

    If destination is Payment for Supplier, return apply_customization=False so
    ERPNext standard payment creation behavior remains untouched.

    Args:
        payment_request: Payment Request name
        currency: Payment currency to resolve the child suspense account
    """
    try:
        if not payment_request:
            return {"ok": False}

        # Validate that the payment_request actually exists
        if not frappe.db.exists("Payment Request", payment_request):
            return {"ok": False}

        pr_fields = [
            "custom_purchase_user", "custom_requested_by_email",
            "company", "currency", "reference_doctype", "reference_name",
            "custom_payment_destination", "party_type", "party", "grand_total",
            "outstanding_amount",
        ]
        if _payment_request_has_field("custom_purchase_suspense_account"):
            pr_fields.append("custom_purchase_suspense_account")

        pr_data = frappe.db.get_value(
            "Payment Request", payment_request, pr_fields, as_dict=True
        )
        if not pr_data:
            return {"ok": False}

        payment_destination = (pr_data.get("custom_payment_destination") or "Suspense").strip()
        if payment_destination.lower() not in {"suspense", "internal transfer", "internal_transfer"}:
            supplier = _resolve_supplier_from_pr_data(pr_data)
            amount = _resolve_amount_from_pr_data(pr_data)
            return {
                "ok": True,
                "apply_customization": False,
                "payment_destination": payment_destination,
                "supplier": supplier,
                "amount": amount,
            }

        purchase_user = pr_data.get("custom_purchase_user") or pr_data.get("custom_requested_by_email")
        if not purchase_user:
            return {
                "ok": False,
                "message": _("Payment Request requires a Purchase User for suspense destination."),
            }

        # Use provided currency, fall back to Payment Request currency
        resolve_currency = currency or pr_data.get("currency")

        # Resolve company: PR → reference document (PO/PI)
        company = pr_data.get("company") or _get_company_from_reference(pr_data)

        # Always start from the User's parent suspense account so that
        # currency-based resolution works correctly.
        user_data = frappe.db.get_value(
            "User",
            purchase_user,
            ["custom_suspense_account"],
            as_dict=True,
        )
        parent_suspense = (user_data or {}).get("custom_suspense_account")

        # If no parent suspense from user, fall back to the PR field
        if not parent_suspense:
            parent_suspense = pr_data.get("custom_purchase_suspense_account")

        paid_to_account = _resolve_user_suspense_account(
            purchase_user=purchase_user,
            parent_suspense=parent_suspense,
            currency=resolve_currency,
            company=company,
        )

        if not paid_to_account:
            return {
                "ok": False,
                "message": _(
                    "No suspense account resolved for purchaser {0} with currency {1}."
                ).format(purchase_user, resolve_currency or _("Not Set")),
            }

        paid_from_account = _get_company_cash_account(company)
        if not paid_from_account:
            return {
                "ok": False,
                "message": _("No default cash account found for company {0}.").format(
                    company or ""
                ),
            }

        return {
            "ok": True,
            "apply_customization": True,
            "payment_type": "Internal Transfer",
            "payment_destination": payment_destination,
            "paid_to": paid_to_account,
            "paid_from": paid_from_account,
            "suspense_parent_account": parent_suspense,
        }
    except Exception as e:
        frappe.log_error(
            title="Payment Entry Defaults API Error",
            message=(
                f"Error: {repr(e)}\n"
                f"Payment Request: {payment_request}\n"
                f"Currency: {currency}\n\n"
                f"Traceback:\n{frappe.get_traceback()}"
            ),
        )
        return {
            "ok": False,
            "message": _("Failed to resolve Payment Entry defaults. Check Error Log for details."),
            "error": repr(e),
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


def _ensure_payment_request_reference(doc, payment_request_name):
    """Ensure Payment Entry keeps explicit link to Payment Request."""
    if not payment_request_name:
        return

    if doc.meta.has_field("reference_no") and not doc.get("reference_no"):
        doc.reference_no = payment_request_name

    if doc.meta.has_field("reference_doctype") and not doc.get("reference_doctype"):
        doc.reference_doctype = "Payment Request"

    if doc.meta.has_field("reference_name") and not doc.get("reference_name"):
        doc.reference_name = payment_request_name

    if doc.meta.has_field("references"):
        has_pr_ref = False
        for row in doc.get("references") or []:
            if row.reference_doctype == "Payment Request" and row.reference_name == payment_request_name:
                has_pr_ref = True
                break

        if not has_pr_ref:
            doc.append("references", {
                "reference_doctype": "Payment Request",
                "reference_name": payment_request_name,
                "allocated_amount": doc.get("paid_amount") or doc.get("received_amount") or 0,
                "total_amount": doc.get("paid_amount") or doc.get("received_amount") or 0,
                "outstanding_amount": doc.get("paid_amount") or doc.get("received_amount") or 0,
            })


def _set_payment_entry_account_currencies(doc):
    """Populate account currency fields required by Payment Entry validation."""
    if doc.get("paid_from") and (not doc.get("paid_from_account_currency")):
        doc.paid_from_account_currency = frappe.db.get_value("Account", doc.paid_from, "account_currency")

    if doc.get("paid_to") and (not doc.get("paid_to_account_currency")):
        doc.paid_to_account_currency = frappe.db.get_value("Account", doc.paid_to, "account_currency")


def _get_payment_request_limit_amount(pr_data):
    """Resolve maximum payable amount from Payment Request data."""
    if not pr_data:
        return 0

    for key in ("outstanding_amount", "grand_total"):
        value = pr_data.get(key)
        if value is not None:
            try:
                return abs(float(value))
            except Exception:
                continue
    return 0


def _get_existing_payment_entry_total(payment_request_name, current_payment_entry=None):
    """Get sum of submitted/draft Payment Entries linked to a Payment Request, excluding current doc."""
    if not payment_request_name:
        return 0

    pe_names = set()

    rows = frappe.get_all(
        "Payment Entry",
        filters={"reference_no": payment_request_name, "docstatus": ["!=", 2]},
        fields=["name"],
    )
    for row in rows:
        pe_names.add(row.name)

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

    if _doctype_has_field("Payment Entry", "procurement_source_doctype"):
        source_rows = frappe.get_all(
            "Payment Entry",
            filters={
                "procurement_source_doctype": "Payment Request",
                "procurement_source_name": payment_request_name,
                "docstatus": ["!=", 2],
            },
            fields=["name"],
        )
        for row in source_rows:
            pe_names.add(row.name)

    if current_payment_entry and current_payment_entry in pe_names:
        pe_names.remove(current_payment_entry)

    if not pe_names:
        return 0

    total = 0.0
    entries = frappe.get_all(
        "Payment Entry",
        filters={"name": ["in", list(pe_names)]},
        fields=["name", "paid_amount", "received_amount"],
    )
    for pe in entries:
        try:
            amount = float(pe.paid_amount or pe.received_amount or 0)
        except Exception:
            amount = 0
        total += abs(amount)

    return total


def _validate_payment_entry_total_against_request(doc, payment_request_name, pr_data):
    """Prevent cumulative Payment Entries from exceeding Payment Request total."""
    max_allowed = _get_payment_request_limit_amount(pr_data)
    if max_allowed <= 0:
        return

    current_amount = abs(float(doc.get("paid_amount") or doc.get("received_amount") or 0))
    existing_total = _get_existing_payment_entry_total(
        payment_request_name=payment_request_name,
        current_payment_entry=doc.get("name"),
    )
    new_total = existing_total + current_amount

    if new_total - max_allowed > 0.0001:
        frappe.throw(
            _(
                "Total Payment Entry amount for Payment Request {0} cannot exceed {1}. Existing: {2}, Current: {3}, New Total: {4}."
            ).format(
                payment_request_name,
                frappe.format_value(max_allowed, {"fieldtype": "Currency"}),
                frappe.format_value(existing_total, {"fieldtype": "Currency"}),
                frappe.format_value(current_amount, {"fieldtype": "Currency"}),
                frappe.format_value(new_total, {"fieldtype": "Currency"}),
            )
        )


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
