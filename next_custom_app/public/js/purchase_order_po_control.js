// Copyright (c) 2026, Nextcore Technologies and contributors
// For license information, please see license.txt

/**
 * Purchase Order - Quantity Control & Supplier Validation
 */

frappe.ui.form.on('Purchase Order', {
	onload: function(frm) {
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
	
	refresh: function(frm) {
		// Show RFQ quantity status if PO is from SQ
		if (frm.doc.procurement_source_doctype === 'Supplier Quotation' && frm.doc.procurement_source_name) {
			show_rfq_quantity_status_in_po(frm);
		}
	},
	
	supplier: function(frm) {
		// Validate supplier matches source SQ
		if (frm.doc.procurement_source_doctype === 'Supplier Quotation' && frm.doc.procurement_source_name) {
			validate_supplier_matches_sq(frm);
		}
	}
});


frappe.ui.form.on('Purchase Order Item', {
	items_add: function(frm, cdt, cdn) {
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


function show_rfq_quantity_status_in_po(frm) {
	/**
	 * Show RFQ quantity status for items in PO
	 */
	if (!frm.doc.procurement_source_name) return;
	
	// Get the RFQ through SQ
	frappe.db.get_value('Supplier Quotation', frm.doc.procurement_source_name, 
		['procurement_source_doctype', 'procurement_source_name'])
		.then(r => {
			if (r.message && r.message.procurement_source_doctype === 'Request for Quotation') {
				const rfq_name = r.message.procurement_source_name;
				
				// Fetch RFQ quantities
				frappe.call({
					method: 'next_custom_app.next_custom_app.utils.po_quantity_control.get_rfq_available_quantities',
					args: { rfq_name: rfq_name },
					callback: function(r) {
						if (r.message) {
							display_quantity_indicators(frm, r.message, rfq_name);
						}
					}
				});
			}
		});
}


function display_quantity_indicators(frm, rfq_quantities, rfq_name) {
	/**
	 * Display quantity indicators in the items grid
	 */
	frm.fields_dict.items.grid.wrapper.find('.grid-body .grid-row').each(function(i) {
		const item = frm.doc.items[i];
		if (!item || !item.item_code) return;
		
		const rfq_qty_data = rfq_quantities[item.item_code];
		if (!rfq_qty_data) return;
		
		const remaining = rfq_qty_data.remaining_qty;
		const ordered = rfq_qty_data.ordered_qty;
		const total = rfq_qty_data.qty;
		const item_qty = item.qty || 0;
		
		let indicator_color = 'green';
		let indicator_text = '';
		let alert_icon = '';
		
		if (item_qty > remaining) {
			indicator_color = 'red';
			indicator_text = `Exceeds by ${item_qty - remaining}`;
			alert_icon = '⚠️';
		} else if (remaining === 0) {
			indicator_color = 'orange';
			indicator_text = 'RFQ fully ordered';
			alert_icon = '⚠️';
		} else {
			indicator_color = 'blue';
			indicator_text = `${remaining} available in RFQ`;
		}
		
		// Add indicator
		$(this).find('[data-fieldname="item_code"]').append(
			`<div style="margin-top: 3px; font-size: 10px;">
				<span class="indicator-pill ${indicator_color}">
					${alert_icon} ${indicator_text}
				</span>
				<a href="/app/request-for-quotation/${rfq_name}" target="_blank" 
				   style="margin-left: 5px; font-size: 10px; color: #666;">
					View RFQ →
				</a>
			</div>`
		);
	});
}


console.log('=== Purchase Order Quantity Control Script Loaded ===');
