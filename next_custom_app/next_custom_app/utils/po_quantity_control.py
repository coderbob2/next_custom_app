# Copyright (c) 2026, Nextcore Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt


def setup_rfq_quantity_fields():
	"""
	Add ordered_qty and remaining_qty custom fields to Request for Quotation Item.
	Call this after app installation.
	"""
	from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
	
	custom_fields = {
		"Request for Quotation Item": [
			{
				"fieldname": "column_break_qty_tracking",
				"fieldtype": "Column Break",
				"insert_after": "qty"
			},
			{
				"fieldname": "ordered_qty",
				"label": "Ordered Quantity",
				"fieldtype": "Float",
				"default": "0",
				"read_only": 1,
				"insert_after": "column_break_qty_tracking",
				"description": "Total quantity ordered in Purchase Orders from all Supplier Quotations"
			},
			{
				"fieldname": "remaining_qty",
				"label": "Remaining Quantity",
				"fieldtype": "Float",
				"read_only": 1,
				"insert_after": "ordered_qty",
				"description": "Remaining quantity available for ordering (Qty - Ordered Qty)"
			}
		]
	}
	
	try:
		create_custom_fields(custom_fields, update=True)
		frappe.db.commit()
		frappe.msgprint("RFQ quantity tracking fields created successfully!", indicator="green")
		return True
	except Exception as e:
		frappe.log_error(
			title="Error Creating RFQ Quantity Fields",
			message=f"{str(e)}\n{frappe.get_traceback()}"
		)
		frappe.msgprint(f"Error: {str(e)}", indicator="red")
		return False


def validate_po_against_rfq(doc):
	"""
	Validate Purchase Order quantities against the source RFQ limits.
	This is the main control point to prevent over-ordering beyond RFQ quantities.
	
	Args:
		doc: Purchase Order document
	"""
	# Only validate if PO is from Supplier Quotation
	if doc.doctype != "Purchase Order":
		return
	
	if doc.procurement_source_doctype != "Supplier Quotation":
		return
	
	# Get source Supplier Quotation
	if not doc.procurement_source_name:
		return
	
	try:
		sq = frappe.get_doc("Supplier Quotation", doc.procurement_source_name)
		
		# Check if SQ is from RFQ
		if sq.procurement_source_doctype != "Request for Quotation" or not sq.procurement_source_name:
			return
		
		# Get the source RFQ
		rfq = frappe.get_doc("Request for Quotation", sq.procurement_source_name)
		
		# Validate each item in the PO
		for po_item in doc.items:
			# Find matching RFQ item
			rfq_item = next((i for i in rfq.items if i.item_code == po_item.item_code), None)
			if not rfq_item:
				continue
			
			# Get current ordered quantity from RFQ item
			current_ordered_qty = flt(rfq_item.ordered_qty)
			rfq_total_qty = flt(rfq_item.qty)
			po_qty = flt(po_item.qty)
			
			# Calculate what the total would be after this PO
			# If updating existing PO, we need to exclude its current quantity
			existing_po_qty = 0
			if not doc.is_new():
				# Get the original PO to find what was already counted
				try:
					original_po = frappe.get_doc("Purchase Order", doc.name)
					original_item = next((i for i in original_po.items if i.item_code == po_item.item_code), None)
					if original_item:
						existing_po_qty = flt(original_item.qty)
				except:
					pass
			
			# Calculate available quantity
			available_qty = rfq_total_qty - current_ordered_qty + existing_po_qty
			
			# Validate
			if po_qty > available_qty:
				# Calculate dynamically from all POs for better error message
				all_pos_qty = calculate_rfq_ordered_quantities_dynamic(rfq.name)
				actual_consumed = all_pos_qty.get(po_item.item_code, 0)
				
				# Create a styled, professional error message
				error_msg = f"""
<div style="padding: 20px; background: white; border: 2px solid #dc3545; border-radius: 8px; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">
	<h4 style="color: #dc3545; margin: 0 0 15px 0; font-size: 18px; display: flex; align-items: center; gap: 8px;">
		<span style="font-size: 24px;">⚠️</span>
		Quantity Exceeds RFQ Limit
	</h4>
	
	<div style="background: #fff3cd; padding: 15px; border-left: 4px solid #ffc107; border-radius: 4px; margin-bottom: 20px;">
		<p style="margin: 0; color: #856404; font-size: 14px; font-weight: 500;">
			Item <strong style="color: #dc3545;">{po_item.item_code}</strong> exceeds available quantity in the source RFQ.
		</p>
	</div>
	
	<table style="width: 100%; border-collapse: collapse; margin: 15px 0;">
		<tr style="border-bottom: 2px solid #e9ecef;">
			<td style="padding: 10px 0; color: #495057; font-weight: 500;">Source RFQ:</td>
			<td style="padding: 10px 0; text-align: right;">
				<a href="/app/request-for-quotation/{rfq.name}" target="_blank" style="color: #007bff; font-weight: 600; text-decoration: none;">
					{rfq.name} →
				</a>
			</td>
		</tr>
		<tr style="border-bottom: 1px solid #e9ecef;">
			<td style="padding: 10px 0; color: #495057;">RFQ Quantity:</td>
			<td style="padding: 10px 0; text-align: right;">
				<strong style="color: #28a745; font-size: 16px;">{rfq_total_qty}</strong>
			</td>
		</tr>
		<tr style="border-bottom: 1px solid #e9ecef;">
			<td style="padding: 10px 0; color: #495057;">Already Ordered:</td>
			<td style="padding: 10px 0; text-align: right;">
				<strong style="color: #ffc107; font-size: 16px;">{actual_consumed}</strong>
			</td>
		</tr>
		<tr style="border-bottom: 1px solid #e9ecef;">
			<td style="padding: 10px 0; color: #495057;">Available to Order:</td>
			<td style="padding: 10px 0; text-align: right;">
				<strong style="color: {'#dc3545' if available_qty <= 0 else '#28a745'}; font-size: 16px;">{available_qty}</strong>
			</td>
		</tr>
		<tr>
			<td style="padding: 10px 0; color: #495057;">This PO Quantity:</td>
			<td style="padding: 10px 0; text-align: right;">
				<strong style="color: #dc3545; font-size: 16px;">{po_qty}</strong>
			</td>
		</tr>
	</table>
	
	<div style="background: #e7f3ff; padding: 15px; border-left: 4px solid #2490ef; border-radius: 4px; margin-top: 20px;">
		<p style="margin: 0; color: #004085; font-size: 14px;">
			<strong>💡 Solution:</strong> {f'Reduce the quantity to <strong>{available_qty}</strong> or less' if available_qty > 0 else 'All quantities have been ordered. Increase the RFQ quantity if you need to order more.'}
		</p>
	</div>
</div>
"""
				
				frappe.throw(error_msg, title=f"Quantity Exceeded: {po_item.item_code}")
				
	except frappe.DoesNotExistError as e:
		frappe.log_error(
			title=f"Document Not Found in PO Validation",
			message=f"PO: {doc.name}\nError: {str(e)}\n{frappe.get_traceback()}"
		)
	except Exception as e:
		frappe.log_error(
			title=f"Error Validating PO Against RFQ - {doc.name}",
			message=frappe.get_traceback()
		)
		# Re-raise to prevent saving invalid data
		raise


def update_rfq_ordered_qty(po_doc, action="add"):
	"""
	Update the ordered_qty in RFQ items when a Purchase Order is submitted or cancelled.
	
	Args:
		po_doc: Purchase Order document
		action: "add" (on submit) or "subtract" (on cancel)
	"""
	if po_doc.doctype != "Purchase Order":
		return
	
	if po_doc.procurement_source_doctype != "Supplier Quotation":
		return
	
	try:
		# Get Supplier Quotation
		sq = frappe.get_doc("Supplier Quotation", po_doc.procurement_source_name)
		
		# Check if SQ is from RFQ
		if sq.procurement_source_doctype != "Request for Quotation" or not sq.procurement_source_name:
			return
		
		# Get RFQ and update ordered quantities
		rfq = frappe.get_doc("Request for Quotation", sq.procurement_source_name)
		
		for po_item in po_doc.items:
			# Find matching RFQ item
			for rfq_item in rfq.items:
				if rfq_item.item_code == po_item.item_code:
					po_qty = flt(po_item.qty)
					
					if action == "add":
						rfq_item.ordered_qty = flt(rfq_item.ordered_qty) + po_qty
					elif action == "subtract":
						rfq_item.ordered_qty = max(0, flt(rfq_item.ordered_qty) - po_qty)
					
					# Calculate remaining quantity
					rfq_item.remaining_qty = flt(rfq_item.qty) - flt(rfq_item.ordered_qty)
					
					frappe.logger().info(
						f"Updated RFQ {rfq.name} item {rfq_item.item_code}: "
						f"ordered_qty={rfq_item.ordered_qty}, remaining_qty={rfq_item.remaining_qty}"
					)
					break
		
		# Save RFQ with ignore validations since it's already submitted
		rfq.flags.ignore_validate_update_after_submit = True
		rfq.flags.ignore_permissions = True
		rfq.save()
		frappe.db.commit()
		
		frappe.logger().info(f"Successfully updated RFQ {rfq.name} ordered quantities (action: {action})")
		
	except Exception as e:
		frappe.log_error(
			title=f"Error Updating RFQ Ordered Quantity - PO {po_doc.name}",
			message=f"Action: {action}\n{frappe.get_traceback()}"
		)
		# Don't block the PO submission/cancellation if RFQ update fails
		# Just log the error


def calculate_rfq_ordered_quantities_dynamic(rfq_name):
	"""
	Dynamically calculate ordered quantities from all existing POs linked to an RFQ.
	This is used as a safety net to verify the stored ordered_qty values.
	
	Args:
		rfq_name: RFQ document name
	
	Returns:
		dict: {item_code: ordered_qty}
	"""
	ordered_qtys = {}
	
	try:
		# Get all Supplier Quotations from this RFQ
		sqs = frappe.get_all("Supplier Quotation",
			filters={
				"procurement_source_doctype": "Request for Quotation",
				"procurement_source_name": rfq_name,
				"docstatus": 1  # Only submitted
			},
			pluck="name"
		)
		
		if not sqs:
			return ordered_qtys
		
		# Get all Purchase Orders from these Supplier Quotations
		pos = frappe.get_all("Purchase Order",
			filters={
				"procurement_source_doctype": "Supplier Quotation",
				"procurement_source_name": ["in", sqs],
				"docstatus": ["!=", 2]  # Not cancelled
			},
			fields=["name"]
		)
		
		# Sum up quantities by item
		for po in pos:
			po_doc = frappe.get_doc("Purchase Order", po.name)
			for item in po_doc.items:
				ordered_qtys[item.item_code] = flt(ordered_qtys.get(item.item_code, 0)) + flt(item.qty)
		
	except Exception as e:
		frappe.log_error(
			title=f"Error Calculating RFQ Ordered Quantities - {rfq_name}",
			message=frappe.get_traceback()
		)
	
	return ordered_qtys


@frappe.whitelist()
def get_rfq_available_quantities(rfq_name):
	"""
	Get available quantities for each item in an RFQ (for UI display).
	
	Args:
		rfq_name: RFQ document name
	
	Returns:
		dict: {item_code: {"qty": ..., "ordered_qty": ..., "remaining_qty": ...}}
	"""
	try:
		rfq = frappe.get_doc("Request for Quotation", rfq_name)
		
		result = {}
		for item in rfq.items:
			result[item.item_code] = {
				"qty": flt(item.qty),
				"ordered_qty": flt(item.ordered_qty),
				"remaining_qty": flt(item.qty) - flt(item.ordered_qty)
			}
		
		return result
		
	except Exception as e:
		frappe.log_error(
			title=f"Error Getting RFQ Available Quantities - {rfq_name}",
			message=frappe.get_traceback()
		)
		return {}


def validate_supplier_matches_sq(doc):
	"""
	Validate that PO supplier matches the source Supplier Quotation supplier.
	Auto-sets supplier if empty.
	
	Args:
		doc: Purchase Order document
	"""
	if doc.doctype != "Purchase Order":
		return
	
	if doc.procurement_source_doctype != "Supplier Quotation":
		return
	
	if not doc.procurement_source_name:
		return
	
	try:
		sq = frappe.get_doc("Supplier Quotation", doc.procurement_source_name)
		
		if not doc.supplier:
			# Auto-set supplier from SQ
			doc.supplier = sq.supplier
			frappe.logger().info(f"Auto-set supplier to {sq.supplier} from SQ {sq.name}")
			return
		
		# Validate supplier matches
		if doc.supplier != sq.supplier:
			error_msg = f"""
<div style="padding: 20px; background: white; border: 2px solid #dc3545; border-radius: 8px; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">
	<h4 style="color: #dc3545; margin: 0 0 15px 0; font-size: 18px; display: flex; align-items: center; gap: 8px;">
		<span style="font-size: 24px;">🚫</span>
		Supplier Mismatch
	</h4>
	
	<div style="background: #fff3cd; padding: 15px; border-left: 4px solid #ffc107; border-radius: 4px; margin-bottom: 20px;">
		<p style="margin: 0; color: #856404; font-size: 14px;">
			The Purchase Order supplier must match the Supplier Quotation supplier.
		</p>
	</div>
	
	<table style="width: 100%; border-collapse: collapse; margin: 15px 0;">
		<tr style="border-bottom: 1px solid #e9ecef;">
			<td style="padding: 10px 0; color: #495057;">Supplier Quotation:</td>
			<td style="padding: 10px 0; text-align: right;">
				<a href="/app/supplier-quotation/{sq.name}" target="_blank" style="color: #007bff; font-weight: 600; text-decoration: none;">
					{sq.name} →
				</a>
			</td>
		</tr>
		<tr style="border-bottom: 1px solid #e9ecef;">
			<td style="padding: 10px 0; color: #495057;">Expected Supplier:</td>
			<td style="padding: 10px 0; text-align: right;"><strong style="color: #28a745; font-size: 16px;">{sq.supplier}</strong></td>
		</tr>
		<tr>
			<td style="padding: 10px 0; color: #495057;">Current Supplier:</td>
			<td style="padding: 10px 0; text-align: right;"><strong style="color: #dc3545; font-size: 16px;">{doc.supplier}</strong></td>
		</tr>
	</table>
	
	<div style="background: #e7f3ff; padding: 15px; border-left: 4px solid #2490ef; border-radius: 4px; margin-top: 20px;">
		<p style="margin: 0; color: #004085; font-size: 14px;">
			<strong>💡 Solution:</strong> Change the supplier to <strong>{sq.supplier}</strong> or create the PO from the correct Supplier Quotation.
		</p>
	</div>
</div>
"""
			frappe.throw(error_msg.strip(), title="Supplier Mismatch")
			
	except frappe.DoesNotExistError:
		frappe.log_error(
			title=f"SQ Not Found - {doc.procurement_source_name}",
			message=f"Could not validate supplier for PO {doc.name}"
		)


def on_po_submit(doc, method=None):
	"""Hook called when Purchase Order is submitted"""
	update_rfq_ordered_qty(doc, action="add")


def on_po_cancel(doc, method=None):
	"""Hook called when Purchase Order is cancelled"""
	update_rfq_ordered_qty(doc, action="subtract")


def on_po_validate(doc, method=None):
	"""Hook called when Purchase Order is validated"""
	validate_supplier_matches_sq(doc)
	validate_po_against_rfq(doc)
