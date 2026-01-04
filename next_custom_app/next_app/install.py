# Copyright (c) 2025, Nextcore Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe import _


def after_install():
	"""
	After installation hook.
	Automatically sets up custom fields after doctypes are synced.
	"""
	frappe.log("Procurement workflow app installed. Setting up custom fields...")
	
	# Commit any pending transactions to ensure doctypes are available
	frappe.db.commit()
	
	# Setup workspace
	setup_workspace()
	
	# Import and run setup
	try:
		from next_custom_app.next_custom_app.utils.procurement_workflow import setup_custom_fields
		result = setup_custom_fields()
		
		if result:
			frappe.log("Procurement workflow custom fields setup completed successfully.")
		else:
			frappe.log("Procurement workflow custom fields setup encountered issues. Check Error Log.")
	except Exception as e:
		frappe.log_error(
			title="Procurement Workflow Installation Error",
			message=f"Error during custom fields setup: {str(e)}\n{frappe.get_traceback()}"
		)
		frappe.msgprint(
			_("Installation completed but custom fields setup failed. Please run: bench --site {0} execute next_custom_app.next_custom_app.utils.procurement_workflow.setup_custom_fields").format(frappe.local.site),
			indicator="orange",
			alert=True
		)


def setup_workspace():
	"""Setup Procurement Workflow workspace"""
	import os
	import json
	
	workspace_path = frappe.get_app_path("next_custom_app", "next_custom_app", "workspace", "procurement_workflow", "procurement_workflow.json")
	
	if os.path.exists(workspace_path):
		try:
			with open(workspace_path, 'r') as f:
				workspace_data = json.load(f)
			
			# Check if workspace already exists
			if not frappe.db.exists("Workspace", workspace_data.get("name")):
				workspace = frappe.get_doc(workspace_data)
				workspace.insert(ignore_permissions=True)
				frappe.db.commit()
				frappe.log("Procurement Workflow workspace created successfully.")
			else:
				frappe.log("Procurement Workflow workspace already exists.")
		except Exception as e:
			frappe.log_error(
				title="Workspace Setup Error",
				message=f"Error setting up workspace: {str(e)}\n{frappe.get_traceback()}"
			)