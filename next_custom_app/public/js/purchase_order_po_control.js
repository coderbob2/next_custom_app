// Copyright (c) 2026, Nextcore Technologies and contributors
// For license information, please see license.txt

/**
 * Purchase Order - Supplier Validation for Procurement Workflow
 *
 * Quantity control is handled entirely server-side by
 * validate_quantity_limits() in procurement_workflow.py.
 */

frappe.ui.form.on('Purchase Order', {
	onload: function (frm) {
		// If PO is created from Supplier Quotation, set supplier and validate
		if (frm.doc.procurement_source_doctype === 'Supplier Quotation' && frm.doc.procurement_source_name) {
			// Fetch supplier from source SQ if not already set
			if (!frm.doc.supplier) {
				frappe.db.get_value('Supplier Quotation', frm.doc.procurement_source_name, 'supplier')
					.then(r => {
						if (r.message && r.message.supplier) {
							frm.set_value('supplier', r.message.supplier);
						}
					});
			}

			// Make supplier field read-only (must match SQ)
			frm.set_df_property('supplier', 'read_only', 1);
			frm.set_df_property('supplier', 'description', 'Supplier is locked from Supplier Quotation');
		}
	},

	supplier: function (frm) {
		// Validate supplier matches source SQ
		if (frm.doc.procurement_source_doctype === 'Supplier Quotation' && frm.doc.procurement_source_name) {
			validate_supplier_matches_sq(frm);
		}
	}
});


frappe.ui.form.on('Purchase Order Item', {
	items_add: function (frm, cdt, cdn) {
		// Set schedule_date default for new items to avoid null errors
		const item = frappe.get_doc(cdt, cdn);
		if (!item.schedule_date) {
			frappe.model.set_value(cdt, cdn, 'schedule_date', frm.doc.schedule_date || frappe.datetime.add_days(frappe.datetime.now_date(), 7));
		}
	}
});


function validate_supplier_matches_sq(frm) {
	/**
	 * Ensure supplier in PO matches the supplier in source SQ
	 */
	if (!frm.doc.supplier || !frm.doc.procurement_source_name) return;

	frappe.db.get_value('Supplier Quotation', frm.doc.procurement_source_name, 'supplier')
		.then(r => {
			if (r.message && r.message.supplier) {
				const sq_supplier = r.message.supplier;
				if (frm.doc.supplier !== sq_supplier) {
					frappe.msgprint({
						title: __('Supplier Mismatch'),
						message: __('The supplier must match the Supplier Quotation.<br>Expected: <strong>{0}</strong>', [sq_supplier]),
						indicator: 'orange'
					});
					frm.set_value('supplier', sq_supplier);
				}
			}
		});
}
