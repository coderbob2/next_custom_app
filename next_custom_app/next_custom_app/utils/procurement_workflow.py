# Copyright (c) 2025, Nextcore Technologies and contributors
# For license information, please see license.txt

import json
import frappe
from frappe import _
from frappe.utils import now, flt
from frappe.desk.form.linked_with import get_submitted_linked_docs as _core_get_submitted_linked_docs


def _table_has_column(table, column):
	"""Safely check if a DB table has a column (works across Frappe versions)."""
	try:
		# Frappe usually accepts either doctype or table name, but table name is safest here.
		return bool(frappe.db.has_column(table, column))
	except Exception:
		try:
			return column in (frappe.db.get_table_columns(table) or [])
		except Exception:
			return False


# Procurement doctypes that should be tracked
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


def setup_custom_fields():
	"""
	Backward-compatible wrapper – delegates to the centralized module.

	Run: bench --site <site> execute next_custom_app.next_custom_app.custom_fields.setup_all_custom_fields
	"""
	from next_custom_app.next_custom_app.custom_fields import setup_all_custom_fields
	return setup_all_custom_fields()


@frappe.whitelist()
def get_active_flow():
	"""Get the currently active procurement flow"""
	return frappe.db.get_value(
		"Procurement Flow",
		{"is_active": 1},
		["name", "flow_name"],
		as_dict=True
	)


@frappe.whitelist()
def get_procurement_doctypes():
	"""Return the unique list of doctypes defined in the active Procurement Flow.

	Used by the client-side button override script to dynamically determine
	which doctypes should have their default ERPNext "Create" buttons suppressed.

	Returns a list of doctype name strings, e.g.
	["Material Request", "Request for Quotation", "Purchase Order", ...]
	"""
	active_flow = get_active_flow()
	if not active_flow:
		return []

	steps = get_flow_steps(active_flow.name)
	# Deduplicate while preserving step order
	seen = set()
	doctypes = []
	for step in steps:
		dt = step.doctype_name
		if dt not in seen:
			seen.add(dt)
			doctypes.append(dt)
	return doctypes


def get_flow_steps(flow_name):
	"""Get all steps for a specific procurement flow"""
	flow = frappe.get_doc("Procurement Flow", flow_name)
	return sorted(flow.flow_steps, key=lambda x: (x.step_no, x.doctype_name))


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
	"""Get the previous step in the workflow (first matching doctype)"""
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


def get_previous_steps_for_doctype(current_doctype, flow_name=None):
	"""Get all valid previous steps for a doctype (handles parallel steps)."""
	if not flow_name:
		active_flow = get_active_flow()
		if not active_flow:
			return []
		flow_name = active_flow.name
	
	steps = get_flow_steps(flow_name)
	current_steps = [step for step in steps if step.doctype_name == current_doctype]
	if not current_steps:
		return []
	
	min_step_no = min(step.step_no for step in current_steps)
	prev_step_no = min_step_no - 1
	if prev_step_no < 1:
		return []
	
	return [step for step in steps if step.step_no == prev_step_no]


@frappe.whitelist()
def get_next_step(current_doctype, flow_name=None):
	"""Get the next step in the workflow (first match)."""
	next_steps = get_next_steps(current_doctype, flow_name)
	return next_steps[0] if next_steps else None


@frappe.whitelist()
def get_next_steps(current_doctype, flow_name=None):
	"""Get all next steps in the workflow (parallel steps supported).

	When the current doctype belongs to a ``step_group``, only next steps
	in the **same** group (or with no group) are returned.  This ensures
	that, for example, Purchase Receipt only shows "Create Purchase Invoice"
	and Payment Request only shows "Create Payment Entry".

	When the current doctype has **no** step_group (e.g. Purchase Order at
	step 5), all next steps are returned regardless of their group.
	"""
	if not flow_name:
		active_flow = get_active_flow()
		if not active_flow:
			return []
		flow_name = active_flow.name
	
	steps = get_flow_steps(flow_name)
	current_steps = [step for step in steps if step.doctype_name == current_doctype]
	if not current_steps:
		return []
	
	# Determine the step_group(s) of the current doctype
	current_groups = {
		getattr(step, "step_group", None)
		for step in current_steps
	}
	current_groups.discard(None)
	current_groups.discard("")
	
	current_step_no = min(step.step_no for step in current_steps)
	next_step_no = current_step_no + 1
	next_steps = [step for step in steps if step.step_no == next_step_no]
	
	# If the current doctype belongs to a step_group, filter next steps
	# to only those in the same group (or with no group assigned).
	if current_groups:
		filtered = []
		for step in next_steps:
			step_group = getattr(step, "step_group", None) or ""
			if not step_group or step_group in current_groups:
				filtered.append(step)
		next_steps = filtered
	
	return [
		{
			"doctype_name": step.doctype_name,
			"step_no": step.step_no,
			"requires_source": step.requires_source,
			"is_final_step": getattr(step, "is_final_step", 0),
			"step_group": getattr(step, "step_group", None),
			"role": getattr(step, "role", None) or ""
		}
		for step in next_steps
	]


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
		# If both are empty, the workflow requires a source — block the save
		if not has_source_doctype and not has_source_name:
			previous_steps = get_previous_steps_for_doctype(doc.doctype, active_flow.name)
			expected_sources = ", ".join(sorted({s.doctype_name for s in previous_steps})) if previous_steps else "a previous step document"
			frappe.throw(
				_("A source document is required to create {0}. "
				  "Please create this document from {1} using the workflow Create button.").format(
					doc.doctype, expected_sources
				),
				title=_("Source Document Required")
			)
		
		# If only one is set, that's an error - both must be set or both empty
		if has_source_doctype != has_source_name:
			frappe.throw(
				_("Both source document type and name must be provided together.")
			)
	
	# If source fields are set, validate that source is from a valid previous step
	if has_source_doctype and has_source_name:
		previous_steps = get_previous_steps_for_doctype(doc.doctype, active_flow.name)
		if previous_steps:
			allowed_sources = {step.doctype_name for step in previous_steps}
			if doc.procurement_source_doctype not in allowed_sources:
				frappe.throw(
					_("Invalid source document. Expected one of {0}, but got {1}").format(
						", ".join(sorted(allowed_sources)),
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
	- Supplier Quotation: Skipped - multiple SQs quote for same quantities from different suppliers
	- Purchase Order: Tracks against original RFQ (not Supplier Quotation) to prevent over-allocation across suppliers
	- Stock Entry: Validates against parallel steps (e.g., Purchase Requisition) to prevent over-allocation
	
	PARALLEL STEP VALIDATION:
	For documents in parallel steps (same step_no but different doctypes), this function aggregates
	consumed quantities across all parallel documents. For example, if Material Request has 10 qty for
	item 1, and Purchase Requisition consumes 5 qty in the same step, then Stock Entry (if in same step)
	can only transfer the remaining 5 qty.
	"""
	# Stock Entry created via standard ERPNext routes may not have procurement_source_*.
	# Try to infer from Material Request references before skipping.
	if not doc.get("procurement_source_doctype") or not doc.get("procurement_source_name"):
		if doc.doctype == "Stock Entry":
			normalize_procurement_source(doc)
		# Still missing -> nothing to validate here.
		if not doc.get("procurement_source_doctype") or not doc.get("procurement_source_name"):
			return
	
	# Skip quantity validation for RFQ - we're collecting quotes from multiple suppliers
	# for the same items, not consuming quantities
	if doc.doctype == "Request for Quotation":
		frappe.logger().info(f"Skipping quantity validation for RFQ {doc.name} - multiple suppliers quote for same items")
		return
	
	# Skip quantity validation for Supplier Quotation - multiple suppliers quote for same quantities
	# Quantity control happens at Purchase Order level
	if doc.doctype == "Supplier Quotation":
		# Still validate supplier is in source RFQ if applicable
		if doc.procurement_source_doctype == "Request for Quotation":
			validate_supplier_in_rfq(doc)
		frappe.logger().info(f"Skipping quantity validation for Supplier Quotation {doc.name} - control at PO level")
		return
	
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

	# Aggregate requested quantities per item_code (important for Stock Entry which can have duplicates)
	target_requested = {}
	for row in target_items:
		item_code = getattr(row, "item_code", None)
		if not item_code:
			continue
		qty = (getattr(row, "qty", 0) or 0)
		target_requested[item_code] = target_requested.get(item_code, 0) + qty
	
	# Calculate already consumed quantities, excluding current document if it's being updated
	exclude_current = doc.name if not doc.is_new() else None
	
	# Get detailed breakdown for better error messages
	# Use tracking_source for PO to track against RFQ instead of SQ
	# Aggregate parallel step consumption to prevent over-allocation across step branches
	consumed_breakdown = get_parallel_consumed_breakdown(
		tracking_source_doctype,
		tracking_source_name,
		doc.doctype,
		exclude_doc=exclude_current
	)
	
	frappe.logger().info(f"Validating quantities for {doc.doctype} {doc.name}")
	frappe.logger().info(f"Tracking Source: {tracking_source_name}, Consumed breakdown: {consumed_breakdown}")
	
	# Validate each target item_code once
	validated = set()
	for item_code, target_qty in target_requested.items():
		if item_code in validated:
			continue
		validated.add(item_code)

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
					dt = doc_info.get("doctype") or doc.doctype
					doc_link = f"/app/{dt.lower().replace(' ', '-')}/{doc_info['name']}"
					breakdown_html += f"""
					<li style="margin: 5px 0;">
					<strong>{doc_info['qty']}</strong>
					(<a href="{doc_link}" target="_blank" style="color: #007bff;">{dt}: {doc_info['name']}</a>)
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
						<td style="padding: 6px 0; color: #495057;">Your Total Request (this document):</td>
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
					<strong>💡 Tip:</strong> Reduce total quantity for <strong>{item_code}</strong> to <strong>{available_qty}</strong> or less
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


def validate_stock_entry_source_alignment(doc):
	"""
	Ensure Stock Entry purpose/warehouses align with the source document.
	Also enforces that Stock Entry must have a source document when workflow requires it.
	"""
	if doc.doctype != "Stock Entry":
		return
	
	# Try to infer source from Material Request references
	normalize_procurement_source(doc)
	
	# Check if active flow requires source document for Stock Entry
	if not doc.get("procurement_source_doctype") or not doc.get("procurement_source_name"):
		active_flow = get_active_flow()
		if active_flow:
			current_step = get_current_step(doc.doctype, active_flow.name)
			if current_step and current_step.requires_source:
				# Get valid previous step doctypes for error message
				previous_steps = get_previous_steps_for_doctype(doc.doctype, active_flow.name)
				if previous_steps:
					allowed_sources = [step.doctype_name for step in previous_steps]
					error_msg = f"""
					<div style="padding: 15px; background: white; border: 2px solid #dc3545; border-radius: 6px; margin: 10px 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">
						<h4 style="color: #dc3545; margin: 0 0 12px 0; font-size: 16px;">
							⚠️ Source Document Required
						</h4>
						
						<div style="background: #fff3cd; padding: 12px; border-left: 4px solid #ffc107; border-radius: 4px; margin-bottom: 15px;">
							<p style="margin: 0; color: #856404; font-size: 14px;">
								Stock Entry must be created from a source document within the procurement workflow.
							</p>
						</div>
						
						<div style="margin-bottom: 15px;">
							<p style="margin: 0 0 10px 0; font-weight: 600; color: #495057; font-size: 14px;">
								📋 Allowed Source Documents:
							</p>
							<ul style='margin: 5px 0 0 0; padding-left: 20px;'>
								{''.join([f"<li style='margin: 3px 0;'><strong>{dt}</strong></li>" for dt in allowed_sources])}
							</ul>
						</div>
						
						<div style="background: #e7f3ff; padding: 12px; border-radius: 4px;">
							<p style="margin: 0; color: #004085; font-size: 13px;">
								<strong>💡 Tip:</strong> Create this Stock Entry from one of the allowed source document types,
								or update the procurement workflow configuration if manual Stock Entry creation should be allowed.
							</p>
						</div>
					</div>
					"""
					frappe.throw(error_msg, title="Source Document Required")
		return
	
	# Validate purpose/warehouses alignment with source document

	source_doc = frappe.get_doc(doc.procurement_source_doctype, doc.procurement_source_name)
	purpose_value = (
		source_doc.get("material_request_type")
		or source_doc.get("purchase_requisition_type")
		or source_doc.get("purpose")
	)

	if purpose_value and doc.get("stock_entry_type") and doc.stock_entry_type != purpose_value:
		frappe.throw(
			_("Stock Entry Type must match source document purpose ({0}).").format(purpose_value)
		)

	from_wh = source_doc.get("set_from_warehouse") or source_doc.get("from_warehouse")
	to_wh = source_doc.get("set_warehouse") or source_doc.get("to_warehouse")

	if from_wh and doc.get("from_warehouse") and doc.from_warehouse != from_wh:
		frappe.throw(
			_("From Warehouse must match source document ({0}).").format(from_wh)
		)
	if to_wh and doc.get("to_warehouse") and doc.to_warehouse != to_wh:
		frappe.throw(
			_("To Warehouse must match source document ({0}).").format(to_wh)
		)

	items = doc.get("items") or []
	for item in items:
		if from_wh and getattr(item, "s_warehouse", None) and item.s_warehouse != from_wh:
			frappe.throw(
				_("Item {0} Source Warehouse must match source document ({1}).").format(
					item.item_code,
					from_wh,
				)
			)
		if to_wh and getattr(item, "t_warehouse", None) and item.t_warehouse != to_wh:
			frappe.throw(
				_("Item {0} Target Warehouse must match source document ({1}).").format(
					item.item_code,
					to_wh,
				)
			)


def normalize_procurement_source(doc):
	"""Normalize procurement source fields for Stock Entry from standard references."""
	if doc.doctype != "Stock Entry":
		return
	if doc.get("procurement_source_doctype") and doc.get("procurement_source_name"):
		return
	if doc.get("material_request"):
		doc.procurement_source_doctype = "Material Request"
		doc.procurement_source_name = doc.material_request
		return
	# Some ERPNext versions/flows use material_request_no on Stock Entry
	if doc.get("material_request_no"):
		doc.procurement_source_doctype = "Material Request"
		doc.procurement_source_name = doc.material_request_no
		return
	if doc.get("purchase_requisition"):
		doc.procurement_source_doctype = "Purchase Requisition"
		doc.procurement_source_name = doc.purchase_requisition
		return
	if doc.get("purchase_receipt_no"):
		doc.procurement_source_doctype = "Purchase Receipt"
		doc.procurement_source_name = doc.purchase_receipt_no
		return


def normalize_buying_chain_references(doc):
	"""Ensure ERPNext buying-link fields exist on generated docs.

	Without these fields, ERPNext can't update received/billed status correctly.
	"""
	if doc.doctype == "Purchase Receipt" and doc.get("procurement_source_doctype") == "Purchase Order":
		for item in doc.get("items") or []:
			if not item.get("purchase_order"):
				item.purchase_order = doc.get("procurement_source_name")
			if not item.get("purchase_order_item"):
				po_item = frappe.db.get_value(
					"Purchase Order Item",
					{
						"parent": doc.get("procurement_source_name"),
						"item_code": item.get("item_code"),
					},
					"name",
				)
				if po_item:
					item.purchase_order_item = po_item

	if doc.doctype == "Purchase Invoice" and doc.get("procurement_source_doctype") == "Purchase Receipt":
		source_pr = doc.get("procurement_source_name")
		for item in doc.get("items") or []:
			if not item.get("purchase_receipt"):
				item.purchase_receipt = source_pr

			if not item.get("pr_detail"):
				pr_item = frappe.db.get_value(
					"Purchase Receipt Item",
					{
						"parent": source_pr,
						"item_code": item.get("item_code"),
					},
					"name",
				)
				if pr_item:
					item.pr_detail = pr_item

			if not item.get("purchase_order") or not item.get("po_detail"):
				if item.get("pr_detail"):
					po_vals = frappe.db.get_value(
						"Purchase Receipt Item",
						item.get("pr_detail"),
						["purchase_order", "purchase_order_item"],
						as_dict=True,
					)
					if po_vals:
						if not item.get("purchase_order") and po_vals.get("purchase_order"):
							item.purchase_order = po_vals.purchase_order
						if not item.get("po_detail") and po_vals.get("purchase_order_item"):
							item.po_detail = po_vals.purchase_order_item


@frappe.whitelist()
def backfill_purchase_invoice_receipt_links(purchase_invoice=None):
	"""Backfill missing PR/PO references on submitted Purchase Invoice Items.

	This repairs legacy documents created before proper item-link mapping was added.
	It also recalculates Purchase Receipt billing status after the backfill.
	"""
	filters = {
		"docstatus": 1,
		"procurement_source_doctype": "Purchase Receipt",
	}
	if purchase_invoice:
		filters["name"] = purchase_invoice

	pis = frappe.get_all("Purchase Invoice", filters=filters, fields=["name", "procurement_source_name"])

	total_items_updated = 0
	updated_pi = set()
	touched_pr = set()

	for pi_row in pis:
		source_pr = pi_row.procurement_source_name
		if not source_pr:
			continue

		pi_doc = frappe.get_doc("Purchase Invoice", pi_row.name)
		for item in pi_doc.get("items") or []:
			updates = {}

			if not item.get("purchase_receipt"):
				updates["purchase_receipt"] = source_pr

			pr_item_name = item.get("pr_detail")
			if not pr_item_name:
				pr_item_name = frappe.db.get_value(
					"Purchase Receipt Item",
					{
						"parent": source_pr,
						"item_code": item.get("item_code"),
					},
					"name",
				)
				if pr_item_name:
					updates["pr_detail"] = pr_item_name

			if pr_item_name and (not item.get("purchase_order") or not item.get("po_detail")):
				po_vals = frappe.db.get_value(
					"Purchase Receipt Item",
					pr_item_name,
					["purchase_order", "purchase_order_item"],
					as_dict=True,
				)
				if po_vals:
					if not item.get("purchase_order") and po_vals.get("purchase_order"):
						updates["purchase_order"] = po_vals.purchase_order
					if not item.get("po_detail") and po_vals.get("purchase_order_item"):
						updates["po_detail"] = po_vals.purchase_order_item

			if updates:
				frappe.db.set_value("Purchase Invoice Item", item.name, updates, update_modified=False)
				total_items_updated += 1
				updated_pi.add(pi_row.name)
				touched_pr.add(source_pr)

	# Recompute billed amount from PI -> PR using ERPNext core logic.
	for pi_name in sorted(updated_pi):
		try:
			pi_doc = frappe.get_doc("Purchase Invoice", pi_name)
			pi_doc.update_billing_status_in_pr(update_modified=False)
		except Exception:
			frappe.log_error(
				title=f"PI Billing Refresh Failed - {pi_name}",
				message=frappe.get_traceback(),
			)

	for pr_name in touched_pr:
		try:
			# Force-recompute billed_amt on PR items from submitted PI items.
			pr_items = frappe.get_all(
				"Purchase Receipt Item",
				filters={"parent": pr_name},
				fields=["name"],
			)
			if pr_items:
				pr_item_names = [d.name for d in pr_items]
				rows = frappe.db.sql(
					"""
					SELECT pii.pr_detail, SUM(pii.amount) AS billed_amt
					FROM `tabPurchase Invoice Item` pii
					INNER JOIN `tabPurchase Invoice` pi ON pi.name = pii.parent
					WHERE pi.docstatus = 1
					  AND pii.pr_detail IN %(pr_items)s
					GROUP BY pii.pr_detail
					""",
					{"pr_items": tuple(pr_item_names)},
					as_dict=True,
				)
				billed_map = {r.pr_detail: (r.billed_amt or 0) for r in rows}
				for pr_item_name in pr_item_names:
					frappe.db.set_value(
						"Purchase Receipt Item",
						pr_item_name,
						"billed_amt",
						billed_map.get(pr_item_name, 0),
						update_modified=False,
					)

			pr_doc = frappe.get_doc("Purchase Receipt", pr_name)
			pr_doc.update_billing_status(update_modified=False)
			pr_doc.set_status(update=True)
		except Exception:
			frappe.log_error(
				title=f"PR Billing Status Refresh Failed - {pr_name}",
				message=frappe.get_traceback(),
			)

	frappe.db.commit()

	return {
		"purchase_invoices_updated": sorted(updated_pi),
		"purchase_receipts_refreshed": sorted(touched_pr),
		"items_updated": total_items_updated,
	}
	items = doc.get("items") or []
	for item in items:
		if getattr(item, "material_request", None):
			doc.procurement_source_doctype = "Material Request"
			doc.procurement_source_name = item.material_request
			return
		if getattr(item, "material_request_no", None):
			doc.procurement_source_doctype = "Material Request"
			doc.procurement_source_name = item.material_request_no
			return

		# Some ERPNext flows only set material_request_item (child row link) without setting material_request.
		mr_item = getattr(item, "material_request_item", None)
		if mr_item:
			try:
				mr_parent = frappe.db.get_value("Material Request Item", mr_item, "parent")
			except Exception:
				mr_parent = None
			if mr_parent:
				doc.procurement_source_doctype = "Material Request"
				doc.procurement_source_name = mr_parent
				return


def _get_stock_entry_material_request_candidates(doc):
	"""Return a set of Material Request names referenced by a Stock Entry (header or items)."""
	candidates = set()
	if doc.doctype != "Stock Entry":
		return candidates

	for fn in ("material_request", "material_request_no"):
		val = doc.get(fn)
		if val:
			candidates.add(val)

	for row in (doc.get("items") or []):
		for fn in ("material_request", "material_request_no"):
			val = getattr(row, fn, None)
			if val:
				candidates.add(val)
	return candidates


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


def _has_procurement_source_fields(doctype):
	"""Return True if doctype has procurement_source_* fields."""
	try:
		meta = frappe.get_meta(doctype)
		return bool(meta.has_field("procurement_source_doctype") and meta.has_field("procurement_source_name"))
	except Exception:
		return False


def _get_submitted_procurement_children(parent_doctype, parent_name):
	"""Find direct submitted children using procurement_source_* fields."""
	children = []
	for dt in PROCUREMENT_DOCTYPES:
		if not _has_procurement_source_fields(dt):
			continue

		for row in frappe.get_all(
			dt,
			filters={
				"docstatus": 1,
				"procurement_source_doctype": parent_doctype,
				"procurement_source_name": parent_name,
			},
			fields=["name"],
		):
			children.append({"doctype": dt, "name": row.name})

	return children


def _get_all_submitted_descendants(doctype, docname):
	"""Breadth-first traversal to find all submitted downstream procurement docs."""
	descendants = []
	visited = set()
	queue = [(doctype, docname)]

	while queue:
		current_doctype, current_name = queue.pop(0)
		key = (current_doctype, current_name)
		if key in visited:
			continue
		visited.add(key)

		children = _get_submitted_procurement_children(current_doctype, current_name)
		for child in children:
			child_key = (child["doctype"], child["name"])
			if child_key in visited:
				continue
			descendants.append(child)
			queue.append(child_key)

	return descendants


def _get_procurement_ancestors(doctype, docname):
	"""Return upstream chain based on procurement_source_* fields."""
	ancestors = []
	visited = set()
	current_doctype, current_name = doctype, docname

	while True:
		key = (current_doctype, current_name)
		if key in visited:
			break
		visited.add(key)

		if not _has_procurement_source_fields(current_doctype):
			break

		vals = frappe.db.get_value(
			current_doctype,
			current_name,
			["procurement_source_doctype", "procurement_source_name"],
			as_dict=True,
		)
		if not vals or not vals.get("procurement_source_doctype") or not vals.get("procurement_source_name"):
			break

		source_key = (vals.procurement_source_doctype, vals.procurement_source_name)
		ancestors.append(source_key)
		current_doctype, current_name = source_key

	return ancestors


@frappe.whitelist()
def get_submitted_linked_docs_forward_only(doctype: str, name: str):
	"""
	Override for cancel-all tree to ignore upstream procurement documents.

	Frappe's linked-doc traversal can include tracking/dynamic links that surface
	ancestors (e.g. PI showing PR/PO/Payment Request). For procurement doctypes,
	we keep only true downstream links.
	"""
	result = _core_get_submitted_linked_docs(doctype, name)
	docs = (result or {}).get("docs") or []

	if doctype not in PROCUREMENT_DOCTYPES:
		return result

	ancestor_set = set(_get_procurement_ancestors(doctype, name))
	if not ancestor_set:
		return result

	filtered_docs = []
	for link in docs:
		candidate = (link.get("doctype"), link.get("name"))
		if candidate in ancestor_set:
			continue

		# Payment Request that references an upstream procurement ancestor should
		# not be offered in "Cancel All" for a downstream document.
		if link.get("doctype") == "Payment Request":
			ref = frappe.db.get_value(
				"Payment Request",
				link.get("name"),
				["reference_doctype", "reference_name"],
				as_dict=True,
			)
			if ref and (ref.reference_doctype, ref.reference_name) in ancestor_set:
				continue

		filtered_docs.append(link)

	return {"docs": filtered_docs, "count": len(filtered_docs)}


def check_can_cancel(doc, method=None):
	"""
	ERPNext-style cancellation guard:
	- only block when there are submitted downstream documents
	- downstream is derived from source linkage (procurement_source_*), not child link table
	"""
	# Ignore only the tracking child table in Frappe core backlink checks.
	# This avoids dynamic-link loops from Procurement Document Link while
	# keeping standard ERPNext document-link cancellation behavior intact.
	ignore = doc.get("ignore_linked_doctypes") or []
	if isinstance(ignore, tuple):
		ignore = list(ignore)
	if "Procurement Document Link" not in ignore:
		ignore.append("Procurement Document Link")
	doc.ignore_linked_doctypes = ignore

	active_children = _get_all_submitted_descendants(doc.doctype, doc.name)

	if not active_children:
		return

	docs_by_type = {}
	for child in active_children:
		docs_by_type.setdefault(child["doctype"], []).append(child["name"])

	child_docs_html = ""
	for doctype, doc_names in docs_by_type.items():
		child_docs_html += f"<div style='margin: 8px 0;'>"
		child_docs_html += f"<strong style='color: #495057;'>{doctype}</strong> "
		child_docs_html += f"<span style='background: #e9ecef; padding: 2px 8px; border-radius: 10px; font-size: 11px; font-weight: 600;'>{len(doc_names)}</span>"
		child_docs_html += "<ul style='margin: 5px 0 0 0; padding-left: 20px;'>"
		for child_name in doc_names:
			doc_link = f"/app/{doctype.lower().replace(' ', '-')}/{child_name}"
			child_docs_html += f"""
				<li style="margin: 3px 0;">
					<a href="{doc_link}" target="_blank" style="color: #007bff; text-decoration: none;">
						{child_name}
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
				This document has <strong>{len(active_children)} active downstream document{'s' if len(active_children) > 1 else ''}</strong> that must be cancelled first.
			</p>
		</div>

		<div style="margin-bottom: 15px;">
			<p style="margin: 0 0 10px 0; font-weight: 600; color: #495057; font-size: 14px;">
				📋 Active Downstream Documents:
			</p>
			{child_docs_html}
		</div>

		<div style="background: #e7f3ff; padding: 12px; border-radius: 4px; margin-top: 15px;">
			<p style="margin: 0; color: #004085; font-size: 13px;">
				<strong>💡 Tip:</strong> Cancel the latest documents first, then cancel this document.
			</p>
		</div>
	</div>
	"""

	frappe.throw(error_msg, title="Cancellation Not Allowed")


def on_procurement_cancel(doc, method=None):
	"""
	Re-append ignored tracking table after ERPNext on_cancel overrides
	ignore_linked_doctypes.
	"""
	ignore = doc.get("ignore_linked_doctypes") or []
	if isinstance(ignore, tuple):
		ignore = list(ignore)
	if "Procurement Document Link" not in ignore:
		ignore.append("Procurement Document Link")
	doc.ignore_linked_doctypes = ignore


def get_consumed_quantities_detailed(source_doctype, source_name, target_doctype, exclude_doc=None):
	"""
	Get detailed consumed quantities with document-level breakdown for better error messages.
	Returns a dict of {item_code: {"total": qty, "documents": [{"name": doc_name, "qty": qty, "doctype": doctype}]}}
	
	This function differs from get_consumed_quantities() by including document names for error reporting.
	For Stock Entry, it handles special cases where procurement_source fields may not be set, falling
	back to material_request references in the item child table.
	
	Args:
		source_doctype: The source document type (e.g., "Material Request")
		source_name: The source document name (e.g., "MR-00001")
		target_doctype: The target/child document type (e.g., "Purchase Requisition", "Stock Entry")
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

		# Handle indirect chain: PO → SQ → RFQ
		# When tracking Purchase Order quantities against an RFQ, POs don't point directly
		# to the RFQ — they point to a Supplier Quotation which in turn points to the RFQ.
		# We need to find all POs whose source SQ points to this RFQ.
		if (not child_docs
			and target_doctype == "Purchase Order"
			and source_doctype == "Request for Quotation"):
			# Find all Supplier Quotations from this RFQ
			sqs = frappe.get_all("Supplier Quotation",
				filters={
					"procurement_source_doctype": "Request for Quotation",
					"procurement_source_name": source_name,
					"docstatus": ["!=", 2]
				},
				pluck="name"
			)
			if sqs:
				# Find all POs from these SQs
				child_docs = frappe.get_all("Purchase Order",
					filters={
						"procurement_source_doctype": "Supplier Quotation",
						"procurement_source_name": ["in", sqs],
						"docstatus": ["!=", 2]  # Not cancelled (includes drafts)
					},
					fields=["name"]
				)
				frappe.logger().info(
					f"Found {len(child_docs)} POs via indirect RFQ→SQ→PO chain "
					f"(RFQ: {source_name}, SQs: {sqs})"
				)

		# Fallback for Stock Entry created via standard ERPNext routes (might not have procurement_source fields)
		# Material Request references may exist either on:
		# - Stock Entry Detail.material_request
		# - Stock Entry Detail.material_request_item -> Material Request Item.parent
		# - Stock Entry header material_request/material_request_no (if present)
		if (not child_docs and target_doctype == "Stock Entry" and source_doctype == "Material Request"):
			params = {"mr": source_name}
			exclude_clause = ""
			if exclude_doc:
				exclude_clause = " AND se.name != %(exclude_doc)s"
				params["exclude_doc"] = exclude_doc

			se_mr_field = "se.material_request" if _table_has_column("tabStock Entry", "material_request") else "NULL"
			se_mr_no_field = "se.material_request_no" if _table_has_column("tabStock Entry", "material_request_no") else "NULL"

			rows = frappe.db.sql(
				f"""
				SELECT
					se.name as name,
					sed.item_code as item_code,
					SUM(sed.qty) as qty
				FROM `tabStock Entry` se
				INNER JOIN `tabStock Entry Detail` sed ON sed.parent = se.name
				LEFT JOIN `tabMaterial Request Item` mri ON mri.name = sed.material_request_item
				WHERE se.docstatus != 2
					AND (
						sed.material_request = %(mr)s
						OR mri.parent = %(mr)s
						OR {se_mr_field} = %(mr)s
						OR {se_mr_no_field} = %(mr)s
					)
					{exclude_clause}
				GROUP BY se.name, sed.item_code
				""",
				params,
				as_dict=True,
			)
			for r in rows or []:
				item_code = r.get("item_code")
				qty = r.get("qty") or 0
				name = r.get("name")
				if not item_code or not name:
					continue
				if item_code not in consumed:
					consumed[item_code] = {"total": 0, "documents": []}
				consumed[item_code]["total"] += qty
				consumed[item_code]["documents"].append({
					"name": name,
					"qty": qty,
				})
			return consumed
		
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


def get_parallel_step_doctypes(source_doctype, target_doctype, flow_name=None):
	"""Return doctypes in the same step number as target_doctype (including target)."""
	if not flow_name:
		active_flow = get_active_flow()
		if not active_flow:
			return [target_doctype]
		flow_name = active_flow.name
	
	steps = get_flow_steps(flow_name)
	matching = [step for step in steps if step.doctype_name == target_doctype]
	if not matching:
		return [target_doctype]

	step_groups = {getattr(step, "step_group", None) for step in matching}
	step_groups.discard(None)
	step_groups.discard("")
	if step_groups:
		return [step.doctype_name for step in steps if getattr(step, "step_group", None) in step_groups]

	step_no = min(step.step_no for step in matching)
	return [step.doctype_name for step in steps if step.step_no == step_no]


def get_parallel_consumed_breakdown(source_doctype, source_name, target_doctype, exclude_doc=None, flow_name=None):
	"""Aggregate consumed quantities across all doctypes in the target's step group."""
	consumed = {}
	parallel_doctypes = get_parallel_step_doctypes(source_doctype, target_doctype, flow_name)
	for dt in parallel_doctypes:
		breakdown = get_consumed_quantities_detailed(source_doctype, source_name, dt, exclude_doc=exclude_doc)
		for item_code, info in breakdown.items():
			if item_code not in consumed:
				consumed[item_code] = {"total": 0, "documents": []}
			consumed[item_code]["total"] += info.get("total", 0)
			for doc_info in info.get("documents", []):
				consumed[item_code]["documents"].append({
					"name": doc_info.get("name"),
					"qty": doc_info.get("qty"),
					"doctype": dt
				})
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

		# Handle indirect chain: PO → SQ → RFQ
		# When tracking Purchase Order quantities against an RFQ, POs don't point directly
		# to the RFQ — they point to a Supplier Quotation which in turn points to the RFQ.
		if (not child_docs
			and target_doctype == "Purchase Order"
			and source_doctype == "Request for Quotation"):
			sqs = frappe.get_all("Supplier Quotation",
				filters={
					"procurement_source_doctype": "Request for Quotation",
					"procurement_source_name": source_name,
					"docstatus": ["!=", 2]
				},
				pluck="name"
			)
			if sqs:
				child_docs = frappe.get_all("Purchase Order",
					filters={
						"procurement_source_doctype": "Supplier Quotation",
						"procurement_source_name": ["in", sqs],
						"docstatus": ["!=", 2]
					},
					fields=["name"]
				)

		# Fallback for Stock Entry created without procurement_source fields (standard ERPNext flow)
		if (not child_docs and target_doctype == "Stock Entry" and source_doctype == "Material Request"):
			params = {"mr": source_name}
			exclude_clause = ""
			if exclude_doc:
				exclude_clause = " AND se.name != %(exclude_doc)s"
				params["exclude_doc"] = exclude_doc

			se_mr_field = "se.material_request" if _table_has_column("tabStock Entry", "material_request") else "NULL"
			se_mr_no_field = "se.material_request_no" if _table_has_column("tabStock Entry", "material_request_no") else "NULL"

			rows = frappe.db.sql(
				f"""
				SELECT
					sed.item_code as item_code,
					SUM(sed.qty) as qty
				FROM `tabStock Entry` se
				INNER JOIN `tabStock Entry Detail` sed ON sed.parent = se.name
				LEFT JOIN `tabMaterial Request Item` mri ON mri.name = sed.material_request_item
				WHERE se.docstatus != 2
					AND (
						sed.material_request = %(mr)s
						OR mri.parent = %(mr)s
						OR {se_mr_field} = %(mr)s
						OR {se_mr_no_field} = %(mr)s
					)
					{exclude_clause}
				GROUP BY sed.item_code
				""",
				params,
				as_dict=True,
			)
			for r in rows or []:
				item_code = r.get("item_code")
				qty = r.get("qty") or 0
				if item_code:
					consumed[item_code] = consumed.get(item_code, 0) + qty
			return consumed
		
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
		"Purchase Invoice": "items",
		"Stock Entry": "items"
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
		source_doctype, source_name = _resolve_parent_link(doc, doctype)

		if source_doctype and source_name:
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
					current_doctype, current_name = _resolve_parent_link(parent_doc, current_doctype)
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
					child_docs = []

					# Check if the child doctype actually has procurement_source fields
					# before querying, to avoid OperationalError on missing columns.
					child_has_proc_src = frappe.get_meta(child_doctype).has_field("procurement_source_doctype")

					if child_has_proc_src:
						child_docs = frappe.get_all(
							child_doctype,
							filters={
								"procurement_source_doctype": dt,
								"procurement_source_name": dn,
								"docstatus": ["!=", 2]  # Not cancelled
							},
							fields=["name"]
						)

					# Fallback for Payment Request: also check reference_doctype/reference_name
					# This covers Payment Requests created before procurement_source fields
					# were added, or when they were created via standard ERPNext flow.
					if not child_docs and child_doctype == "Payment Request":
						child_docs = frappe.get_all(
							"Payment Request",
							filters={
								"reference_doctype": dt,
								"reference_name": dn,
								"docstatus": ["!=", 2],
							},
							fields=["name"],
						)

					# Fallback for Stock Entry when procurement_source fields are not set
					if not child_docs and child_doctype == "Stock Entry" and dt == "Material Request":
						# Use SQL so we can also resolve links via material_request_item -> Material Request Item.parent.
						se_mr_field = "se.material_request" if _table_has_column("tabStock Entry", "material_request") else "NULL"
						se_mr_no_field = "se.material_request_no" if _table_has_column("tabStock Entry", "material_request_no") else "NULL"
						rows = frappe.db.sql(
							f"""
							SELECT DISTINCT se.name
							FROM `tabStock Entry` se
							INNER JOIN `tabStock Entry Detail` sed ON sed.parent = se.name
							LEFT JOIN `tabMaterial Request Item` mri ON mri.name = sed.material_request_item
							WHERE se.docstatus != 2
								AND (
									sed.material_request = %(mr)s
									OR mri.parent = %(mr)s
									OR {se_mr_field} = %(mr)s
									OR {se_mr_no_field} = %(mr)s
								)
							""",
							{"mr": dn},
							as_dict=True,
						)
						parent_names = [r.get("name") for r in (rows or []) if r.get("name")]
						if parent_names:
							child_docs = frappe.get_all(
								"Stock Entry",
								filters={
									"name": ["in", parent_names],
									"docstatus": ["!=", 2]
								},
								fields=["name"]
							)

					# Fallback for Payment Entry: check reference_no (set to PR name by ERPNext)
					if not child_docs and child_doctype == "Payment Entry" and dt == "Payment Request":
						child_docs = frappe.get_all(
							"Payment Entry",
							filters={
								"reference_no": dn,
								"docstatus": ["!=", 2],
							},
							fields=["name"],
						)
						# Also check Payment Entry Reference child table
						if not child_docs:
							ref_rows = frappe.get_all(
								"Payment Entry Reference",
								filters={
									"reference_doctype": "Payment Request",
									"reference_name": dn,
									"docstatus": ["!=", 2],
								},
								fields=["parent"],
							)
							if ref_rows:
								pe_names = list(set(r.parent for r in ref_rows))
								child_docs = frappe.get_all(
									"Payment Entry",
									filters={
										"name": ["in", pe_names],
										"docstatus": ["!=", 2],
									},
									fields=["name"],
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


def _resolve_parent_link(doc, current_dt):
	"""
	Resolve the parent (source) document link for a given document.
	Checks procurement_source fields first, then falls back to
	reference_doctype/reference_name for Payment Request and
	reference_no for Payment Entry.
	"""
	source_dt = doc.get("procurement_source_doctype")
	source_name = doc.get("procurement_source_name")

	if source_dt and source_name:
		return source_dt, source_name

	# Fallback: Payment Request uses reference_doctype/reference_name
	if current_dt == "Payment Request":
		ref_dt = doc.get("reference_doctype")
		ref_name = doc.get("reference_name")
		if ref_dt and ref_name:
			return ref_dt, ref_name

	# Fallback: Payment Entry uses reference_no (which is the Payment Request name)
	if current_dt == "Payment Entry":
		ref_no = doc.get("reference_no")
		if ref_no and frappe.db.exists("Payment Request", ref_no):
			return "Payment Request", ref_no

	return None, None


def find_root_document(doctype, docname):
	"""Find the root (topmost) document by traversing backward."""
	current_dt = doctype
	current_name = docname
	max_iterations = 20
	iterations = 0
	
	while iterations < max_iterations:
		try:
			doc = frappe.get_doc(current_dt, current_name)
			parent_dt, parent_name = _resolve_parent_link(doc, current_dt)
			if parent_dt and parent_name:
				current_dt = parent_dt
				current_name = parent_name
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
			parent_dt, parent_name = _resolve_parent_link(doc, current_dt)
			if parent_dt and parent_name:
				current_dt = parent_dt
				current_name = parent_name
				iterations += 1
			else:
				break
		except:
			break
	
	return set(path)


def get_direct_forward_documents(doctype, docname):
	"""Return direct (immediate) child documents for the given node."""
	direct_children = []

	for child_doctype in PROCUREMENT_DOCTYPES:
		try:
			child_docs = []

			child_has_proc_src = frappe.get_meta(child_doctype).has_field("procurement_source_doctype")
			if child_has_proc_src:
				child_docs = frappe.get_all(
					child_doctype,
					filters={
						"procurement_source_doctype": doctype,
						"procurement_source_name": docname,
						"docstatus": ["!=", 2],
					},
					fields=["name"],
				)

			# Legacy fallback for Payment Request links
			if not child_docs and child_doctype == "Payment Request":
				child_docs = frappe.get_all(
					"Payment Request",
					filters={
						"reference_doctype": doctype,
						"reference_name": docname,
						"docstatus": ["!=", 2],
					},
					fields=["name"],
				)

			# Stock Entry fallback for Material Request
			if not child_docs and child_doctype == "Stock Entry" and doctype == "Material Request":
				se_mr_field = "se.material_request" if _table_has_column("tabStock Entry", "material_request") else "NULL"
				se_mr_no_field = "se.material_request_no" if _table_has_column("tabStock Entry", "material_request_no") else "NULL"
				rows = frappe.db.sql(
					f"""
					SELECT DISTINCT se.name
					FROM `tabStock Entry` se
					INNER JOIN `tabStock Entry Detail` sed ON sed.parent = se.name
					LEFT JOIN `tabMaterial Request Item` mri ON mri.name = sed.material_request_item
					WHERE se.docstatus != 2
						AND (
							sed.material_request = %(mr)s
							OR mri.parent = %(mr)s
							OR {se_mr_field} = %(mr)s
							OR {se_mr_no_field} = %(mr)s
						)
					""",
					{"mr": docname},
					as_dict=True,
				)
				parent_names = [r.get("name") for r in (rows or []) if r.get("name")]
				if parent_names:
					child_docs = frappe.get_all(
						"Stock Entry",
						filters={
							"name": ["in", parent_names],
							"docstatus": ["!=", 2],
						},
						fields=["name"],
					)

			# Payment Entry fallback via Payment Request
			if not child_docs and child_doctype == "Payment Entry" and doctype == "Payment Request":
				child_docs = frappe.get_all(
					"Payment Entry",
					filters={
						"reference_no": docname,
						"docstatus": ["!=", 2],
					},
					fields=["name"],
				)

				if not child_docs:
					ref_rows = frappe.get_all(
						"Payment Entry Reference",
						filters={
							"reference_doctype": "Payment Request",
							"reference_name": docname,
							"docstatus": ["!=", 2],
						},
						fields=["parent"],
					)
					if ref_rows:
						pe_names = list(set(r.parent for r in ref_rows))
						child_docs = frappe.get_all(
							"Payment Entry",
							filters={
								"name": ["in", pe_names],
								"docstatus": ["!=", 2],
							},
							fields=["name"],
						)

			for row in child_docs:
				direct_children.append({"doctype": child_doctype, "name": row.name})

		except Exception:
			pass

	return direct_children


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
	
	# Get immediate forward documents (children)
	try:
		direct_children = get_direct_forward_documents(doctype, docname)

		for child in direct_children:
			dt = child["doctype"]
			doc_name = child["name"]
			child_key = f"{dt}::{doc_name}"
			if child_key not in processed:
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
		source_doctype, source_name = _resolve_parent_link(doc, doctype)
		
		node = {
			"doctype": doctype,
			"name": docname,
			"is_current": is_current,
			"is_submitted": doc.docstatus == 1,
			"status": doc.get("status") or ("Submitted" if doc.docstatus == 1 else "Draft"),
			"workflow_state": doc.get("workflow_state"),
			"source_doctype": source_doctype,
			"source_name": source_name,
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


def _set_payment_request_custom_fields(target_doc, target_meta, source_doc):
	"""
	Set custom procurement fields on a Payment Request document during creation.
	Populates: custom_requested_by, custom_requested_by_email, custom_purchase_user,
	and custom_purchase_suspense_account from the current session user.
	"""
	from next_custom_app.next_custom_app.utils.payment_request_utils import (
		_resolve_user_suspense_account,
	)

	current_user = frappe.session.user

	# Set requested_by (full name)
	if target_meta.has_field("custom_requested_by"):
		target_doc.custom_requested_by = frappe.utils.get_fullname(current_user)

	# Set requested_by_email
	if target_meta.has_field("custom_requested_by_email"):
		target_doc.custom_requested_by_email = current_user

	# Set purchase_user
	if target_meta.has_field("custom_purchase_user"):
		target_doc.custom_purchase_user = current_user

	# Resolve and set suspense account
	if target_meta.has_field("custom_purchase_suspense_account"):
		user_data = frappe.db.get_value(
			"User",
			current_user,
			["custom_is_purchaser", "custom_suspense_account"],
			as_dict=True,
		)
		if user_data and user_data.get("custom_is_purchaser") and user_data.get("custom_suspense_account"):
			currency = target_doc.get("currency") or source_doc.get("currency")
			company = target_doc.get("company") or source_doc.get("company")
			suspense_account = _resolve_user_suspense_account(
				purchase_user=current_user,
				parent_suspense=user_data.get("custom_suspense_account"),
				currency=currency,
				company=company,
			)
			if suspense_account:
				target_doc.custom_purchase_suspense_account = suspense_account


def _set_reference_fields(target_doc, source_doctype, source_name, source_doc):
	"""
	Set reference fields on a target document that doesn't have an items table.
	Handles doctypes like Payment Entry, Payment Request, etc.
	
	Tries to set common reference fields like reference_doctype, reference_name,
	party_type, party, paid_amount, etc. based on what the target doctype supports.
	"""
	target_meta = target_doc.meta
	
	# Set reference doctype/name if the target supports it
	if target_meta.has_field("reference_doctype"):
		target_doc.reference_doctype = source_doctype
	if target_meta.has_field("reference_name"):
		target_doc.reference_name = source_name
	
	# Payment Entry specific fields
	if target_meta.has_field("payment_type"):
		# Keep supplier payments as Pay, but enforce Internal Transfer for
		# Payment Requests explicitly routed to Suspense.
		destination = (source_doc.get("custom_payment_destination") or "").strip().lower()
		if source_doctype == "Payment Request" and destination in {"suspense", "internal transfer", "internal_transfer"}:
			target_doc.payment_type = "Internal Transfer"
			# Populate mandatory account fields immediately at create time.
			try:
				from next_custom_app.next_custom_app.utils.payment_request_utils import (
					_get_company_cash_account,
					_get_company_from_reference,
					_resolve_user_suspense_account,
				)
				purchase_user = source_doc.get("custom_purchase_user") or source_doc.get("custom_requested_by_email")
				company = source_doc.get("company") or _get_company_from_reference({
					"reference_doctype": source_doc.get("reference_doctype"),
					"reference_name": source_doc.get("reference_name"),
				})
				currency = source_doc.get("currency") or target_doc.get("paid_to_account_currency") or target_doc.get("paid_from_account_currency")
				parent_suspense = source_doc.get("custom_purchase_suspense_account")
				if purchase_user and not parent_suspense:
					parent_suspense = frappe.db.get_value("User", purchase_user, "custom_suspense_account")
				paid_to_account = _resolve_user_suspense_account(
					purchase_user=purchase_user,
					parent_suspense=parent_suspense,
					currency=currency,
					company=company,
				)
				paid_from_account = _get_company_cash_account(company)
				if paid_from_account and target_meta.has_field("paid_from"):
					target_doc.paid_from = paid_from_account
				if paid_to_account and target_meta.has_field("paid_to"):
					target_doc.paid_to = paid_to_account
				if target_doc.get("paid_from") and target_meta.has_field("paid_from_account_currency"):
					target_doc.paid_from_account_currency = frappe.db.get_value("Account", target_doc.paid_from, "account_currency")
				if target_doc.get("paid_to") and target_meta.has_field("paid_to_account_currency"):
					target_doc.paid_to_account_currency = frappe.db.get_value("Account", target_doc.paid_to, "account_currency")
				if target_meta.has_field("mode_of_payment") and not target_doc.get("mode_of_payment") and frappe.db.exists("Mode of Payment", "Cash"):
					target_doc.mode_of_payment = "Cash"
			except Exception:
				# Final normalization still happens in Payment Entry validate hook.
				pass
		else:
			target_doc.payment_type = "Pay"

	# Resolve Supplier party from source document.
	# For Purchase Order/Invoice this is `supplier`; for Payment Request it's
	# usually `party` when `party_type == Supplier`.
	supplier = None
	supplier_name = None
	if source_doc.get("supplier"):
		supplier = source_doc.get("supplier")
		supplier_name = source_doc.get("supplier_name")
	elif source_doctype == "Payment Request" and source_doc.get("party_type") == "Supplier" and source_doc.get("party"):
		supplier = source_doc.get("party")
		supplier_name = source_doc.get("party_name")

	# Resolve amount from the most reliable source fields.
	amount = (
		source_doc.get("outstanding_amount")
		or source_doc.get("grand_total")
		or source_doc.get("paid_amount")
		or source_doc.get("received_amount")
	)

	if target_meta.has_field("party_type") and supplier:
		target_doc.party_type = "Supplier"
	if target_meta.has_field("party") and supplier:
		target_doc.party = supplier
	if target_meta.has_field("party_name") and supplier_name:
		target_doc.party_name = supplier_name

	# For Internal Transfer (Suspense destination), clear supplier party fields
	# so ERPNext does not try to resolve Supplier None.
	destination = (source_doc.get("custom_payment_destination") or "").strip().lower()
	if target_meta.has_field("payment_type") and target_doc.get("payment_type") == "Internal Transfer":
		if target_meta.has_field("party_type"):
			target_doc.party_type = None
		if target_meta.has_field("party"):
			target_doc.party = None
		if target_meta.has_field("party_name"):
			target_doc.party_name = None
	elif source_doctype == "Payment Request" and destination in {"suspense", "internal transfer", "internal_transfer"}:
		if target_meta.has_field("party_type"):
			target_doc.party_type = None
		if target_meta.has_field("party"):
			target_doc.party = None
		if target_meta.has_field("party_name"):
			target_doc.party_name = None
	if target_meta.has_field("paid_amount") and amount:
		target_doc.paid_amount = amount
	if target_meta.has_field("received_amount") and amount:
		target_doc.received_amount = amount
	if target_meta.has_field("posting_date"):
		target_doc.posting_date = frappe.utils.today()
	
	# Payment Request specific fields
	if target_meta.has_field("grand_total") and source_doc.get("grand_total"):
		target_doc.grand_total = source_doc.grand_total
	elif target_meta.has_field("grand_total") and source_doc.get("rounded_total"):
		target_doc.grand_total = source_doc.rounded_total
	elif target_meta.has_field("grand_total") and source_doc.get("total"):
		target_doc.grand_total = source_doc.total
	if target_meta.has_field("transaction_date"):
		target_doc.transaction_date = frappe.utils.today()

	# Payment Request: map supplier to party fields (critical for PR -> PE supplier flow)
	if target_meta.has_field("party_type") and source_doc.get("supplier"):
		target_doc.party_type = "Supplier"
	if target_meta.has_field("party") and source_doc.get("supplier"):
		target_doc.party = source_doc.supplier
	if target_meta.has_field("party_name") and source_doc.get("supplier_name"):
		target_doc.party_name = source_doc.supplier_name

	# Payment Request: set payment_request_type to Outward
	if target_meta.has_field("payment_request_type"):
		target_doc.payment_request_type = "Outward"

	# Payment Request: set mode_of_payment to Cash if available
	if target_meta.has_field("mode_of_payment") and not target_doc.get("mode_of_payment"):
		if frappe.db.exists("Mode of Payment", "Cash"):
			target_doc.mode_of_payment = "Cash"

	# Payment Request: set custom procurement fields (requested_by, purchase_user, suspense_account)
	_set_payment_request_custom_fields(target_doc, target_meta, source_doc)

	# Payment Request: explicitly copy project and cost_center from PO source
	if source_doctype == "Purchase Order":
		if target_meta.has_field("project") and source_doc.get("project"):
			target_doc.project = source_doc.project
		if target_meta.has_field("cost_center") and source_doc.get("cost_center"):
			target_doc.cost_center = source_doc.cost_center

	# If the target has a "references" child table (like Payment Entry), add a reference row
	if target_meta.has_field("references"):
		ref_row = {
			"reference_doctype": source_doctype,
			"reference_name": source_name,
		}
		if amount:
			ref_row["total_amount"] = amount
			ref_row["allocated_amount"] = amount
			ref_row["outstanding_amount"] = source_doc.get("outstanding_amount") or amount
		if source_doc.get("due_date"):
			ref_row["due_date"] = source_doc.due_date
		target_doc.append("references", ref_row)


@frappe.whitelist()
def make_procurement_document(source_name, target_doctype=None, **kwargs):
	"""
	Create a new procurement document from a source document.
	This is called when user clicks 'Create' button.
	
	UPDATED: Enhanced to ensure ALL items are copied from source.
	Supports non-items doctypes (e.g., Payment Entry) via reference fields.
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

	# Check that the current user has permission to create the target doctype
	if not frappe.has_permission(target_doctype, "create"):
		frappe.throw(
			_("You do not have permission to create {0}").format(target_doctype),
			frappe.PermissionError
		)
	
	# Validate that target_doctype is one of the next steps
	active_flow = get_active_flow()
	if active_flow:
		next_steps = get_next_steps(source_doctype, active_flow.name)
		allowed_next = {step.get("doctype_name") for step in next_steps}
		if allowed_next and target_doctype not in allowed_next:
			frappe.throw(
				_("Invalid target document type. Expected one of {0} after {1}").format(
					", ".join(sorted(allowed_next)), source_doctype
				)
			)
	
	# Get items field names
	source_items_field = get_items_field_name(source_doctype)
	target_items_field = get_items_field_name(target_doctype)
	
	# Check if target doctype supports items mapping.
	# Some doctypes (e.g., Payment Entry, Payment Request) don't have an items
	# child table and need special handling — we create them with reference fields only.
	target_has_items = bool(source_items_field and target_items_field)
	
	if target_has_items:
		# Get source items
		source_items = source_doc.get(source_items_field) or []
		if not source_items:
			frappe.throw(_("Source document has no items to copy"))
		frappe.logger().info(f"Creating {target_doctype} from {source_doctype} {source_name} with {len(source_items)} items")
	else:
		source_items = []
		frappe.logger().info(f"Creating {target_doctype} from {source_doctype} {source_name} (no items mapping — reference-only)")
	
	# Create new target document
	target_doc = frappe.new_doc(target_doctype)
	
	# Set procurement source fields
	target_doc.procurement_source_doctype = source_doctype
	target_doc.procurement_source_name = source_name
	
	# ── Copy common header fields ──
	# These fields are shared across most procurement doctypes.
	# We iterate the list and only set a value when the source has it AND the
	# target doctype's meta declares the same fieldname.
	COMMON_HEADER_FIELDS = [
		# Core
		"company",
		"currency",
		"conversion_rate",
		# Accounting / costing
		"cost_center",
		"project",
		# Pricing
		"buying_price_list",
		"price_list_currency",
		"plc_conversion_rate",
		# Taxes & charges
		"taxes_and_charges",
		"shipping_rule",
		# Discounts
		"apply_discount_on",
		"additional_discount_percentage",
		"discount_amount",
		# Terms & conditions
		"tc_name",
		"terms",
		# Printing
		"letter_head",
		"select_print_heading",
		"language",
		"group_same_items",
		# Warehouse defaults
		"set_warehouse",
		"set_from_warehouse",
		"set_reserve_warehouse",
		# Supplier (when both source and target have the field)
		"supplier",
		"supplier_name",
		"supplier_address",
		"address_display",
		"shipping_address",
		"shipping_address_display",
		"contact_person",
		"contact_display",
		"contact_mobile",
		"contact_email",
		# Payment
		"payment_terms_template",
		# Material Request / Purchase Requisition type
		"material_request_type",
	]

	for field in COMMON_HEADER_FIELDS:
		value = source_doc.get(field)
		if value is not None and value != "" and target_doc.meta.has_field(field):
			setattr(target_doc, field, value)

	# Stock Entry: carry over purpose and warehouse defaults from source
	if target_doctype == "Stock Entry":
		purpose_value = (
			source_doc.get("purpose")
			or source_doc.get("material_request_type")
			or source_doc.get("purchase_requisition_type")
		)
		if purpose_value and target_doc.meta.has_field("purpose"):
			target_doc.purpose = purpose_value
		if purpose_value and target_doc.meta.has_field("stock_entry_type"):
			target_doc.stock_entry_type = purpose_value
		if source_doctype == "Purchase Receipt" and target_doc.meta.has_field("purchase_receipt_no"):
			target_doc.purchase_receipt_no = source_name

		from_wh = source_doc.get("set_from_warehouse") or source_doc.get("from_warehouse")
		to_wh = source_doc.get("set_warehouse") or source_doc.get("to_warehouse")
		if from_wh and target_doc.meta.has_field("from_warehouse"):
			target_doc.from_warehouse = from_wh
		if to_wh and target_doc.meta.has_field("to_warehouse"):
			target_doc.to_warehouse = to_wh
	
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
	
	# Copy ALL items from source (only for doctypes with items tables)
	# For Stock Entry, validate parallel step consumption to prevent over-allocation
	items_copied = 0
	if not target_has_items:
		# Non-items doctype (e.g., Payment Entry, Payment Request)
		# Set reference fields if the target doctype supports them
		_set_reference_fields(target_doc, source_doctype, source_name, source_doc)
		frappe.logger().info(f"Created {target_doctype} with reference to {source_doctype} {source_name}")
		return target_doc.as_dict()
	
	stock_entry_consumed = {}
	if target_doctype == "Stock Entry":
		# Get parallel step consumption (e.g., from Purchase Requisition in same step)
		stock_entry_consumed = get_parallel_consumed_breakdown(
			source_doctype,
			source_name,
			target_doctype
		)
		frappe.logger().info(f"Stock Entry parallel consumption: {stock_entry_consumed}")
	
	for source_item in source_items:
		if target_doctype == "Stock Entry":
			item_code = source_item.item_code
			consumed_info = stock_entry_consumed.get(item_code, {"total": 0})
			source_qty = source_item.qty or 0
			consumed_qty = consumed_info.get("total") or 0
			available_qty = source_qty - consumed_qty
			
			# Skip items with no available quantity (already consumed by parallel steps)
			if available_qty <= 0:
				frappe.logger().info(f"Skipping {item_code}: no available qty (consumed: {consumed_qty}, source: {source_qty})")
				continue
			
			# Use available quantity (respects parallel step consumption)
			adjusted_qty = min(source_qty, available_qty)
			frappe.logger().info(f"Adding {item_code}: adjusted_qty={adjusted_qty} (available: {available_qty})")
		else:
			adjusted_qty = source_item.qty

		target_item = {
			"item_code": source_item.item_code,
			"qty": adjusted_qty,
			"uom": source_item.uom,
		}

		# Get child table meta for target
		child_meta_doctype = f"{target_doctype} Item"
		if target_doctype == "Stock Entry":
			child_meta_doctype = "Stock Entry Detail"
		child_meta = frappe.get_meta(child_meta_doctype)

		# Preserve ERPNext buying chain references so downstream status updates
		# (received/billed) work correctly.
		if target_doctype == "Purchase Receipt" and source_doctype == "Purchase Order":
			if child_meta.has_field("purchase_order"):
				target_item["purchase_order"] = source_name
			if child_meta.has_field("purchase_order_item") and getattr(source_item, "name", None):
				target_item["purchase_order_item"] = source_item.name

		if target_doctype == "Purchase Invoice":
			# PR -> PI (preferred flow)
			if source_doctype == "Purchase Receipt":
				if child_meta.has_field("purchase_receipt"):
					target_item["purchase_receipt"] = source_name
				if child_meta.has_field("pr_detail") and getattr(source_item, "name", None):
					target_item["pr_detail"] = source_item.name

				# Carry PO references from PR Item if available.
				if child_meta.has_field("purchase_order") and getattr(source_item, "purchase_order", None):
					target_item["purchase_order"] = source_item.purchase_order
				if child_meta.has_field("po_detail") and getattr(source_item, "purchase_order_item", None):
					target_item["po_detail"] = source_item.purchase_order_item

			# PO -> PI (fallback flow)
			elif source_doctype == "Purchase Order":
				if child_meta.has_field("purchase_order"):
					target_item["purchase_order"] = source_name
				if child_meta.has_field("po_detail") and getattr(source_item, "name", None):
					target_item["po_detail"] = source_item.name
		
		# Copy optional fields that commonly exist
		optional_fields = [
			'item_name', 'description', 'rate', 'warehouse', 'schedule_date',
			'project', 'cost_center', 'conversion_factor', 'stock_uom', 'stock_qty',
			'image', 'item_group', 'brand', 'manufacturer', 'manufacturer_part_no'
		]
		
		for field in optional_fields:
			if hasattr(source_item, field):
				value = getattr(source_item, field)
				# Only set if target child table has this field and value is not None
				if child_meta and child_meta.has_field(field) and value is not None:
					target_item[field] = value
		
		# Set defaults if not copied
		if 'description' not in target_item or not target_item.get('description'):
			target_item['description'] = source_item.item_code
		if 'conversion_factor' not in target_item:
			target_item['conversion_factor'] = 1
		
		# For Purchase Order, ensure schedule_date is always set to avoid JS errors
		if target_doctype == "Purchase Order" and ('schedule_date' not in target_item or not target_item.get('schedule_date')):
			target_item['schedule_date'] = target_doc.schedule_date or frappe.utils.add_days(frappe.utils.today(), 7)

		# Stock Entry item warehouses and Material Request references
		# CRITICAL: Must set material_request_item to pass ERPNext's validate_with_material_request()
		if target_doctype == "Stock Entry":
			from_wh = source_doc.get("set_from_warehouse") or source_doc.get("from_warehouse")
			to_wh = source_doc.get("set_warehouse") or source_doc.get("to_warehouse")
			if from_wh and child_meta.has_field("s_warehouse"):
				target_item["s_warehouse"] = from_wh
			if to_wh and child_meta.has_field("t_warehouse"):
				target_item["t_warehouse"] = to_wh
			
			# Set Material Request references to satisfy ERPNext validation
			if source_doctype == "Material Request":
				# Set header-level material_request if field exists
				if target_doc.meta.has_field("material_request") and not target_doc.get("material_request"):
					target_doc.material_request = source_name
				
				# Set item-level references
				if child_meta.has_field("material_request"):
					target_item["material_request"] = source_name
				if child_meta.has_field("material_request_item") and getattr(source_item, "name", None):
					target_item["material_request_item"] = source_item.name
			
			# For Purchase Requisition source, try to find the Material Request
			elif source_doctype == "Purchase Requisition":
				if source_doc.get("procurement_source_doctype") == "Material Request":
					mr_name = source_doc.get("procurement_source_name")
					if mr_name:
						# Try to find matching Material Request Item for this item
						mr_doc = frappe.get_doc("Material Request", mr_name)
						mr_item = next((mi for mi in mr_doc.items if mi.item_code == source_item.item_code), None)
						if mr_item:
							if child_meta.has_field("material_request"):
								target_item["material_request"] = mr_name
							if child_meta.has_field("material_request_item"):
								target_item["material_request_item"] = mr_item.name
		
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
		company_currency = frappe.db.get_value("Company", rfq.company, "default_currency")

		# Provide selectable currencies for the pivot dialog
		available_currencies = []
		try:
			available_currencies = frappe.get_all(
				"Currency",
				filters={"enabled": 1},
				pluck="name"
			)
		except Exception:
			available_currencies = []

		if not available_currencies and company_currency:
			available_currencies = [company_currency]
		
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
			"company_currency": company_currency,
			"available_currencies": available_currencies,
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
def create_supplier_quotations_from_pivot(rfq_name, pivot_data, selected_currency=None):
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
		def _find_any_enabled_buying_price_list():
			"""Find any enabled buying price list (compatible with multiple ERPNext versions)."""
			filters = {"enabled": 1}
			if _table_has_column("Price List", "buying"):
				filters["buying"] = 1
			elif _table_has_column("Price List", "selling"):
				filters["selling"] = 0

			return frappe.db.get_value("Price List", filters, "name")

		# Parse pivot data if it's a string
		if isinstance(pivot_data, str):
			import json
			pivot_data = json.loads(pivot_data)
		
		# Get RFQ document
		rfq = frappe.get_doc("Request for Quotation", rfq_name)
		company_currency = frappe.db.get_value("Company", rfq.company, "default_currency")
		quotation_currency = selected_currency or company_currency

		# Get conversion rate from quotation currency to company currency
		conversion_rate = 1.0
		if quotation_currency and company_currency and quotation_currency != company_currency:
			direct_rate = frappe.db.get_value(
				"Currency Exchange",
				{
					"from_currency": quotation_currency,
					"to_currency": company_currency,
				},
				"exchange_rate",
				order_by="date desc"
			)
			if direct_rate:
				conversion_rate = flt(direct_rate)
			else:
				reverse_rate = frappe.db.get_value(
					"Currency Exchange",
					{
						"from_currency": company_currency,
						"to_currency": quotation_currency,
					},
					"exchange_rate",
					order_by="date desc"
				)
				if reverse_rate:
					conversion_rate = 1 / flt(reverse_rate)
		
		created_sqs = []
		skipped_suppliers = []
		errors = []
		
		# Process each supplier
		for supplier, items_data in pivot_data.items():
			try:
				supplier_default_price_list = frappe.db.get_value("Supplier", supplier, "default_price_list")
				price_list_currency = None
				if supplier_default_price_list:
					price_list_currency = frappe.db.get_value("Price List", supplier_default_price_list, "currency")

				# Manual Supplier Quotation form accepts non-company currency even when
				# buying_price_list currency differs (ERPNext handles via conversion rates).
				# Keep pivot behavior aligned with form behavior.
				resolved_buying_price_list = supplier_default_price_list or _find_any_enabled_buying_price_list()

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
				sq_data = {
					"doctype": "Supplier Quotation",
					"supplier": supplier,
					"company": rfq.company,
					"transaction_date": frappe.utils.today(),
					"valid_till": frappe.utils.add_days(frappe.utils.today(), 30),
					"currency": quotation_currency,
					"conversion_rate": conversion_rate,
					"procurement_source_doctype": "Request for Quotation",
					"procurement_source_name": rfq_name,
					"items": []
				}

				if resolved_buying_price_list:
					sq_data["buying_price_list"] = resolved_buying_price_list

				sq = frappe.get_doc({
					**sq_data
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

		if not created_sqs and errors:
			frappe.throw(
				_("No Supplier Quotation was created. Details: {0}").format(" | ".join(errors[:3]))
			)
		
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
		frappe.throw(_("Error creating Supplier Quotations: {0}").format(str(e)))


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



def validate_stock_entry_before_insert(doc, method=None):
	"""
	Emergency validation hook for Stock Entry BEFORE insert.
	This ensures Stock Entry cannot be created without proper source.
	CRITICAL: This is called before the document is saved to database.
	"""
	if doc.doctype != "Stock Entry":
		return
	
	# Try to normalize source from Material Request references
	normalize_procurement_source(doc)
	
	# Check if workflow requires source
	active_flow = get_active_flow()
	if not active_flow:
		return  # No active flow, allow manual creation
	
	current_step = get_current_step(doc.doctype, active_flow.name)
	if not current_step:
		return  # Stock Entry not in workflow
	
	if current_step.requires_source:
		# Source is REQUIRED - block if missing
		if not doc.get("procurement_source_doctype") or not doc.get("procurement_source_name"):
			previous_steps = get_previous_steps_for_doctype(doc.doctype, active_flow.name)
			if previous_steps:
				allowed_sources = [step.doctype_name for step in previous_steps]
				frappe.throw(
					_("CRITICAL: Stock Entry cannot be created without a source document. Workflow configuration requires source from one of: {0}. Please create Stock Entry from {1}.").format(
						", ".join(allowed_sources),
						allowed_sources[0] if len(allowed_sources) == 1 else "one of the allowed documents"
					),
					title="Source Document Required"
				)


def validate_procurement_document(doc, method=None):
	"""
	Main validation hook for procurement documents.
	This is called during the validate event.
	CRITICAL: This function must BLOCK document save if validation fails.
	Only runs when a Procurement Flow is active.
	"""
	# Skip all procurement validations when no flow is active
	active_flow = get_active_flow()
	if not active_flow:
		return

	try:
		# For Stock Entry, run emergency validation first
		if doc.doctype == "Stock Entry":
			validate_stock_entry_before_insert(doc, method)
		
		normalize_procurement_source(doc)
		normalize_buying_chain_references(doc)
		validate_step_order(doc)
		validate_quantity_limits(doc)
		validate_items_against_source(doc)
		validate_stock_entry_source_alignment(doc)
		
		# Final check: ensure procurement_source fields are set if required
		if doc.doctype == "Stock Entry":
			active_flow = get_active_flow()
			if active_flow:
				current_step = get_current_step(doc.doctype, active_flow.name)
				if current_step and current_step.requires_source:
					if not doc.get("procurement_source_doctype") or not doc.get("procurement_source_name"):
						frappe.throw(
							_("CRITICAL: Stock Entry validation failed - source document is required but missing."),
							title="Validation Failed"
						)
	except Exception as e:
		frappe.log_error(
			title=f"Procurement Workflow Validation Error - {doc.doctype} {doc.name}",
			message=frappe.get_traceback()
		)
		# Re-raise to block the save
		raise


def on_procurement_submit(doc, method=None):
	"""
	Hook called when a procurement document is submitted.
	Creates backward links to track the document chain.
	"""
	try:
		# Stock Entry may come from standard ERPNext flows; infer procurement source before linking
		normalize_procurement_source(doc)
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


def on_payment_request_submit(doc, method=None):
	"""
	Hook called when a Payment Request is submitted.
	Creates backward link on the source Purchase Order so that the PO's
	forward links (document flow) show the Payment Request.

	Payment Request uses reference_doctype/reference_name as its source link
	(standard ERPNext fields). We also populate procurement_source_doctype/name
	if the custom fields exist, so the standard procurement workflow logic works.
	"""
	try:
		# Sync procurement_source fields from reference fields if not already set
		if not doc.get("procurement_source_doctype") or not doc.get("procurement_source_name"):
			ref_dt = doc.get("reference_doctype")
			ref_name = doc.get("reference_name")
			if ref_dt and ref_name:
				if doc.meta.has_field("procurement_source_doctype"):
					doc.db_set("procurement_source_doctype", ref_dt, update_modified=False)
				if doc.meta.has_field("procurement_source_name"):
					doc.db_set("procurement_source_name", ref_name, update_modified=False)

		# Determine the source document (PO or other)
		source_dt = doc.get("procurement_source_doctype") or doc.get("reference_doctype")
		source_name = doc.get("procurement_source_name") or doc.get("reference_name")

		if source_dt and source_name:
			create_backward_link(source_dt, source_name, doc.doctype, doc.name)
	except Exception as e:
		frappe.log_error(
			title=f"Payment Request Submit Link Error - {doc.name}",
			message=f"Error creating backward link on source document.\n{frappe.get_traceback()}"
		)


def on_payment_entry_submit(doc, method=None):
	"""
	Hook called when a Payment Entry is submitted.
	Creates backward link on the source Payment Request (or other source)
	so that the document flow shows the Payment Entry.

	Payment Entry may come from:
	1. Payment Request (via reference_no or procurement_source fields)
	2. Purchase Invoice or other documents (via references child table)
	3. Manual creation (no source)
	"""
	try:
		# Try procurement_source fields first
		source_dt = doc.get("procurement_source_doctype")
		source_name = doc.get("procurement_source_name")

		# Fallback: resolve from reference_no (ERPNext sets this to Payment Request name)
		if not source_dt or not source_name:
			ref_no = doc.get("reference_no")
			if ref_no and frappe.db.exists("Payment Request", ref_no):
				source_dt = "Payment Request"
				source_name = ref_no
				# Persist the procurement source fields for future lookups
				if doc.meta.has_field("procurement_source_doctype"):
					doc.db_set("procurement_source_doctype", source_dt, update_modified=False)
				if doc.meta.has_field("procurement_source_name"):
					doc.db_set("procurement_source_name", source_name, update_modified=False)

		if source_dt and source_name:
			create_backward_link(source_dt, source_name, doc.doctype, doc.name)
	except Exception as e:
		frappe.log_error(
			title=f"Payment Entry Submit Link Error - {doc.name}",
			message=f"Error creating backward link on source document.\n{frappe.get_traceback()}"
		)
