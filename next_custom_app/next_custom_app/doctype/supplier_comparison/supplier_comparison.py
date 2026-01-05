# Copyright (c) 2026, Nextcore Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import flt


class SupplierComparison(Document):
	pass


@frappe.whitelist()
def get_supplier_quotations_comparison(rfq_name):
	"""
	Get live comparison data from all submitted Supplier Quotations for an RFQ.
	This is a real-time calculation, not stored data.
	
	Args:
		rfq_name: RFQ document name
	
	Returns:
		{
			"rfq": rfq_data,
			"supplier_quotations": [list of SQs with items],
			"items_comparison": [item-wise comparison],
			"total_comparison": [supplier-wise totals],
			"winner_by_total": supplier_name,
			"winner_by_items": supplier_name
		}
	"""
	try:
		# Get RFQ
		rfq = frappe.get_doc("Request for Quotation", rfq_name)
		
		# Get all submitted Supplier Quotations from this RFQ
		sqs = frappe.get_all("Supplier Quotation",
			filters={
				"procurement_source_doctype": "Request for Quotation",
				"procurement_source_name": rfq_name,
				"docstatus": 1  # Only submitted
			},
			fields=["name", "supplier", "transaction_date", "grand_total"]
		)
		
		if not sqs:
			return {
				"error": "No submitted Supplier Quotations found for this RFQ",
				"rfq": rfq.name
			}
		
		# Build detailed comparison data
		supplier_quotations = []
		supplier_totals = {}
		items_by_supplier = {}  # {item_code: {supplier: {rate, qty, amount}}}
		
		for sq_ref in sqs:
			sq = frappe.get_doc("Supplier Quotation", sq_ref.name)
			supplier = sq.supplier
			
			supplier_quotations.append({
				"name": sq.name,
				"supplier": supplier,
				"date": sq.transaction_date,
				"grand_total": sq.grand_total
			})
			
			supplier_totals[supplier] = {
				"sq_name": sq.name,
				"total": flt(sq.grand_total),
				"items_count": len(sq.items)
			}
			
			# Collect item prices
			for item in sq.items:
				if item.item_code not in items_by_supplier:
					items_by_supplier[item.item_code] = {
						"item_name": item.item_name,
						"qty": item.qty,
						"uom": item.uom
					}
				
				items_by_supplier[item.item_code][supplier] = {
					"rate": flt(item.rate),
					"qty": flt(item.qty),
					"amount": flt(item.amount)
				}
		
		# Calculate item-wise comparison
		items_comparison = []
		item_wise_winners = {}
		
		for item_code, item_data in items_by_supplier.items():
			item_info = {
				"item_code": item_code,
				"item_name": item_data.get("item_name"),
				"qty": item_data.get("qty"),
				"uom": item_data.get("uom"),
				"suppliers": {}
			}
			
			best_rate = None
			best_supplier = None
			total_rate = 0
			rate_count = 0
			
			for supplier in supplier_totals.keys():
				if supplier in item_data:
					rate = item_data[supplier]["rate"]
					qty = item_data[supplier]["qty"]
					amount = item_data[supplier]["amount"]
					
					item_info["suppliers"][supplier] = {
						"rate": rate,
						"qty": qty,
						"amount": amount
					}
					
					# Track best rate
					if best_rate is None or rate < best_rate:
						best_rate = rate
						best_supplier = supplier
					
					total_rate += rate
					rate_count += 1
				else:
					item_info["suppliers"][supplier] = None
			
			item_info["best_rate"] = best_rate
			item_info["best_supplier"] = best_supplier
			item_info["avg_rate"] = total_rate / rate_count if rate_count > 0 else 0
			
			items_comparison.append(item_info)
			
			# Track winner by item
			if best_supplier:
				item_wise_winners[best_supplier] = item_wise_winners.get(best_supplier, 0) + 1
		
		# Rank suppliers by total
		sorted_suppliers = sorted(supplier_totals.items(), key=lambda x: x[1]["total"])
		for rank, (supplier, data) in enumerate(sorted_suppliers, 1):
			supplier_totals[supplier]["rank"] = rank
		
		# Winner by total price
		winner_by_total = sorted_suppliers[0][0] if sorted_suppliers else None
		
		# Winner by item-wise (most items won)
		winner_by_items = max(item_wise_winners.items(), key=lambda x: x[1])[0] if item_wise_winners else None
		
		return {
			"rfq": {
				"name": rfq.name,
				"company": rfq.company,
				"transaction_date": rfq.transaction_date
			},
			"supplier_quotations": supplier_quotations,
			"items_comparison": items_comparison,
			"supplier_totals": supplier_totals,
			"winner_by_total": winner_by_total,
			"winner_by_items": winner_by_items,
			"comparison_summary": {
				"total_suppliers": len(supplier_quotations),
				"total_items": len(items_comparison),
				"best_total_price": sorted_suppliers[0][1]["total"] if sorted_suppliers else 0,
				"worst_total_price": sorted_suppliers[-1][1]["total"] if sorted_suppliers else 0
			}
		}
		
	except Exception as e:
		frappe.log_error(
			title=f"Error in Supplier Quotations Comparison - {rfq_name}",
			message=frappe.get_traceback()
		)
		frappe.throw(f"Error generating comparison: {str(e)}")


@frappe.whitelist()
def award_supplier(rfq_name, supplier, award_type="total"):
	"""
	Award a supplier and optionally create Purchase Order.
	
	Args:
		rfq_name: RFQ document name
		supplier: Winning supplier
		award_type: "total" or "itemwise"
	
	Returns:
		Result message and optional PO name
	"""
	try:
		# Get the supplier's quotation
		sq = frappe.get_value("Supplier Quotation", {
			"procurement_source_doctype": "Request for Quotation",
			"procurement_source_name": rfq_name,
			"supplier": supplier,
			"docstatus": 1
		}, "name")
		
		if not sq:
			frappe.throw(f"No submitted Supplier Quotation found for supplier {supplier}")
		
		return {
			"success": True,
			"supplier": supplier,
			"supplier_quotation": sq,
			"message": f"Supplier {supplier} awarded for RFQ {rfq_name}",
			"award_type": award_type
		}
		
	except Exception as e:
		frappe.log_error(
			title=f"Error Awarding Supplier - {rfq_name}",
			message=frappe.get_traceback()
		)
		frappe.throw(f"Error awarding supplier: {str(e)}")
