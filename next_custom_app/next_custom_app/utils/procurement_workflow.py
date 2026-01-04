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
				"read_only": 0,
				"no_copy": 1,
				"print_hide": 1,
				"in_list_view": 0,
				"in_standard_filter": 0
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
				"in_standard_filter": 0
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


@frappe.whitelist()
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


@frappe.whitelist()
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
			next_step = steps[i + 1]
			return {
				"doctype_name": next_step.doctype_name,
				"step_no": next_step.step_no,
				"requires_source": next_step.requires_source
			}
	return None


def validate_step_order(doc):
	"""
	Validate that the document is being created in the correct step order.
	If requires_source is checked, ensure the source document exists and is valid.
	
	UPDATED: Now allows manual document creation when source is not provided.
	Only enforces source requirement when a source is partially set (one field but not the other).
	"""
	active_flow = get_active_flow()
	if not active_flow:
		# No active flow, skip validation
		return
	
	current_step = get_current_step(doc.doctype, active_flow.name)
	if not current_step:
		# Current doctype is not part of the workflow
		return
	
	# Check if source fields are set
	has_source_doctype = bool(doc.get("procurement_source_doctype"))
	has_source_name = bool(doc.get("procurement_source_name"))
	
	# Check if source is required
	if current_step.requires_source:
		# If both are empty, allow manual creation
		if not has_source_doctype and not has_source_name:
			frappe.logger().info(f"{doc.doctype} {doc.name}: Manual creation allowed - no source fields set")
			return
		
		# If only one is set, that's an error - both must be set or both empty
		if has_source_doctype != has_source_name:
			frappe.throw(
				_("Both source document type and name must be provided together, or neither should be set.")
			)
		
		# Both are set - validate that source is from the correct previous step
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
	This now properly checks against ALL existing child documents, not just those in the links table.
	
	SPECIAL CASES:
	- RFQ (Request for Quotation): Skipped - multiple RFQs can request same quantities for different suppliers
	- Supplier Quotation: Validates supplier exists in source RFQ
	- Purchase Order: Tracks against original RFQ (not Supplier Quotation) to prevent over-allocation across suppliers
	"""
	if not doc.get("procurement_source_doctype") or not doc.get("procurement_source_name"):
		return
	
	# Skip quantity validation for RFQ since we're collecting quotes from multiple suppliers
	# for the same items - not consuming quantities
	if doc.doctype == "Request for Quotation":
		frappe.logger().info(f"Skipping quantity validation for RFQ {doc.name} - multiple suppliers quote for same items")
		return
	
	# For Supplier Quotation, validate supplier is in source RFQ
	if doc.doctype == "Supplier Quotation" and doc.procurement_source_doctype == "Request for Quotation":
		validate_supplier_in_rfq(doc)
	
	# Get source document
	source_doc = frappe.get_doc(doc.procurement_source_doctype, doc.procurement_source_name)
	
	# For Purchase Order from Supplier Quotation, track against RFQ not SQ
	# This prevents over-allocation when only one supplier will be awarded from multiple quotes
	tracking_source_doctype = doc.procurement_source_doctype
	tracking_source_name = doc.procurement_source_name
	
	if doc.doctype == "Purchase Order" and doc.procurement_source_doctype == "Supplier Quotation":
		# Get the RFQ that the Supplier Quotation came from
		sq_doc = source_doc
		if sq_doc.get("procurement_source_doctype") == "Request for Quotation" and sq_doc.get("procurement_source_name"):
			# Track against RFQ instead of SQ for quantity limits
			tracking_source_doctype = "Request for Quotation"
			tracking_source_name = sq_doc.procurement_source_name
			source_doc = frappe.get_doc(tracking_source_doctype, tracking_source_name)
			frappe.logger().info(f"PO {doc.name}: Tracking quantities against RFQ {tracking_source_name} instead of SQ {doc.procurement_source_name}")
	
	# Get items field names for different doctypes
	source_items_field = get_items_field_name(doc.procurement_source_doctype)
	target_items_field = get_items_field_name(doc.doctype)
	
	if not source_items_field or not target_items_field:
		return
	
	source_items = source_doc.get(source_items_field) or []
	target_items = doc.get(target_items_field) or []
	
	# Calculate already consumed quantities, excluding current document if it's being updated
	exclude_current = doc.name if not doc.is_new() else None
	
	# Get detailed breakdown for better error messages
	# Use tracking_source for PO to track against RFQ instead of SQ
	consumed_breakdown = get_consumed_quantities_detailed(
		tracking_source_doctype,
		tracking_source_name,
		doc.doctype,
		exclude_doc=exclude_current
	)
	
	frappe.logger().info(f"Validating quantities for {doc.doctype} {doc.name}")
	frappe.logger().info(f"Tracking Source: {tracking_source_name}, Consumed breakdown: {consumed_breakdown}")
	
	# Validate each target item
	for target_item in target_items:
		item_code = target_item.item_code
		target_qty = target_item.qty or 0
		
		# Find matching source item
		source_item = next((si for si in source_items if si.item_code == item_code), None)
		if not source_item:
			# Create detailed error message for invalid item
			error_msg = f"""
			<div style="padding: 15px; background: #fff3cd; border-left: 4px solid #ffc107; margin: 10px 0;">
				<h4 style="color: #856404; margin-top: 0;">❌ Invalid Item</h4>
				<p style="font-size: 14px; margin: 10px 0;">
					Item <strong style="color: #d9534f;">{item_code}</strong> does not exist in the source document.
				</p>
				<div style="background: white; padding: 10px; border-radius: 4px; margin-top: 10px;">
					<p style="margin: 5px 0;"><strong>Source Document:</strong>
						<a href="/app/{doc.procurement_source_doctype.lower().replace(' ', '-')}/{doc.procurement_source_name}"
						   target="_blank" style="color: #007bff;">
							{doc.procurement_source_doctype}: {doc.procurement_source_name}
						</a>
					</p>
					<p style="margin: 5px 0; color: #666;">
						Please select items that exist in the source document.
					</p>
				</div>
			</div>
			"""
			frappe.throw(error_msg, title="Invalid Item")
		
		source_qty = source_item.qty or 0
		item_breakdown = consumed_breakdown.get(item_code, {"total": 0, "documents": []})
		consumed_qty = item_breakdown["total"]
		available_qty = source_qty - consumed_qty
		
		frappe.logger().info(f"Item {item_code}: Source={source_qty}, Consumed={consumed_qty}, Requested={target_qty}, Available={available_qty}")
		
		if target_qty > available_qty:
			# Create detailed breakdown HTML
			breakdown_html = ""
			if item_breakdown["documents"]:
				breakdown_html = "<ul style='margin: 10px 0; padding-left: 20px;'>"
				for doc_info in item_breakdown["documents"]:
					doc_link = f"/app/{doc.doctype.lower().replace(' ', '-')}/{doc_info['name']}"
					breakdown_html += f"""
					<li style="margin: 5px 0;">
						<strong>{doc_info['qty']}</strong>
						(<a href="{doc_link}" target="_blank" style="color: #007bff;">{doc_info['name']}</a>)
					</li>
					"""
				breakdown_html += "</ul>"
			else:
				breakdown_html = "<p style='margin: 10px 0; color: #666;'><em>No documents processed yet</em></p>"
			
			error_msg = f"""
			<div style="padding: 15px; background: white; border: 2px solid #dc3545; border-radius: 6px; margin: 10px 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">
				<h4 style="color: #dc3545; margin: 0 0 12px 0; font-size: 16px;">
					⚠️ Quantity Exceeds Requested Stock for <strong>{item_code}</strong>
				</h4>
				
				<table style="width: 100%; border-collapse: collapse; margin-bottom: 12px;">
					<tr style="border-bottom: 1px solid #e9ecef;">
						<td style="padding: 6px 0; color: #495057;">Source Quantity:</td>
						<td style="padding: 6px 0; text-align: right;">
							<strong style="color: #28a745;">{source_qty}</strong>
						</td>
					</tr>
					<tr style="border-bottom: 1px solid #e9ecef;">
						<td style="padding: 6px 0; color: #495057;">Already Processed:</td>
						<td style="padding: 6px 0; text-align: right;">
							<strong style="color: #ffc107;">{consumed_qty}</strong>
						</td>
					</tr>
					<tr style="border-bottom: 1px solid #e9ecef;">
						<td style="padding: 6px 0; color: #495057;">Available:</td>
						<td style="padding: 6px 0; text-align: right;">
							<strong style="color: {'#28a745' if available_qty > 0 else '#dc3545'};">{available_qty}</strong>
						</td>
					</tr>
					<tr>
						<td style="padding: 6px 0; color: #495057;">Your Request:</td>
						<td style="padding: 6px 0; text-align: right;">
							<strong style="color: #dc3545;">{target_qty}</strong>
						</td>
					</tr>
				</table>
				
				{f'''
				<div style="background: #fff3cd; padding: 10px; border-radius: 4px; margin-bottom: 10px; border-left: 3px solid #ffc107;">
					<p style="margin: 0 0 6px 0; font-weight: 600; color: #856404; font-size: 13px;">📋 Already Processed In:</p>
					{breakdown_html}
				</div>
				''' if item_breakdown["documents"] else ''}
				
				<p style="margin: 0; color: #004085; font-size: 12px; padding: 8px; background: #e7f3ff; border-radius: 4px;">
					<strong>💡 Tip:</strong> Reduce quantity to <strong>{available_qty}</strong> or less
					| <a href="/app/{doc.procurement_source_doctype.lower().replace(' ', '-')}/{doc.procurement_source_name}"
					      target="_blank" style="color: #007bff;">View {doc.procurement_source_doctype} →</a>
				</p>
			</div>
			"""
			frappe.throw(error_msg, title=f"Quantity Exceeded for {item_code}")


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


def validate_supplier_in_rfq(doc):
	"""
	Validate that the supplier in a Supplier Quotation exists in the source RFQ.
	This ensures suppliers can only quote if they were invited in the RFQ.
	
	Args:
		doc: Supplier Quotation document
	"""
	if not doc.get("supplier"):
		return  # No supplier set yet, skip validation
	
	try:
		# Get source RFQ
		rfq = frappe.get_doc("Request for Quotation", doc.procurement_source_name)
		
		# Get list of suppliers in RFQ
		rfq_suppliers = [s.supplier for s in rfq.suppliers] if rfq.get("suppliers") else []
		
		# Check if current supplier is in RFQ
		if doc.supplier not in rfq_suppliers:
			supplier_list_html = ""
			if rfq_suppliers:
				supplier_list_html = "<ul style='margin: 10px 0; padding-left: 20px;'>"
				for supplier in rfq_suppliers:
					supplier_list_html += f"<li style='margin: 5px 0;'><strong>{supplier}</strong></li>"
				supplier_list_html += "</ul>"
			else:
				supplier_list_html = "<p style='margin: 10px 0; color: #666;'><em>No suppliers in RFQ</em></p>"
			
			error_msg = f"""
			<div style="padding: 15px; background: white; border: 2px solid #dc3545; border-radius: 6px; margin: 10px 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">
				<h4 style="color: #dc3545; margin: 0 0 12px 0; font-size: 16px;">
					⚠️ Supplier Not in RFQ
				</h4>
				
				<div style="background: #fff3cd; padding: 12px; border-left: 4px solid #ffc107; border-radius: 4px; margin-bottom: 15px;">
					<p style="margin: 0; color: #856404; font-size: 14px;">
						Supplier <strong style="color: #dc3545;">{doc.supplier}</strong> is not listed in the source RFQ.
					</p>
				</div>
				
				<table style="width: 100%; border-collapse: collapse; margin-bottom: 12px;">
					<tr style="border-bottom: 1px solid #e9ecef;">
						<td style="padding: 6px 0; color: #495057;">Source RFQ:</td>
						<td style="padding: 6px 0; text-align: right;">
							<strong><a href="/app/request-for-quotation/{doc.procurement_source_name}" target="_blank" style="color: #007bff;">{doc.procurement_source_name}</a></strong>
						</td>
					</tr>
					<tr style="border-bottom: 1px solid #e9ecef;">
						<td style="padding: 6px 0; color: #495057;">Attempted Supplier:</td>
						<td style="padding: 6px 0; text-align: right;">
							<strong style="color: #dc3545;">{doc.supplier}</strong>
						</td>
					</tr>
				</table>
				
				<div style="margin-bottom: 10px;">
					<p style="margin: 0 0 6px 0; font-weight: 600; color: #495057; font-size: 13px;">📋 Allowed Suppliers in RFQ:</p>
					{supplier_list_html}
				</div>
				
				<p style="margin: 0; color: #004085; font-size: 12px; padding: 8px; background: #e7f3ff; border-radius: 4px;">
					<strong>💡 Tip:</strong> Only suppliers listed in the RFQ can submit quotations.
					Please select one of the allowed suppliers or add this supplier to the RFQ first.
				</p>
			</div>
			"""
			frappe.throw(error_msg, title=f"Invalid Supplier for RFQ")
			
	except frappe.DoesNotExistError:
		# RFQ not found, log but don't block
		frappe.log_error(
			title=f"RFQ Not Found - {doc.procurement_source_name}",
			message=f"Could not validate supplier for SQ {doc.name}"
		)


def create_backward_link(source_doctype, source_name, target_doctype, target_name):
	"""
	Create a backward link from source to target document.
	This is called after submit of the target document.
	"""
	try:
		# Add link to source document
		source_doc = frappe.get_doc(source_doctype, source_name)
		
		# Check if procurement_links field exists (custom fields must be set up)
		if not source_doc.meta.has_field("procurement_links"):
			frappe.log_error(
				title="Procurement Links Field Not Found",
				message=f"The procurement_links field does not exist in {source_doctype}. "
				f"Please run setup_custom_fields() to enable document tracking.\n"
				f"Attempted to link {target_doctype}: {target_name}"
			)
			return
		
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
		
		# Allow updating child tables on submitted documents
		source_doc.flags.ignore_validate_update_after_submit = True
		source_doc.save(ignore_permissions=True)
		frappe.db.commit()
		
	except Exception as e:
		# Log the error but don't block the submission
		frappe.log_error(
			title=f"Error Creating Backward Link - {source_doctype} {source_name}",
			message=f"Failed to create link to {target_doctype} {target_name}\n{frappe.get_traceback()}"
		)


@frappe.whitelist()
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


def check_can_cancel(doc, method=None):
	"""
	Check if a document can be cancelled.
	Documents with child documents cannot be cancelled.
	"""
	forward_links = doc.get("procurement_links") or []
	if forward_links:
		# Group child documents by doctype for better organization
		docs_by_type = {}
		for link in forward_links:
			if link.target_doctype not in docs_by_type:
				docs_by_type[link.target_doctype] = []
			docs_by_type[link.target_doctype].append(link.target_docname)
		
		# Build HTML for child documents list
		child_docs_html = ""
		for doctype, doc_names in docs_by_type.items():
			child_docs_html += f"<div style='margin: 8px 0;'>"
			child_docs_html += f"<strong style='color: #495057;'>{doctype}</strong> "
			child_docs_html += f"<span style='background: #e9ecef; padding: 2px 8px; border-radius: 10px; font-size: 11px; font-weight: 600;'>{len(doc_names)}</span>"
			child_docs_html += "<ul style='margin: 5px 0 0 0; padding-left: 20px;'>"
			for doc_name in doc_names:
				doc_link = f"/app/{doctype.lower().replace(' ', '-')}/{doc_name}"
				child_docs_html += f"""
					<li style="margin: 3px 0;">
						<a href="{doc_link}" target="_blank" style="color: #007bff; text-decoration: none;">
							{doc_name}
						</a>
					</li>
				"""
			child_docs_html += "</ul></div>"
		
		error_msg = f"""
		<div style="padding: 20px; background: white; border: 2px solid #dc3545; border-radius: 8px; margin: 10px 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">
			<h4 style="color: #dc3545; margin: 0 0 15px 0; font-size: 18px; display: flex; align-items: center; gap: 8px;">
				<span style="font-size: 24px;">🚫</span>
				Cannot Cancel Document
			</h4>
			
			<div style="background: #fff3cd; padding: 12px; border-left: 4px solid #ffc107; border-radius: 4px; margin-bottom: 15px;">
				<p style="margin: 0; color: #856404; font-size: 14px;">
					This document has <strong>{len(forward_links)} child document{'s' if len(forward_links) > 1 else ''}</strong> that must be cancelled first.
				</p>
			</div>
			
			<div style="margin-bottom: 15px;">
				<p style="margin: 0 0 10px 0; font-weight: 600; color: #495057; font-size: 14px;">
					📋 Child Documents:
				</p>
				{child_docs_html}
			</div>
			
			<div style="background: #e7f3ff; padding: 12px; border-radius: 4px; margin-top: 15px;">
				<p style="margin: 0; color: #004085; font-size: 13px;">
					<strong>💡 Tip:</strong> Cancel the child documents first, then you can cancel this document.
				</p>
			</div>
		</div>
		"""
		
		frappe.throw(error_msg, title="Cancellation Not Allowed")


def get_consumed_quantities_detailed(source_doctype, source_name, target_doctype, exclude_doc=None):
	"""
	Get detailed consumed quantities with document-level breakdown for better error messages.
	Returns a dict of {item_code: {"total": qty, "documents": [{"name": doc_name, "qty": qty}]}}
	
	Args:
		source_doctype: The source document type (e.g., "Material Request")
		source_name: The source document name (e.g., "MR-00001")
		target_doctype: The target/child document type (e.g., "Purchase Requisition")
		exclude_doc: Optional document name to exclude from calculation (for updates)
	"""
	consumed = {}
	
	target_items_field = get_items_field_name(target_doctype)
	if not target_items_field:
		return consumed
	
	try:
		child_docs = frappe.get_all(
			target_doctype,
			filters={
				"procurement_source_doctype": source_doctype,
				"procurement_source_name": source_name,
				"docstatus": ["!=", 2]  # Not cancelled
			},
			fields=["name"]
		)
		
		for child_doc_ref in child_docs:
			doc_name = child_doc_ref.name
			
			if exclude_doc and doc_name == exclude_doc:
				continue
			
			try:
				target_doc = frappe.get_doc(target_doctype, doc_name)
				items = target_doc.get(target_items_field) or []
				
				for item in items:
					item_code = item.item_code
					qty = item.qty or 0
					
					if item_code not in consumed:
						consumed[item_code] = {"total": 0, "documents": []}
					
					consumed[item_code]["total"] += qty
					consumed[item_code]["documents"].append({
						"name": doc_name,
						"qty": qty
					})
					
			except frappe.DoesNotExistError:
				pass
				
	except Exception as e:
		frappe.log_error(
			title=f"Error getting detailed consumed quantities - {source_doctype} {source_name}",
			message=frappe.get_traceback()
		)
	
	return consumed


def get_consumed_quantities(source_doctype, source_name, target_doctype, exclude_doc=None):
	"""
	Get the total consumed quantities from a source document by querying database directly.
	This ensures we capture all child documents, even those not yet in the links table.
	Returns a dict of {item_code: consumed_qty}
	
	Args:
		source_doctype: The source document type (e.g., "Material Request")
		source_name: The source document name (e.g., "MR-00001")
		target_doctype: The target/child document type (e.g., "Purchase Requisition")
		exclude_doc: Optional document name to exclude from calculation (for updates)
	"""
	consumed = {}
	
	target_items_field = get_items_field_name(target_doctype)
	if not target_items_field:
		return consumed
	
	# Query database for ALL documents of target type that reference this source
	try:
		child_docs = frappe.get_all(
			target_doctype,
			filters={
				"procurement_source_doctype": source_doctype,
				"procurement_source_name": source_name,
				"docstatus": ["!=", 2]  # Not cancelled
			},
			fields=["name"]
		)
		
		frappe.logger().info(f"Found {len(child_docs)} {target_doctype} documents from {source_doctype} {source_name}")
		
		# Calculate consumed quantities from each child document
		for child_doc_ref in child_docs:
			doc_name = child_doc_ref.name
			
			# Skip if this is the document being excluded (current doc during validation)
			if exclude_doc and doc_name == exclude_doc:
				frappe.logger().info(f"Excluding current document: {doc_name}")
				continue
			
			try:
				target_doc = frappe.get_doc(target_doctype, doc_name)
				items = target_doc.get(target_items_field) or []
				
				for item in items:
					item_code = item.item_code
					qty = item.qty or 0
					consumed[item_code] = consumed.get(item_code, 0) + qty
					frappe.logger().info(f"Added {qty} of {item_code} from {doc_name}, total consumed: {consumed[item_code]}")
					
			except frappe.DoesNotExistError:
				pass
				
	except Exception as e:
		frappe.log_error(
			title=f"Error getting consumed quantities - {source_doctype} {source_name}",
			message=frappe.get_traceback()
		)
	
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


@frappe.whitelist()
def get_linked_documents_with_counts(doctype, docname):
	"""
	Get all linked documents (forward and backward) with counts.
	Used to display navigation bar with smart action buttons.
	Now includes draft documents (not just submitted ones).
	Returns ALL descendants in the chain, not just direct children.
	Returns: {
		"backward": [{"doctype": "Material Request", "count": 1, "documents": ["MR-001"]}],
		"forward": [{"doctype": "Purchase Requisition", "count": 2, "documents": ["PR-001", "PR-002"]}]
	}
	"""
	linked_docs = {
		"backward": [],
		"forward": []
	}
	
	try:
		# Get current document
		doc = frappe.get_doc(doctype, docname)
		
		# Get backward links (source documents)
		if doc.get("procurement_source_doctype") and doc.get("procurement_source_name"):
			source_doctype = doc.procurement_source_doctype
			source_name = doc.procurement_source_name
			
			# Recursively get all backward links
			backward_chain = []
			current_doctype = source_doctype
			current_name = source_name
			
			while current_doctype and current_name:
				backward_chain.append({
					"doctype": current_doctype,
					"name": current_name
				})
				
				# Get next parent
				try:
					parent_doc = frappe.get_doc(current_doctype, current_name)
					current_doctype = parent_doc.get("procurement_source_doctype")
					current_name = parent_doc.get("procurement_source_name")
				except:
					break
			
			# Group by doctype and count
			backward_by_type = {}
			for item in backward_chain:
				dt = item["doctype"]
				if dt not in backward_by_type:
					backward_by_type[dt] = []
				backward_by_type[dt].append(item["name"])
			
			for dt, docs in backward_by_type.items():
				linked_docs["backward"].append({
					"doctype": dt,
					"count": len(docs),
					"documents": docs
				})
		
		# Get forward links (child documents) - RECURSIVELY collecting ALL descendants
		forward_by_type = {}
		
		def collect_all_descendants(dt, dn, visited=None):
			"""Recursively collect all descendant documents"""
			if visited is None:
				visited = set()
			
			doc_key = f"{dt}::{dn}"
			if doc_key in visited:
				return
			visited.add(doc_key)
			
			# Search database for direct children of this document
			for child_doctype in PROCUREMENT_DOCTYPES:
				try:
					child_docs = frappe.get_all(
						child_doctype,
						filters={
							"procurement_source_doctype": dt,
							"procurement_source_name": dn,
							"docstatus": ["!=", 2]  # Not cancelled
						},
						fields=["name"]
					)
					
					if child_docs:
						if child_doctype not in forward_by_type:
							forward_by_type[child_doctype] = []
						
						for child_doc in child_docs:
							if child_doc.name not in forward_by_type[child_doctype]:
								forward_by_type[child_doctype].append(child_doc.name)
							
							# Recursively collect descendants of this child
							collect_all_descendants(child_doctype, child_doc.name, visited)
							
				except Exception as e:
					# Doctype might not exist or other error, continue
					pass
		
		# Start recursive collection from current document
		collect_all_descendants(doctype, docname)
		
		# Build final forward links list
		for dt, docs in forward_by_type.items():
			linked_docs["forward"].append({
				"doctype": dt,
				"count": len(docs),
				"documents": docs
			})
		
	except Exception as e:
		frappe.log_error(
			title=f"Error getting linked documents - {doctype} {docname}",
			message=frappe.get_traceback()
		)
	
	return linked_docs


@frappe.whitelist()
def get_document_flow_with_statuses(doctype, docname):
	"""
	Get the complete document flow tree from root with the current document's path highlighted.
	Returns a hierarchical structure showing all documents with current path marked.
	"""
	flow_data = {
		"nodes": [],
		"current_doc": {
			"doctype": doctype,
			"name": docname
		}
	}
	
	try:
		# Step 1: Find the root document (traverse backward)
		root_doctype, root_docname = find_root_document(doctype, docname)
		
		# Step 2: Build complete tree from root
		# Step 3: Mark the current document's path
		current_path = get_path_to_document(doctype, docname)
		
		# Step 4: Build the tree with all documents
		processed = set()
		build_complete_tree(flow_data["nodes"], root_doctype, root_docname, current_path, processed, doctype, docname)
		
	except Exception as e:
		frappe.log_error(
			title=f"Error getting document flow - {doctype} {docname}",
			message=frappe.get_traceback()
		)
		frappe.throw(_("Error loading document flow. Check error log for details."))
	
	return flow_data


def find_root_document(doctype, docname):
	"""Find the root (topmost) document by traversing backward."""
	current_dt = doctype
	current_name = docname
	max_iterations = 20
	iterations = 0
	
	while iterations < max_iterations:
		try:
			doc = frappe.get_doc(current_dt, current_name)
			if doc.get("procurement_source_doctype") and doc.get("procurement_source_name"):
				current_dt = doc.procurement_source_doctype
				current_name = doc.procurement_source_name
				iterations += 1
			else:
				break
		except:
			break
	
	return current_dt, current_name


def get_path_to_document(target_doctype, target_docname):
	"""Get the path from root to the target document."""
	path = []
	current_dt = target_doctype
	current_name = target_docname
	max_iterations = 20
	iterations = 0
	
	# Build path backward from target to root
	while iterations < max_iterations:
		path.insert(0, f"{current_dt}::{current_name}")
		try:
			doc = frappe.get_doc(current_dt, current_name)
			if doc.get("procurement_source_doctype") and doc.get("procurement_source_name"):
				current_dt = doc.procurement_source_doctype
				current_name = doc.procurement_source_name
				iterations += 1
			else:
				break
		except:
			break
	
	return set(path)


def build_complete_tree(nodes_list, doctype, docname, current_path, processed, target_dt, target_name):
	"""Recursively build the complete document tree with current path marked."""
	doc_key = f"{doctype}::{docname}"
	
	if doc_key in processed:
		return
	
	processed.add(doc_key)
	
	# Determine if this document is in the current path
	is_in_path = doc_key in current_path
	is_current = (doctype == target_dt and docname == target_name)
	
	# Build node for current document
	node = build_flow_node(doctype, docname, is_current)
	if not node:
		return
	
	node["is_in_path"] = is_in_path
	node["is_grayed"] = not is_in_path
	node["children"] = []
	
	# Get all forward documents (children)
	try:
		linked = get_linked_documents_with_counts(doctype, docname)
		
		if linked.get("forward"):
			# Process each child document
			for link in linked["forward"]:
				dt = link["doctype"]
				doc_names = link["documents"]
				
				for doc_name in doc_names:
					child_key = f"{dt}::{doc_name}"
					if child_key not in processed:
						# Recursively build child tree
						child_nodes = []
						build_complete_tree(child_nodes, dt, doc_name, current_path, processed, target_dt, target_name)
						if child_nodes:
							node["children"].extend(child_nodes)
	except Exception as e:
		frappe.logger().error(f"Error building tree for {doctype} {docname}: {str(e)}")
	
	nodes_list.append(node)


def build_flow_node(doctype, docname, is_current=False):
	"""
	Build a flow node with document details and status.
	"""
	try:
		doc = frappe.get_doc(doctype, docname)
		
		node = {
			"doctype": doctype,
			"name": docname,
			"is_current": is_current,
			"is_submitted": doc.docstatus == 1,
			"status": doc.get("status") or ("Submitted" if doc.docstatus == 1 else "Draft"),
			"workflow_state": doc.get("workflow_state"),
			"branches": []
		}
		
		return node
	except Exception as e:
		frappe.log_error(
			title=f"Error building flow node - {doctype} {docname}",
			message=str(e)
		)
		return None


@frappe.whitelist()
def get_procurement_analysis(doctype, docname):
	"""
	Get procurement analysis for a source document.
	Shows statistics about child documents, item consumption, etc.
	"""
	analysis = {
		"total_children": 0,
		"total_items": 0,
		"total_quantity": 0,
		"completion_rate": 0,
		"items_breakdown": []
	}
	
	try:
		# Get source document
		source_doc = frappe.get_doc(doctype, docname)
		source_items_field = get_items_field_name(doctype)
		
		if not source_items_field:
			return analysis
		
		source_items = source_doc.get(source_items_field) or []
		analysis["total_items"] = len(source_items)
		
		# Calculate total source quantity
		total_source_qty = sum(item.qty or 0 for item in source_items)
		analysis["total_quantity"] = total_source_qty
		
		# Get all child documents across all types
		total_children = 0
		for child_doctype in PROCUREMENT_DOCTYPES:
			try:
				children = frappe.get_all(
					child_doctype,
					filters={
						"procurement_source_doctype": doctype,
						"procurement_source_name": docname,
						"docstatus": ["!=", 2]
					},
					fields=["name"]
				)
				total_children += len(children)
			except:
				pass
		
		analysis["total_children"] = total_children
		
		# Calculate item-wise breakdown
		items_breakdown = []
		total_consumed = 0
		
		for source_item in source_items:
			item_code = source_item.item_code
			source_qty = source_item.qty or 0
			
			# Get consumed quantity across all child doctypes
			consumed_qty = 0
			for child_doctype in PROCUREMENT_DOCTYPES:
				consumed = get_consumed_quantities(doctype, docname, child_doctype)
				consumed_qty += consumed.get(item_code, 0)
			
			available_qty = source_qty - consumed_qty
			total_consumed += consumed_qty
			
			items_breakdown.append({
				"item_code": item_code,
				"source_qty": source_qty,
				"consumed": consumed_qty,
				"available": available_qty
			})
		
		analysis["items_breakdown"] = items_breakdown
		
		# Calculate completion rate
		if total_source_qty > 0:
			analysis["completion_rate"] = round((total_consumed / total_source_qty) * 100, 1)
		
	except Exception as e:
		frappe.log_error(
			title=f"Error getting procurement analysis - {doctype} {docname}",
			message=frappe.get_traceback()
		)
	
	return analysis


@frappe.whitelist()
def make_procurement_document(source_name, target_doctype=None, **kwargs):
	"""
	Create a new procurement document from a source document.
	This is called when user clicks 'Create' button.
	
	UPDATED: Enhanced to ensure ALL items are copied from source.
	"""
	# Extract target_doctype from different possible sources
	if not target_doctype:
		# Try to get from kwargs first
		target_doctype = kwargs.get('target_doctype')
	
	if not target_doctype:
		# Try to get from frappe.form_dict (request context)
		target_doctype = frappe.form_dict.get('target_doctype')
	
	if not target_doctype:
		frappe.throw(_("Target document type is required. Received args: source_name={0}, kwargs={1}, form_dict={2}").format(
			source_name, kwargs, frappe.form_dict
		))
	
	# Determine source doctype from document name
	# In Frappe, we need to find which doctype this document belongs to
	source_doctype = None
	for doctype in PROCUREMENT_DOCTYPES:
		if frappe.db.exists(doctype, source_name):
			source_doctype = doctype
			break
	
	if not source_doctype:
		frappe.throw(_("Source document not found"))
	
	# Get source document
	source_doc = frappe.get_doc(source_doctype, source_name)
	
	# Validate document is submitted
	if source_doc.docstatus != 1:
		frappe.throw(_("Source document {0} must be submitted before creating {1}").format(
			source_name, target_doctype
		))
	
	# Validate that target_doctype is the next step
	active_flow = get_active_flow()
	if active_flow:
		next_step = get_next_step(source_doctype, active_flow.name)
		if next_step and next_step.get("doctype_name") != target_doctype:
			frappe.throw(
				_("Invalid target document type. Expected {0} after {1}").format(
					next_step.get("doctype_name"), source_doctype
				)
			)
	
	# Get items field names
	source_items_field = get_items_field_name(source_doctype)
	target_items_field = get_items_field_name(target_doctype)
	
	if not source_items_field or not target_items_field:
		frappe.throw(_("Cannot map items between these document types"))
	
	# Get source items
	source_items = source_doc.get(source_items_field) or []
	if not source_items:
		frappe.throw(_("Source document has no items to copy"))
	
	frappe.logger().info(f"Creating {target_doctype} from {source_doctype} {source_name} with {len(source_items)} items")
	
	# Create new target document
	target_doc = frappe.new_doc(target_doctype)
	
	# Set procurement source fields
	target_doc.procurement_source_doctype = source_doctype
	target_doc.procurement_source_name = source_name
	
	# Copy common header fields
	common_fields = {
		'company': source_doc.get('company'),
		'currency': source_doc.get('currency')
	}
	
	for field, value in common_fields.items():
		if value and target_doc.meta.has_field(field):
			setattr(target_doc, field, value)
	
	# Set date fields based on target doctype
	if target_doctype == "Purchase Requisition":
		target_doc.transaction_date = frappe.utils.today()
		if source_doc.get('schedule_date'):
			target_doc.schedule_date = source_doc.schedule_date
	elif target_doctype == "Request for Quotation":
		target_doc.transaction_date = frappe.utils.today()
		if source_doc.get('schedule_date'):
			target_doc.schedule_date = source_doc.schedule_date
	elif target_doctype == "Purchase Order":
		target_doc.transaction_date = frappe.utils.today()
		target_doc.schedule_date = source_doc.get('schedule_date') or frappe.utils.add_days(frappe.utils.today(), 7)
	elif target_doctype == "Purchase Receipt":
		target_doc.posting_date = frappe.utils.today()
		target_doc.posting_time = frappe.utils.nowtime()
	elif target_doctype == "Purchase Invoice":
		target_doc.posting_date = frappe.utils.today()
		target_doc.posting_time = frappe.utils.nowtime()
	
	# Copy ALL items from source
	items_copied = 0
	for source_item in source_items:
		target_item = {
			"item_code": source_item.item_code,
			"qty": source_item.qty,
			"uom": source_item.uom,
		}
		
		# Copy optional fields that commonly exist
		optional_fields = {
			'item_name': None,
			'description': source_item.item_code,  # Default to item_code
			'rate': 0,
			'warehouse': None,
			'schedule_date': None,
			'project': None,
			'cost_center': None,
			'conversion_factor': 1,
			'stock_uom': None,
			'stock_qty': None
		}
		
		for field, default_value in optional_fields.items():
			if hasattr(source_item, field):
				value = getattr(source_item, field)
				# Only set if target has this field
				if target_doc.meta.get_field(target_items_field):
					child_meta = frappe.get_meta(f"{target_doctype} Item")
					if child_meta and child_meta.has_field(field) and value is not None:
						target_item[field] = value
					elif default_value is not None:
						target_item[field] = default_value
		
		# Append to target document
		target_doc.append(target_items_field, target_item)
		items_copied += 1
	
	frappe.logger().info(f"Copied {items_copied} items to {target_doctype}")
	
	# Validate that items were actually copied
	if items_copied == 0:
		frappe.throw(_("Failed to copy items from source document"))
	
	if items_copied != len(source_items):
		frappe.msgprint(
			_("Warning: Expected {0} items but copied {1}").format(len(source_items), items_copied),
			indicator="orange"
		)
	
	# Return the document as a dict so it can be synced on client side
	return target_doc.as_dict()


@frappe.whitelist()
def get_rfq_pivot_data(rfq_name):
	"""
	Get RFQ data formatted for pivot view.
	Returns items and suppliers for creating a price comparison matrix.
	
	Args:
		rfq_name: RFQ document name
	
	Returns:
		{
			"items": [{"item_code": "...", "item_name": "...", "qty": ..., "uom": "..."}],
			"suppliers": [{"supplier": "...", "supplier_name": "..."}],
			"rfq_name": "...",
			"company": "...",
			"transaction_date": "..."
		}
	"""
	try:
		rfq = frappe.get_doc("Request for Quotation", rfq_name)
		
		# Collect items
		items = []
		for item in rfq.items:
			items.append({
				"item_code": item.item_code,
				"item_name": item.item_name or item.item_code,
				"qty": item.qty,
				"uom": item.uom,
				"description": item.description
			})
		
		# Collect suppliers
		suppliers = []
		for supplier in rfq.suppliers:
			supplier_doc = frappe.get_doc("Supplier", supplier.supplier)
			suppliers.append({
				"supplier": supplier.supplier,
				"supplier_name": supplier_doc.supplier_name or supplier.supplier
			})
		
		return {
			"items": items,
			"suppliers": suppliers,
			"rfq_name": rfq_name,
			"company": rfq.company,
			"transaction_date": rfq.transaction_date or frappe.utils.today(),
			"schedule_date": rfq.schedule_date or frappe.utils.add_days(frappe.utils.today(), 7)
		}
		
	except Exception as e:
		frappe.log_error(
			title=f"Error getting RFQ pivot data - {rfq_name}",
			message=frappe.get_traceback()
		)
		frappe.throw(_("Error loading RFQ data. Check error log for details."))


@frappe.whitelist()
def create_supplier_quotations_from_pivot(rfq_name, pivot_data):
	"""
	Create Supplier Quotations from pivot table data.
	Only creates quotations for suppliers that have at least one item with a price.
	
	Args:
		rfq_name: RFQ document name
		pivot_data: JSON string containing pivot table data
			Format: {
				"supplier1": {
					"item_code1": {"rate": 100, "qty": 10},
					"item_code2": {"rate": 200, "qty": 5}
				},
				"supplier2": {...}
			}
	
	Returns:
		{
			"created": [list of created SQ names],
			"skipped": [list of suppliers skipped (no prices entered)],
			"errors": [list of errors if any]
		}
	"""
	try:
		# Parse pivot data if it's a string
		if isinstance(pivot_data, str):
			import json
			pivot_data = json.loads(pivot_data)
		
		# Get RFQ document
		rfq = frappe.get_doc("Request for Quotation", rfq_name)
		
		created_sqs = []
		skipped_suppliers = []
		errors = []
		
		# Process each supplier
		for supplier, items_data in pivot_data.items():
			try:
				# Filter items that have prices entered
				items_with_prices = []
				for item_code, item_data in items_data.items():
					rate = item_data.get("rate", 0)
					qty = item_data.get("qty", 0)
					
					# Only include items with rate > 0
					if rate and rate > 0:
						# Get original item details from RFQ
						rfq_item = next((i for i in rfq.items if i.item_code == item_code), None)
						if rfq_item:
							items_with_prices.append({
								"item_code": item_code,
								"item_name": rfq_item.item_name,
								"qty": qty if qty > 0 else rfq_item.qty,
								"rate": rate,
								"uom": rfq_item.uom,
								"description": rfq_item.description,
								"warehouse": rfq_item.warehouse if hasattr(rfq_item, 'warehouse') else None,
								"schedule_date": rfq.schedule_date or frappe.utils.add_days(frappe.utils.today(), 7)
							})
				
				# Skip supplier if no items with prices
				if not items_with_prices:
					skipped_suppliers.append(supplier)
					continue
				
				# Create Supplier Quotation
				sq = frappe.get_doc({
					"doctype": "Supplier Quotation",
					"supplier": supplier,
					"company": rfq.company,
					"transaction_date": frappe.utils.today(),
					"valid_till": frappe.utils.add_days(frappe.utils.today(), 30),
					"currency": frappe.db.get_value("Company", rfq.company, "default_currency"),
					"buying_price_list": frappe.db.get_value("Supplier", supplier, "default_price_list"),
					"procurement_source_doctype": "Request for Quotation",
					"procurement_source_name": rfq_name,
					"items": []
				})
				
				# Add items to SQ
				for item in items_with_prices:
					sq.append("items", {
						"item_code": item["item_code"],
						"item_name": item["item_name"],
						"qty": item["qty"],
						"rate": item["rate"],
						"uom": item["uom"],
						"description": item["description"],
						"warehouse": item["warehouse"],
						"schedule_date": item["schedule_date"]
					})
				
				# Insert the Supplier Quotation
				sq.insert()
				created_sqs.append(sq.name)
				
			except Exception as e:
				error_msg = f"Error creating SQ for {supplier}: {str(e)}"
				errors.append(error_msg)
				frappe.log_error(
					title=f"Error creating Supplier Quotation - {supplier}",
					message=f"RFQ: {rfq_name}\n{frappe.get_traceback()}"
				)
		
		# Commit all changes
		frappe.db.commit()
		
		return {
			"created": created_sqs,
			"skipped": skipped_suppliers,
			"errors": errors
		}
		
	except Exception as e:
		frappe.db.rollback()
		frappe.log_error(
			title=f"Error creating Supplier Quotations from pivot - {rfq_name}",
			message=frappe.get_traceback()
		)
		frappe.throw(_("Error creating Supplier Quotations. Check error log for details."))


@frappe.whitelist()
def submit_supplier_quotations(sq_names):
	"""
	Submit multiple Supplier Quotations.
	
	Args:
		sq_names: JSON string or list of SQ names to submit
	
	Returns:
		{
			"submitted": [list of submitted SQ names],
			"errors": [list of errors if any]
		}
	"""
	try:
		# Parse sq_names if it's a string
		if isinstance(sq_names, str):
			import json
			sq_names = json.loads(sq_names)
		
		submitted = []
		errors = []
		
		for sq_name in sq_names:
			try:
				sq = frappe.get_doc("Supplier Quotation", sq_name)
				sq.submit()
				submitted.append(sq_name)
			except Exception as e:
				error_msg = f"Error submitting {sq_name}: {str(e)}"
				errors.append(error_msg)
				frappe.log_error(
					title=f"Error submitting Supplier Quotation - {sq_name}",
					message=frappe.get_traceback()
				)
		
		frappe.db.commit()
		
		return {
			"submitted": submitted,
			"errors": errors
		}
		
	except Exception as e:
		frappe.db.rollback()
		frappe.log_error(
			title="Error submitting Supplier Quotations",
			message=frappe.get_traceback()
		)
		frappe.throw(_("Error submitting Supplier Quotations. Check error log for details."))



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
		# Log error but don't block the submission if it's just a link creation issue
		frappe.log_error(
			title=f"Procurement Workflow Submit Error - {doc.doctype} {doc.name}",
			message=f"Error creating backward link. Document submitted successfully but link tracking failed.\n{frappe.get_traceback()}"
		)
		# Only re-raise if it's a critical error, not just missing custom fields
		if "procurement_links" not in str(e) and "NoneType" not in str(e):
			raise