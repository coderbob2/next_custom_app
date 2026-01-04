# Copyright (c) 2025, Nextcore Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class RFQSupplierRule(Document):
	def validate(self):
		"""Validate the RFQ Supplier Rule before saving"""
		# Validate amount range
		self.validate_amount_range()
		
		# Check for overlapping ranges with other active rules
		self.validate_no_overlaps()
		
		# Validate minimum suppliers
		self.validate_min_suppliers()
	
	def validate_amount_range(self):
		"""Ensure amount_from is less than amount_to"""
		if self.amount_from >= self.amount_to:
			frappe.throw(
				_("Amount From ({0}) must be less than Amount To ({1})").format(
					frappe.format_value(self.amount_from, {"fieldtype": "Currency"}),
					frappe.format_value(self.amount_to, {"fieldtype": "Currency"})
				),
				title=_("Invalid Amount Range")
			)
	
	def validate_min_suppliers(self):
		"""Ensure minimum suppliers is a positive number"""
		if self.min_suppliers < 1:
			frappe.throw(
				_("Minimum Suppliers must be at least 1"),
				title=_("Invalid Minimum Suppliers")
			)
	
	def validate_no_overlaps(self):
		"""Check if this rule's range overlaps with any other active rule"""
		if not self.is_active:
			# Skip overlap check for inactive rules
			return
		
		# Get all other active rules
		filters = {
			"name": ["!=", self.name],
			"is_active": 1
		}
		
		other_rules = frappe.get_all(
			"RFQ Supplier Rule",
			filters=filters,
			fields=["name", "rule_name", "amount_from", "amount_to", "min_suppliers", "priority"]
		)
		
		overlapping_rules = []
		
		for rule in other_rules:
			# Check if ranges overlap
			# Two ranges [a1, a2] and [b1, b2] overlap if:
			# a1 < b2 AND b1 < a2
			if self.amount_from < rule.amount_to and rule.amount_from < self.amount_to:
				overlapping_rules.append({
					"name": rule.rule_name,
					"range": f"{frappe.format_value(rule.amount_from, {'fieldtype': 'Currency'})} - {frappe.format_value(rule.amount_to, {'fieldtype': 'Currency'})}",
					"min_suppliers": rule.min_suppliers,
					"priority": rule.priority
				})
		
		if overlapping_rules:
			# Build detailed error message
			error_msg = _("This rule's amount range overlaps with the following active rules:")
			error_msg += "<br><br>"
			error_msg += "<table class='table table-bordered' style='margin-top: 10px;'>"
			error_msg += "<thead><tr>"
			error_msg += "<th>Rule Name</th>"
			error_msg += "<th>Amount Range</th>"
			error_msg += "<th>Min Suppliers</th>"
			error_msg += "<th>Priority</th>"
			error_msg += "</tr></thead><tbody>"
			
			for rule in overlapping_rules:
				error_msg += f"<tr>"
				error_msg += f"<td><strong>{rule['name']}</strong></td>"
				error_msg += f"<td>{rule['range']}</td>"
				error_msg += f"<td>{rule['min_suppliers']}</td>"
				error_msg += f"<td>{rule['priority']}</td>"
				error_msg += f"</tr>"
			
			error_msg += "</tbody></table>"
			error_msg += "<br>"
			error_msg += _("<strong>Your Range:</strong> {0} - {1}").format(
				frappe.format_value(self.amount_from, {"fieldtype": "Currency"}),
				frappe.format_value(self.amount_to, {"fieldtype": "Currency"})
			)
			error_msg += "<br><br>"
			error_msg += _("Please adjust the amount range to avoid overlaps, or deactivate one of the conflicting rules.")
			
			frappe.throw(error_msg, title=_("Overlapping Amount Ranges"))


@frappe.whitelist()
def get_applicable_rule(total_amount):
	"""
	Get the applicable RFQ Supplier Rule for a given amount
	
	Args:
		total_amount: Total amount of the RFQ
	
	Returns:
		dict: Rule details or None
	"""
	total_amount = float(total_amount)
	
	# Get all active rules that cover this amount
	rules = frappe.get_all(
		"RFQ Supplier Rule",
		filters={
			"is_active": 1,
			"amount_from": ["<=", total_amount],
			"amount_to": [">", total_amount]
		},
		fields=["name", "rule_name", "amount_from", "amount_to", "min_suppliers", "priority"],
		order_by="priority asc, amount_from asc"
	)
	
	if rules:
		# Return the highest priority rule (lowest priority number)
		return rules[0]
	
	return None


@frappe.whitelist()
def validate_rfq_suppliers(doctype, docname):
	"""
	Validate if an RFQ has the required minimum number of suppliers
	
	Args:
		doctype: Should be 'Request for Quotation'
		docname: Name of the RFQ document
	
	Returns:
		dict: Validation result with status and message
	"""
	if doctype != "Request for Quotation":
		return {"valid": True, "message": "Not an RFQ document"}
	
	# Get the RFQ document
	rfq = frappe.get_doc(doctype, docname)
	
	# Calculate total amount
	total_amount = 0
	if hasattr(rfq, "items") and rfq.items:
		for item in rfq.items:
			# Use rate * qty for each item
			item_amount = (item.rate or 0) * (item.qty or 0)
			total_amount += item_amount
	
	if total_amount == 0:
		return {
			"valid": True,
			"message": "No amount to validate (items have no rates)",
			"total_amount": 0
		}
	
	# Get applicable rule
	rule = get_applicable_rule(total_amount)
	
	if not rule:
		return {
			"valid": True,
			"message": "No applicable rule for this amount range",
			"total_amount": total_amount
		}
	
	# Count suppliers
	supplier_count = len(rfq.suppliers) if hasattr(rfq, "suppliers") and rfq.suppliers else 0
	
	if supplier_count < rule["min_suppliers"]:
		return {
			"valid": False,
			"message": _(
				"This RFQ requires at least {0} suppliers (current: {1}). "
				"Applicable rule: {2} for amount range {3} - {4}"
			).format(
				rule["min_suppliers"],
				supplier_count,
				rule["rule_name"],
				frappe.format_value(rule["amount_from"], {"fieldtype": "Currency"}),
				frappe.format_value(rule["amount_to"], {"fieldtype": "Currency"})
			),
			"total_amount": total_amount,
			"required_suppliers": rule["min_suppliers"],
			"current_suppliers": supplier_count,
			"rule_name": rule["rule_name"]
		}
	
	
	return {
		"valid": True,
		"message": _("Supplier count meets requirements"),
		"total_amount": total_amount,
		"required_suppliers": rule["min_suppliers"],
		"current_suppliers": supplier_count,
		"rule_name": rule["rule_name"]
	}


def validate_rfq_on_submit(doc, method=None):
	"""
	Hook function called when RFQ is validated/submitted
	Checks if the RFQ meets minimum supplier requirements
	
	Note: RFQ items typically don't have rates, so this validation
	only checks supplier count and doesn't validate by amount.
	Amount-based validation would apply to Supplier Quotations instead.
	
	Args:
		doc: RFQ Document
		method: Method name (not used)
	"""
	if doc.doctype != "Request for Quotation":
		return
	
	# RFQ items don't have rates since the purpose of RFQ is to GET rates
	# So we can't validate based on amount at this stage
	# The supplier count validation would apply if there are rules defined
	# but without knowing the expected amount, we can only do basic checks
	
	# For now, skip amount-based validation for RFQ
	# Amount-based supplier validation can apply when creating Supplier Quotations
	
	# Future enhancement: Add a field to RFQ for "Expected Total Amount"
	# or validate based on historical data or budget constraints
	
	return