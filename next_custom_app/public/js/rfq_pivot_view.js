/**
 * RFQ Pivot View - Supplier Price Comparison
 * 
 * This script adds a custom button to RFQ to open a pivot view
 * where users can enter prices for each item from each supplier
 * and create supplier quotations in bulk.
 */

frappe.ui.form.on('Request for Quotation', {
	refresh: function(frm) {
		// Only show the button if RFQ is submitted and has items and suppliers
		if (frm.doc.docstatus === 1 && frm.doc.items && frm.doc.items.length > 0 
			&& frm.doc.suppliers && frm.doc.suppliers.length > 0) {
			
			// Add custom button
			frm.add_custom_button(__('Supplier Price Comparison'), function() {
				show_rfq_pivot_view(frm);
			}, __('Create'));
			
			// Set button color to make it stand out
			setTimeout(() => {
				$('.btn-group .btn:contains("Supplier Price Comparison")').addClass('btn-primary');
			}, 100);
		}
	}
});

function show_rfq_pivot_view(frm) {
	console.log('*** Opening RFQ Pivot View for:', frm.doc.name);
	
	// Show loading message
	frappe.show_alert({
		message: __('Loading pivot view...'),
		indicator: 'blue'
	});
	
	// Fetch RFQ data for pivot view
	frappe.call({
		method: 'next_custom_app.next_custom_app.utils.procurement_workflow.get_rfq_pivot_data',
		args: {
			rfq_name: frm.doc.name
		},
		callback: function(r) {
			if (r.message) {
				render_pivot_dialog(frm, r.message);
			}
		},
		error: function(r) {
			frappe.msgprint({
				title: __('Error'),
				message: __('Failed to load RFQ data. Please try again.'),
				indicator: 'red'
			});
		}
	});
}

function render_pivot_dialog(frm, pivot_data) {
	console.log('*** Rendering pivot dialog with data:', pivot_data);
	
	const items = pivot_data.items;
	const suppliers = pivot_data.suppliers;
	
	if (!items || items.length === 0) {
		frappe.msgprint(__('No items found in this RFQ'));
		return;
	}
	
	if (!suppliers || suppliers.length === 0) {
		frappe.msgprint(__('No suppliers found in this RFQ'));
		return;
	}
	
	// Create dialog
	const dialog = new frappe.ui.Dialog({
		title: __('Supplier Price Comparison - {0}', [pivot_data.rfq_name]),
		size: 'extra-large',
		fields: [
			{
				fieldtype: 'HTML',
				fieldname: 'pivot_table_html'
			}
		],
		primary_action_label: __('Create Supplier Quotations'),
		primary_action: function() {
			create_supplier_quotations_from_pivot(frm, dialog, pivot_data);
		},
		secondary_action_label: __('Close')
	});
	
	// Build pivot table HTML
	const pivot_html = build_pivot_table_html(items, suppliers);
	
	// Set the HTML in the dialog
	dialog.fields_dict.pivot_table_html.$wrapper.html(pivot_html);
	
	// Add event listeners for input fields
	setup_pivot_table_events(dialog, items, suppliers);
	
	dialog.show();
}

function build_pivot_table_html(items, suppliers) {
	let html = `
		<style>
			.price-input::-webkit-outer-spin-button,
			.price-input::-webkit-inner-spin-button {
				-webkit-appearance: none;
				margin: 0;
			}
			.price-input[type=number] {
				-moz-appearance: textfield;
			}
		</style>
		<div class="rfq-pivot-container" style="margin: 10px 0;">
			<div style="margin-bottom: 8px; padding: 6px 10px; background: #f0f8ff; border-left: 3px solid #2490ef; font-size: 12px; color: #004085;">
				Enter prices for each item. Only suppliers with prices entered will have quotations created.
			</div>
			
			<div class="table-responsive" style="max-height: 500px; overflow-y: auto; border: 1px solid #ddd;">
				<table class="table table-bordered pivot-table" style="margin: 0; font-size: 13px;">
					<thead style="position: sticky; top: 0; background: #f5f5f5; z-index: 10;">
						<tr>
							<th style="min-width: 150px; padding: 6px 8px; font-weight: 600;">Item Code</th>
							<th style="min-width: 60px; padding: 6px 8px; text-align: center;">Qty</th>
							<th style="min-width: 50px; padding: 6px 8px; text-align: center;">UOM</th>
	`;
	
	// Add supplier column headers
	suppliers.forEach(supplier => {
		html += `<th style="min-width: 120px; padding: 6px 8px; background: #e3f2fd; text-align: center;">${supplier.supplier_name}</th>`;
	});
	
	html += `</tr></thead><tbody>`;
	
	// Add item rows
	items.forEach((item, item_idx) => {
		html += `
			<tr data-item-code="${item.item_code}">
				<td style="padding: 6px 8px;">
					<div style="font-weight: 500;">${item.item_code}</div>
					${item.item_name !== item.item_code ? `<div style="font-size: 11px; color: #666;">${item.item_name}</div>` : ''}
				</td>
				<td style="padding: 6px 8px; text-align: center;">${item.qty}</td>
				<td style="padding: 6px 8px; text-align: center;">${item.uom}</td>
		`;
		
		// Add price input for each supplier
		suppliers.forEach((supplier, supplier_idx) => {
			html += `
				<td style="padding: 4px;">
					<input type="number"
						class="form-control price-input"
						data-item-code="${item.item_code}"
						data-supplier="${supplier.supplier}"
						data-item-idx="${item_idx}"
						data-supplier-idx="${supplier_idx}"
						placeholder="0.00"
						step="0.01"
						min="0"
						style="text-align: right; font-size: 13px; padding: 4px 6px; height: 28px;">
				</td>
			`;
		});
		
		html += `</tr>`;
	});
	
	html += `</tbody></table></div></div>`;
	
	return html;
}

function setup_pivot_table_events(dialog, items, suppliers) {
	// Add focus/blur events for better UX
	dialog.$wrapper.on('focus', '.price-input', function() {
		$(this).css('background-color', '#fff8dc');
	});
	
	dialog.$wrapper.on('blur', '.price-input', function() {
		$(this).css('background-color', '#fafbfc');
		
		// Format the value to 2 decimal places if not empty
		let val = parseFloat($(this).val());
		if (!isNaN(val) && val > 0) {
			$(this).val(val.toFixed(2));
		}
	});
	
	// Add keyboard navigation (Tab/Enter to move to next cell)
	dialog.$wrapper.on('keydown', '.price-input', function(e) {
		if (e.key === 'Enter' || e.key === 'Tab') {
			e.preventDefault();
			const inputs = dialog.$wrapper.find('.price-input');
			const currentIndex = inputs.index(this);
			const nextIndex = e.shiftKey ? currentIndex - 1 : currentIndex + 1;
			
			if (nextIndex >= 0 && nextIndex < inputs.length) {
				inputs.eq(nextIndex).focus().select();
			}
		}
	});
}

function create_supplier_quotations_from_pivot(frm, dialog, pivot_data) {
	console.log('*** Creating Supplier Quotations from pivot data');
	
	// Collect pivot data from input fields
	const pivot_input_data = {};
	let has_any_price = false;
	
	dialog.$wrapper.find('.price-input').each(function() {
		const item_code = $(this).data('item-code');
		const supplier = $(this).data('supplier');
		const rate = parseFloat($(this).val()) || 0;
		
		if (rate > 0) {
			has_any_price = true;
			
			if (!pivot_input_data[supplier]) {
				pivot_input_data[supplier] = {};
			}
			
			// Find the item qty from pivot_data
			const item = pivot_data.items.find(i => i.item_code === item_code);
			
			pivot_input_data[supplier][item_code] = {
				rate: rate,
				qty: item ? item.qty : 0
			};
		}
	});
	
	if (!has_any_price) {
		frappe.msgprint({
			title: __('No Prices Entered'),
			message: __('Please enter at least one price before creating quotations.'),
			indicator: 'orange'
		});
		return;
	}
	
	// Show confirmation dialog
	show_confirmation_dialog(frm, dialog, pivot_input_data, pivot_data);
}

function show_confirmation_dialog(frm, pivot_dialog, pivot_input_data, pivot_data) {
	// Count suppliers with prices
	const suppliers_with_prices = Object.keys(pivot_input_data);
	const total_suppliers = pivot_data.suppliers.length;
	const skipped_suppliers = total_suppliers - suppliers_with_prices.length;
	
	// Build summary HTML
	let summary_html = '<div style="font-family: -apple-system, BlinkMacSystemFont, \'Segoe UI\', Roboto, sans-serif;">';
	
	// Statistics
	summary_html += `
		<div style="display: grid; grid-template-columns: 1fr 1fr; gap: 15px; margin-bottom: 20px;">
			<div style="padding: 15px; background: #e7f3ff; border-left: 4px solid #2490ef; border-radius: 4px;">
				<div style="font-size: 24px; font-weight: bold; color: #2490ef;">${suppliers_with_prices.length}</div>
				<div style="font-size: 12px; color: #666; margin-top: 4px;">Supplier Quotations to Create</div>
			</div>
			<div style="padding: 15px; background: #fff3cd; border-left: 4px solid #ffc107; border-radius: 4px;">
				<div style="font-size: 24px; font-weight: bold; color: #856404;">${skipped_suppliers}</div>
				<div style="font-size: 12px; color: #666; margin-top: 4px;">Suppliers to Skip (No Prices)</div>
			</div>
		</div>
	`;
	
	// Suppliers with quotations to be created
	if (suppliers_with_prices.length > 0) {
		summary_html += '<div style="margin-bottom: 15px;"><strong style="color: #2c3e50;">Quotations to Create:</strong></div>';
		summary_html += '<ul style="margin: 0 0 15px 20px; padding: 0;">';
		
		suppliers_with_prices.forEach(supplier => {
			const item_count = Object.keys(pivot_input_data[supplier]).length;
			const supplier_info = pivot_data.suppliers.find(s => s.supplier === supplier);
			const supplier_name = supplier_info ? supplier_info.supplier_name : supplier;
			
			summary_html += `
				<li style="margin: 5px 0; color: #2c3e50;">
					<strong>${supplier_name}</strong> - ${item_count} item${item_count > 1 ? 's' : ''} with prices
				</li>
			`;
		});
		
		summary_html += '</ul>';
	}
	
	// Skipped suppliers
	if (skipped_suppliers > 0) {
		const skipped_list = pivot_data.suppliers
			.filter(s => !suppliers_with_prices.includes(s.supplier))
			.map(s => s.supplier_name);
		
		summary_html += '<div style="margin-bottom: 10px;"><strong style="color: #856404;">Suppliers to Skip:</strong></div>';
		summary_html += '<ul style="margin: 0 0 15px 20px; padding: 0; color: #666;">';
		
		skipped_list.forEach(name => {
			summary_html += `<li style="margin: 5px 0;">${name}</li>`;
		});
		
		summary_html += '</ul>';
	}
	
	summary_html += '</div>';
	
	// Show confirmation dialog
	frappe.confirm(
		summary_html,
		function() {
			// User confirmed, proceed with creation
			pivot_dialog.hide();
			create_quotations_with_progress(frm, pivot_input_data, pivot_data);
		},
		function() {
			// User cancelled
			console.log('User cancelled quotation creation');
		}
	);
	
	// Customize confirmation dialog title
	setTimeout(() => {
		$('.frappe-confirm-dialog .modal-title').html('<span style="color: #2490ef;">Confirm Supplier Quotation Creation</span>');
	}, 100);
}

function create_quotations_with_progress(frm, pivot_input_data, pivot_data) {
	console.log('*** Creating quotations with progress indicator');
	
	// Show progress indicator
	const progress_dialog = frappe.show_progress(__('Creating Supplier Quotations...'), 0, 100, 
		__('Please wait while quotations are being created...'));
	
	// Call API to create quotations
	frappe.call({
		method: 'next_custom_app.next_custom_app.utils.procurement_workflow.create_supplier_quotations_from_pivot',
		args: {
			rfq_name: pivot_data.rfq_name,
			pivot_data: JSON.stringify(pivot_input_data)
		},
		callback: function(r) {
			progress_dialog.hide();
			
			if (r.message) {
				const result = r.message;
				show_creation_result(frm, result);
			}
		},
		error: function(r) {
			progress_dialog.hide();
			
			frappe.msgprint({
				title: __('Error'),
				message: __('Failed to create Supplier Quotations. Please check the error log.'),
				indicator: 'red'
			});
		}
	});
}

function show_creation_result(frm, result) {
	console.log('*** Creation result:', result);
	
	const created = result.created || [];
	const skipped = result.skipped || [];
	const errors = result.errors || [];
	
	let message = '<div style="font-family: -apple-system, BlinkMacSystemFont, \'Segoe UI\', Roboto, sans-serif;">';
	
	// Success section
	if (created.length > 0) {
		message += `
			<div style="padding: 15px; background: #d4edda; border-left: 4px solid #28a745; border-radius: 4px; margin-bottom: 15px;">
				<div style="font-weight: 600; color: #155724; margin-bottom: 10px;">
					✅ Successfully Created ${created.length} Supplier Quotation${created.length > 1 ? 's' : ''}
				</div>
				<ul style="margin: 0; padding-left: 20px;">
		`;
		
		created.forEach(sq_name => {
			message += `
				<li style="margin: 5px 0;">
					<a href="/app/supplier-quotation/${sq_name}" target="_blank" style="color: #007bff; text-decoration: none; font-weight: 500;">
						${sq_name}
					</a>
				</li>
			`;
		});
		
		message += '</ul></div>';
	}
	
	// Skipped section
	if (skipped.length > 0) {
		message += `
			<div style="padding: 15px; background: #fff3cd; border-left: 4px solid #ffc107; border-radius: 4px; margin-bottom: 15px;">
				<div style="font-weight: 600; color: #856404; margin-bottom: 10px;">
					ℹ️ Skipped ${skipped.length} Supplier${skipped.length > 1 ? 's' : ''} (No Prices Entered)
				</div>
				<ul style="margin: 0; padding-left: 20px; color: #856404;">
		`;
		
		skipped.forEach(supplier => {
			message += `<li style="margin: 5px 0;">${supplier}</li>`;
		});
		
		message += '</ul></div>';
	}
	
	// Errors section
	if (errors.length > 0) {
		message += `
			<div style="padding: 15px; background: #f8d7da; border-left: 4px solid #dc3545; border-radius: 4px;">
				<div style="font-weight: 600; color: #721c24; margin-bottom: 10px;">
					❌ Errors Occurred
				</div>
				<ul style="margin: 0; padding-left: 20px; color: #721c24; font-size: 12px;">
		`;
		
		errors.forEach(error => {
			message += `<li style="margin: 5px 0;">${error}</li>`;
		});
		
		message += '</ul></div>';
	}
	
	// Show option to submit quotations
	if (created.length > 0) {
		message += `
			<div style="margin-top: 20px; padding: 15px; background: #e7f3ff; border-left: 4px solid #2490ef; border-radius: 4px;">
				<p style="margin: 0; color: #004085; font-size: 13px;">
					<strong>💡 Next Step:</strong> Review the created quotations and submit them individually,
					or click the button below to submit all at once.
				</p>
			</div>
		`;
	}
	
	message += '</div>';
	
	// Show result dialog
	const result_dialog = frappe.msgprint({
		title: __('Supplier Quotations Created'),
		message: message,
		indicator: created.length > 0 ? 'green' : 'orange',
		primary_action: created.length > 0 ? {
			label: __('Submit All Quotations'),
			action: function() {
				result_dialog.hide();
				submit_all_quotations(frm, created);
			}
		} : null
	});
	
	// Refresh form to show updated links
	if (created.length > 0) {
		frm.reload_doc();
	}
}

function submit_all_quotations(frm, sq_names) {
	console.log('*** Submitting all quotations:', sq_names);
	
	frappe.confirm(
		__('Are you sure you want to submit all {0} Supplier Quotations?', [sq_names.length]),
		function() {
			// Show progress
			const progress_dialog = frappe.show_progress(__('Submitting Quotations...'), 0, 100);
			
			frappe.call({
				method: 'next_custom_app.next_custom_app.utils.procurement_workflow.submit_supplier_quotations',
				args: {
					sq_names: JSON.stringify(sq_names)
				},
				callback: function(r) {
					progress_dialog.hide();
					
					if (r.message) {
						const result = r.message;
						const submitted = result.submitted || [];
						const errors = result.errors || [];
						
						if (submitted.length > 0) {
							frappe.show_alert({
								message: __('Successfully submitted {0} quotation(s)', [submitted.length]),
								indicator: 'green'
							}, 5);
						}
						
						if (errors.length > 0) {
							frappe.msgprint({
								title: __('Some Submissions Failed'),
								message: errors.join('<br>'),
								indicator: 'orange'
							});
						}
						
						frm.reload_doc();
					}
				},
				error: function() {
					progress_dialog.hide();
					frappe.msgprint({
						title: __('Error'),
						message: __('Failed to submit quotations. Please check the error log.'),
						indicator: 'red'
					});
				}
			});
		}
	);
}

console.log('=== RFQ Pivot View Script Loaded ===');