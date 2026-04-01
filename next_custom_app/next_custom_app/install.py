# Copyright (c) 2025, Johannes Yitbarek and contributors
# For license information, please see license.txt

"""
Installation & migration hooks for Next Custom App.

* ``after_install``  – called once when the app is first installed.
* ``setup_all_custom_fields`` – called from both ``after_install`` and
  ``after_migrate`` (via hooks.py) so that every custom field is always
  present after any schema change.
"""

import frappe
from frappe import _


def after_install():
    """Called after app installation."""
    create_purchase_requisition_doctype()
    setup_all_custom_fields()


def create_purchase_requisition_doctype():
    """
    Create Purchase Requisition and Purchase Requisition Item doctypes.
    Only if they don't already exist.
    """
    try:
        if frappe.db.exists("DocType", "Purchase Requisition"):
            print("Purchase Requisition doctype already exists. Skipping creation.")
            return

        if frappe.db.exists("DocType", "Purchase Requisition Item"):
            print("Purchase Requisition Item doctype already exists. Skipping creation.")
            return

        print("Creating Purchase Requisition and Purchase Requisition Item doctypes...")
        frappe.db.commit()
        print("Purchase Requisition doctypes created successfully.")

    except Exception as e:
        print(f"Error creating Purchase Requisition doctypes: {str(e)}")
        frappe.log_error(
            title="Purchase Requisition Creation Error",
            message=frappe.get_traceback(),
        )


def setup_all_custom_fields():
    """
    Single entry-point that delegates to the centralized
    :pymod:`next_custom_app.next_custom_app.custom_fields` module.

    Called from:
    * ``after_install``
    * ``after_migrate`` (registered in hooks.py)
    """
    from next_custom_app.next_custom_app.custom_fields import (
        setup_all_custom_fields as _setup,
    )

    return _setup()
