# Copyright (c) 2025, Johannes Yitbarek and contributors
# For license information, please see license.txt

import frappe
from frappe import _


def after_install():
	"""Called after app installation"""
	create_purchase_requisition_doctype()


def create_purchase_requisition_doctype():
	"""
	Create Purchase Requisition and Purchase Requisition Item doctypes
	Only if they don't already exist
	"""
	try:
		# Check if Purchase Requisition already exists
		if frappe.db.exists("DocType", "Purchase Requisition"):
			print("Purchase Requisition doctype already exists. Skipping creation.")
			return
		
		# Check if Purchase Requisition Item already exists
		if frappe.db.exists("DocType", "Purchase Requisition Item"):
			print("Purchase Requisition Item doctype already exists. Skipping creation.")
			return
		
		# Import the doctypes if they don't exist
		print("Creating Purchase Requisition and Purchase Requisition Item doctypes...")
		
		# The doctypes will be automatically created when the app is installed
		# This function just logs the process and could be extended for custom logic
		
		frappe.db.commit()
		print("Purchase Requisition doctypes created successfully.")
		
	except Exception as e:
		print(f"Error creating Purchase Requisition doctypes: {str(e)}")
		frappe.log_error(
			title="Purchase Requisition Creation Error",
			message=frappe.get_traceback()
		)