# Copyright (c) 2025, Nextcore Technologies and contributors
# For license information, please see license.txt

import json
import frappe
from frappe import _
from frappe.utils import now


# Procurement doctypes that should be tracked
PROCUREMENT_DOCTYPES = [
	"Material Request",
	"Purchase Requisition",
	"Request for Quotation",
	"Supplier Quotation",
	"Purchase Order",
	"Purchase Receipt",
	"Purchase Invoice"
]


def setup_custom_fields():
	"""
	Add custom fields to all procurement-related doctypes.
	This should be called AFTER app installation.
	Run: bench --site <site> execute next_custom_app.next_custom_app.utils.procurement_workflow.setup_custom_fields
	"""
	from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
	
	# Check if Procurement Document Link doctype exists
	has_doc_link = frappe.db.exists("DocType", "Procurement Document Link")
	
	if not has_doc_link:
		frappe.log_error(
			title="Procurement Document Link Not Found",
			message="The Procurement Document Link doctype was not found. Table field will be skipped."
		)
	
	custom_fields = {}
	
	for doctype in PROCUREMENT_DOCTYPES:
		# Skip if doctype doesn't exist
		if not frappe.db.exists("DocType", doctype):
			frappe.log_error(
				title=f"DocType {doctype} does not exist",
				message=f"Skipping custom field creation for {doctype}"
			)
			continue
		
		custom_fields[doctype] = [
			{
				"fieldname": "procurement_section",
				"label": "Procurement Workflow",
				"fieldtype": "Section Break",
				"insert_after": "amended_from",
				"collapsible": 1
			},
			{
				"fieldname": "procurement_source_doctype",
				"label": "Source DocType",
				"fieldtype": "Link",
				"options": "DocType",
				"insert_after": "procurement_section",
				"read_only": 1,
				"no_copy": 1,
				"print_hide": 1
			},
			{
				"fieldname": "procurement_source_name",
				"label": "Source Document",
				"fieldtype": "Dynamic Link",
				"options": "procurement_source_doctype",
				"insert_after": "procurement_source_doctype",
				"read_only": 1,
				"no_copy": 1,
				"print_hide": 1
			},
			{
				"fieldname": "procurement_column_break",
				"fieldtype": "Column Break",
				"insert_after": "procurement_source_name"
			},
		]
		
		# Only add the table field if Procurement Document Link exists
		if has_doc_link:
			custom_fields[doctype].append({
				"fieldname": "procurement_links",
				"label": "Child Documents",
				"fieldtype": "Table",
				"options": "Procurement Document Link",
				"insert_after": "procurement_column_break",
				"read_only": 1,
				"no_copy": 1,
				"print_hide": 1
			})
		else:
			# Add a placeholder text field instead
			custom_fields[doctype].append({
				"fieldname": "procurement_links_note",
				"label": "Document Links",
				"fieldtype": "Small Text",
				"insert_after": "procurement_column_break",
				"read_only": 1,
				"no_copy": 1,
				"print_hide": 1,
				"default": "Run setup_custom_fields() to enable document tracking",
				"hidden": 1
			})
		
	
	try:
		create_custom_fields(custom_fields, update=True)
		frappe.db.commit()
		frappe.msgprint("Procurement workflow custom fields created successfully!", indicator="green")
		return True
	except Exception as e:
		frappe.log_error(
			title="Procurement Workflow Setup Error",
			message=f"Error creating custom fields: {str(e)}\n{frappe.get_traceback()}"
		)
		frappe.msgprint(f"Error setting up custom fields: {str(e)}", indicator="red")
		return False


def get_active_flow():
	"""Get the currently active procurement flow"""
	return frappe.db.get_value(
		"Procurement Flow",
		{"is_active": 1},
		["name", "flow_name"],
		as_dict=True
	)


def get_flow_steps(flow_name):
	"""Get all steps for a specific procurement flow"""
	flow = frappe.get_doc("Procurement Flow", flow_name)
	return sorted(flow.flow_steps, key=lambda x: x.step_no)


def get_current_step(doctype, flow_name=None):
	"""Get the current step configuration for a doctype"""
	if not flow_name:
		active_flow = get_active_flow()
		if not active_flow:
			return None
		flow_name = active_flow.name
	
	steps = get_flow_steps(flow_name)
	for step in steps:
		if step.doctype_name == doctype:
			return step
	return None


def get_previous_step(current_doctype, flow_name=None):
	"""Get the previous step in the workflow"""
	if not flow_name:
		active_flow = get_active_flow()
		if not active_flow:
			return None
		flow_name = active_flow.name
	
	steps = get_flow_steps(flow_name)
	for i, step in enumerate(steps):
		if step.doctype_name == current_doctype and i > 0:
			return steps[i - 1]
	return None


def get_next_step(current_doctype, flow_name=None):
	"""Get the next step in the workflow"""
	if not flow_name:
		active_flow = get_active_flow()
		if not active_flow:
			return None
		flow_name = active_flow.name
	
	steps = get_flow_steps(flow_name)
	for i, step in enumerate(steps):
		if step.doctype_name == current_doctype and i < len(steps) - 1:
			return steps[i + 1]
	return None


def validate_step_order(doc):
	"""
	Validate that the document is being created in the correct step order.
	If requires_source is checked, ensure the source document exists and is valid.
	"""
	active_flow = get_active_flow()
	if not active_flow:
		# No active flow, skip validation
		return
	
	current_step = get_current_step(doc.doctype, active_flow.name)
	if not current_step:
		# Current doctype is not part of the workflow
		return
	
	# Check if source is required
	if current_step.requires_source:
		if not doc.get("procurement_source_doctype") or not doc.get("procurement_source_name"):
			frappe.throw(
				_("This document requires a source document from the previous step. "
				  "Please create it from the appropriate source document.")
			)
		
		# Validate that source is from the correct previous step
		previous_step = get_previous_step(doc.doctype, active_flow.name)
		if previous_step:
			if doc.procurement_source_doctype != previous_step.doctype_name:
				frappe.throw(
					_("Invalid source document. Expected {0}, but got {1}").format(
						previous_step.doctype_name,
						doc.procurement_source_doctype
					)
				)


def validate_quantity_limits(doc):
	"""
	Validate that quantities in the current document do not exceed
	the quantities available in the source document.
	"""
	if not doc.get("procurement_source_doctype") or not doc.get("procurement_source_name"):
		return
	
	# Get source document
	source_doc = frappe.get_doc(doc.procurement_source_doctype, doc.procurement_source_name)
	
	# Get items field names for different doctypes
	source_items_field = get_items_field_name(doc.procurement_source_doctype)
	target_items_field = get_items_field_name(doc.doctype)
	
	if not source_items_field or not target_items_field:
		return
	
	source_items = source_doc.get(source_items_field) or []
	target_items = doc.get(target_items_field) or []
	
	# Calculate already consumed quantities
	consumed_quantities = get_consumed_quantities(
		doc.procurement_source_doctype,
		doc.procurement_source_name,
		doc.doctype
	)
	
	# Validate each target item
	for target_item in target_items:
		item_code = target_item.item_code
		target_qty = target_item.qty or 0
		
		# Find matching source item
		source_item = next((si for si in source_items if si.item_code == item_code), None)
		if not source_item:
			frappe.throw(
				_("Item {0} does not exist in source document {1}").format(
					item_code,
					doc.procurement_source_name
				)
			)
		
		source_qty = source_item.qty or 0
		consumed_qty = consumed_quantities.get(item_code, 0)
		
		# Exclude current document if it's an update
		if not doc.is_new():
			current_consumed = get_document_item_quantities(doc.doctype, doc.name)
			consumed_qty -= current_consumed.get(item_code, 0)
		
		available_qty = source_qty - consumed_qty
		
		if target_qty > available_qty:
			frappe.throw(
				_("Quantity for item {0} exceeds available quantity. "
				  "Available: {1}, Requested: {2}, Already consumed: {3}").format(
					item_code,
					available_qty,
					target_qty,
					consumed_qty
				)
			)


def validate_items_against_source(doc):
	"""
	Validate that all items in the current document exist in the source document.
	"""
	if not doc.get("procurement_source_doctype") or not doc.get("procurement_source_name"):
		return
	
	source_doc = frappe.get_doc(doc.procurement_source_doctype, doc.procurement_source_name)
	
	source_items_field = get_items_field_name(doc.procurement_source_doctype)
	target_items_field = get_items_field_name(doc.doctype)
	
	if not source_items_field or not target_items_field:
		return
	
	source_items = source_doc.get(source_items_field) or []
	target_items = doc.get(target_items_field) or []
	
	source_item_codes = {item.item_code for item in source_items}
	
	for target_item in target_items:
		if target_item.item_code not in source_item_codes:
			frappe.throw(
				_("Item {0} does not exist in source document {1}").format(
					target_item.item_code,
					doc.procurement_source_name
				)
			)


def create_backward_link(source_doctype, source_name, target_doctype, target_name):
	"""
	Create a backward link from source to target document.
	This is called after submit of the target document.
	"""
	# Add link to source document
	source_doc = frappe.get_doc(source_doctype, source_name)
	
	# Check if link already exists
	existing_links = source_doc.get("procurement_links") or []
	for link in existing_links:
		if (link.target_doctype == target_doctype and 
			link.target_docname == target_name):
			return  # Link already exists
	
	# Add new link
	source_doc.append("procurement_links", {
		"source_doctype": source_doctype,
		"source_docname": source_name,
		"target_doctype": target_doctype,
		"target_docname": target_name,
		"link_date": now()
	})
	
	source_doc.save(ignore_permissions=True)
	frappe.db.commit()


def get_document_chain(doctype, docname):
	"""
	Get the complete document chain (backward and forward links)
	for a given document.
	"""
	chain = {
		"backward": [],
		"forward": []
	}
	
	# Get current document
	doc = frappe.get_doc(doctype, docname)
	
	# Get backward chain (source documents)
	if doc.get("procurement_source_doctype") and doc.get("procurement_source_name"):
		source_chain = get_document_chain(
			doc.procurement_source_doctype,
			doc.procurement_source_name
		)
		chain["backward"] = source_chain["backward"] + [{
			"doctype": doc.procurement_source_doctype,
			"name": doc.procurement_source_name
		}]
	
	# Get forward chain (target documents)
	forward_links = doc.get("procurement_links") or []
	for link in forward_links:
		chain["forward"].append({
			"doctype": link.target_doctype,
			"name": link.target_docname
		})
	
	return chain


def check_can_cancel(doc):
	"""
	Check if a document can be cancelled.
	Documents with child documents cannot be cancelled.
	"""
	forward_links = doc.get("procurement_links") or []
	if forward_links:
		child_docs = [f"{link.target_doctype}: {link.target_docname}" for link in forward_links]
		frappe.throw(
			_("Cannot cancel this document. It has child documents: {0}").format(
				", ".join(child_docs)
			)
		)


def get_consumed_quantities(source_doctype, source_name, target_doctype):
	"""
	Get the total consumed quantities from a source document.
	Returns a dict of {item_code: consumed_qty}
	"""
	consumed = {}
	
	# Get all documents created from this source
	source_doc = frappe.get_doc(source_doctype, source_name)
	forward_links = source_doc.get("procurement_links") or []
	
	target_items_field = get_items_field_name(target_doctype)
	if not target_items_field:
		return consumed
	
	for link in forward_links:
		if link.target_doctype == target_doctype:
			try:
				target_doc = frappe.get_doc(link.target_doctype, link.target_docname)
				if target_doc.docstatus != 2:  # Not cancelled
					items = target_doc.get(target_items_field) or []
					for item in items:
						item_code = item.item_code
						qty = item.qty or 0
						consumed[item_code] = consumed.get(item_code, 0) + qty
			except frappe.DoesNotExistError:
				pass
	
	return consumed


def get_document_item_quantities(doctype, docname):
	"""
	Get quantities for all items in a specific document.
	Returns a dict of {item_code: qty}
	"""
	quantities = {}
	
	try:
		doc = frappe.get_doc(doctype, docname)
		items_field = get_items_field_name(doctype)
		if items_field:
			items = doc.get(items_field) or []
			for item in items:
				quantities[item.item_code] = item.qty or 0
	except frappe.DoesNotExistError:
		pass
	
	return quantities


def get_items_field_name(doctype):
	"""
	Get the field name that contains items for different procurement doctypes.
	"""
	items_field_map = {
		"Material Request": "items",
		"Purchase Requisition": "items",
		"Request for Quotation": "items",
		"Supplier Quotation": "items",
		"Purchase Order": "items",
		"Purchase Receipt": "items",
		"Purchase Invoice": "items"
	}
	return items_field_map.get(doctype)


@frappe.whitelist()
def get_available_quantities(source_doctype, source_name, target_doctype):
	"""
	API method to get available quantities for each item in the source document.
	Used by client-side scripts to show available quantities.
	"""
	source_doc = frappe.get_doc(source_doctype, source_name)
	source_items_field = get_items_field_name(source_doctype)
	
	if not source_items_field:
		return {}
	
	source_items = source_doc.get(source_items_field) or []
	consumed_quantities = get_consumed_quantities(source_doctype, source_name, target_doctype)
	
	available = {}
	for item in source_items:
		item_code = item.item_code
		source_qty = item.qty or 0
		consumed_qty = consumed_quantities.get(item_code, 0)
		available[item_code] = {
			"source_qty": source_qty,
			"consumed_qty": consumed_qty,
			"available_qty": source_qty - consumed_qty
		}
	
	return available


def validate_procurement_document(doc, method=None):
	"""
	Main validation hook for procurement documents.
	This is called during the validate event.
	"""
	try:
		validate_step_order(doc)
		validate_quantity_limits(doc)
		validate_items_against_source(doc)
	except Exception as e:
		frappe.log_error(
			title=f"Procurement Workflow Validation Error - {doc.doctype} {doc.name}",
			message=frappe.get_traceback()
		)
		raise


def on_procurement_submit(doc, method=None):
	"""
	Hook called when a procurement document is submitted.
	Creates backward links to track the document chain.
	"""
	try:
		if doc.get("procurement_source_doctype") and doc.get("procurement_source_name"):
			create_backward_link(
				doc.procurement_source_doctype,
				doc.procurement_source_name,
				doc.doctype,
				doc.name
			)
	except Exception as e:
		frappe.log_error(
			title=f"Procurement Workflow Submit Error - {doc.doctype} {doc.name}",
			message=frappe.get_traceback()
		)
		raise