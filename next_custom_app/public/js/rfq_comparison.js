// Copyright (c) 2026, Nextcore Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on('Request for Quotation', {
	refresh: function (frm) {
		// Only show for submitted RFQs
		if (frm.doc.docstatus === 1) {
			frm.add_custom_button(__('Compare & Award Suppliers'), () => {
				show_supplier_comparison_dialog(frm);
			}, __('Actions'));
		}
	}
});


function show_supplier_comparison_dialog(frm) {
	/**
	 * Show live comparison dialog for supplier quotations
	 */
	frappe.call({
		method: 'next_custom_app.next_custom_app.doctype.supplier_comparison.supplier_comparison.get_supplier_quotations_comparison',
		args: {
			rfq_name: frm.doc.name
		},
		callback: function (r) {
			if (r.message) {
				if (r.message.error) {
					frappe.msgprint({
						title: __('No Quotations Found'),
						message: r.message.error,
						indicator: 'orange'
					});
					return;
				}

				render_comparison_dialog(frm, r.message);
			}
		}
	});
}


function render_comparison_dialog(frm, comparison_data) {
	/**
	 * Render the comparison dialog with pivot table and winner highlights
	 */
	const default_currency = (comparison_data.currency_meta && comparison_data.currency_meta.company_currency)
		|| frappe.defaults.get_default('currency')
		|| 'USD';
	const comparison_state = {
		selected_currency: default_currency
	};

	const d = new frappe.ui.Dialog({
		title: __('Supplier Quotations Comparison - {0}', [frm.doc.name]),
		size: 'extra-large',
		fields: [
			{
				fieldtype: 'HTML',
				fieldname: 'comparison_html'
			}
		],
		primary_action_label: __('Close'),
		primary_action: function () {
			d.hide();
		}
	});

	// Build HTML for comparison
	let html = build_comparison_html(comparison_data, comparison_state.selected_currency);
	d.fields_dict.comparison_html.$wrapper.html(html);

	// Add event listeners after rendering
	setTimeout(() => {
		attach_comparison_events(d, frm, comparison_data, comparison_state);
	}, 100);

	d.show();
}


function build_comparison_html(data, selected_currency) {
	/**
	 * Build the HTML for the comparison view
	 */
	const { items_comparison, supplier_totals, winner_by_total, winner_by_items } = data;
	const suppliers = Object.keys(supplier_totals);
	const company_currency = (data.currency_meta && data.currency_meta.company_currency)
		|| selected_currency
		|| frappe.defaults.get_default('currency')
		|| 'USD';
	const currencies = (data.currency_meta && data.currency_meta.available_currencies && data.currency_meta.available_currencies.length)
		? data.currency_meta.available_currencies
		: [company_currency];
	const active_currency = selected_currency || company_currency;

	let html = `
	<div class="supplier-comparison-container" style="padding: 15px;">
		<div style="display: flex; justify-content: flex-end; align-items: center; gap: 8px; margin-bottom: 12px;">
			<label style="margin: 0; font-weight: 600; color: #495057;">Display Currency</label>
			<select class="form-control input-xs comparison-currency-select" style="width: 180px;">
				${currencies.map(currency => `<option value="${currency}" ${currency === active_currency ? 'selected' : ''}>${currency}</option>`).join('')}
			</select>
		</div>

		<!-- Comparison Type Selector -->
		<div class="comparison-type-selector" style="margin-bottom: 20px; text-align: center;">
			<button class="btn btn-sm btn-primary comparison-btn" data-type="total" style="margin-right: 10px;">
				<i class="fa fa-calculator"></i> Compare by Total Price
			</button>
			<button class="btn btn-sm btn-default comparison-btn" data-type="itemwise" style="margin-right: 10px;">
				<i class="fa fa-list"></i> Compare Item-wise
			</button>
		</div>
		
		<!-- Summary Cards -->
		<div class="row" style="margin-bottom: 20px;">
			<div class="col-md-6">
				<div class="card" style="border: 2px solid #5e64ff; border-radius: 8px; padding: 15px;">
					<h5 style="margin-top: 0; color: #5e64ff;">
						<i class="fa fa-trophy"></i> Winner by Total Price
					</h5>
					<h3 style="margin: 0; color: #333;">${winner_by_total}</h3>
					<p style="margin: 5px 0 0 0; color: #666;">
						Total: ${format_currency(convert_amount(supplier_totals[winner_by_total].base_total || supplier_totals[winner_by_total].total, company_currency, active_currency, data), active_currency)}
					</p>
					<button class="btn btn-sm btn-success award-btn" data-supplier="${winner_by_total}" data-type="total" style="margin-top: 10px;">
						<i class="fa fa-check"></i> Award ${winner_by_total}
					</button>
				</div>
			</div>
			<div class="col-md-6">
				<div class="card" style="border: 2px solid #28a745; border-radius: 8px; padding: 15px;">
					<h5 style="margin-top: 0; color: #28a745;">
						<i class="fa fa-star"></i> Winner by Best Items
					</h5>
					<h3 style="margin: 0; color: #333;">${winner_by_items}</h3>
					<p style="margin: 5px 0 0 0; color: #666;">
						Total: ${format_currency(convert_amount(supplier_totals[winner_by_items].base_total || supplier_totals[winner_by_items].total, company_currency, active_currency, data), active_currency)}
					</p>
					<button class="btn btn-sm btn-success award-btn" data-supplier="${winner_by_items}" data-type="itemwise" style="margin-top: 10px;">
						<i class="fa fa-check"></i> Award ${winner_by_items}
					</button>
				</div>
			</div>
		</div>
		
		<!-- Total Comparison View -->
		<div class="total-comparison-view" style="display: block;">
			<h4 style="margin-top: 20px; border-bottom: 2px solid #e9ecef; padding-bottom: 10px;">
				<i class="fa fa-chart-bar"></i> Total Price Comparison
			</h4>
			<table class="table table-bordered" style="margin-top: 15px;">
				<thead>
					<tr style="background: #f8f9fa;">
						<th>Rank</th>
						<th>Supplier</th>
						<th>Supplier Quotation</th>
						<th>Items Count</th>
						<th>Total Amount</th>
						<th>Action</th>
					</tr>
				</thead>
				<tbody>
	`;

	// Sort suppliers by comparable base total (company currency)
	const sorted_suppliers = Object.entries(supplier_totals)
		.sort((a, b) => (a[1].base_total || a[1].total || 0) - (b[1].base_total || b[1].total || 0));

	sorted_suppliers.forEach(([supplier, data], index) => {
		const is_winner = supplier === winner_by_total;
		const row_style = is_winner ? 'background: #d4edda; font-weight: bold;' : '';
		const rank_badge = index === 0 ? '🥇' : index === 1 ? '🥈' : index === 2 ? '🥉' : index + 1;

		const display_total = convert_amount(data.base_total || data.total || 0, company_currency, active_currency, window.__rfq_comparison_currency_data || {});

		html += `
			<tr style="${row_style}">
				<td style="text-align: center; font-size: 18px;">${rank_badge}</td>
				<td>
					${supplier}
					${is_winner ? '<span class="indicator-pill green" style="margin-left: 8px;">WINNER</span>' : ''}
				</td>
				<td>
					<a href="/app/supplier-quotation/${data.sq_name}" target="_blank">${data.sq_name}</a>
				</td>
				<td style="text-align: center;">${data.items_count}</td>
				<td style="text-align: right; font-weight: bold;">${format_currency(display_total, active_currency)}</td>
				<td style="text-align: center;">
					<button class="btn btn-xs btn-primary award-btn" data-supplier="${supplier}" data-type="total">
						Award
					</button>
				</td>
			</tr>
		`;
	});

	html += `
				</tbody>
			</table>
		</div>
		
		<!-- Item-wise Comparison View -->
		<div class="itemwise-comparison-view" style="display: none;">
			<h4 style="margin-top: 20px; border-bottom: 2px solid #e9ecef; padding-bottom: 10px;">
				<i class="fa fa-list-alt"></i> Item-wise Price Comparison
			</h4>
			<div style="overflow-x: auto; margin-top: 15px;">
				<table class="table table-bordered">
					<thead>
						<tr style="background: #f8f9fa;">
							<th>Item Code</th>
							<th>Item Name</th>
							<th style="text-align: center;">Qty</th>
							${suppliers.map(s => `<th style="text-align: center;">${s}</th>`).join('')}
							<th style="text-align: right;">Best Rate</th>
							<th>Winner</th>
						</tr>
					</thead>
					<tbody>
	`;

	items_comparison.forEach(item => {
		html += `
			<tr>
				<td>${item.item_code}</td>
				<td>${item.item_name || ''}</td>
				<td style="text-align: center;">${item.qty}</td>
		`;

		suppliers.forEach(supplier => {
			const supplier_data = item.suppliers[supplier];
			if (supplier_data) {
				const is_best = supplier === item.best_supplier;
				const cell_style = is_best ? 'background: #d4edda; font-weight: bold;' : '';
				const display_rate = convert_amount(
					supplier_data.base_rate || supplier_data.rate,
					company_currency,
					active_currency,
					window.__rfq_comparison_currency_data || {}
				);
				html += `<td style="text-align: right; ${cell_style}">${format_currency(display_rate, active_currency)}</td>`;
			} else {
				html += '<td style="text-align: center; color: #999;">-</td>';
			}
		});

		html += `
				<td style="text-align: right; font-weight: bold; color: #28a745;">${format_currency(convert_amount(item.best_base_rate || item.best_rate, company_currency, active_currency, window.__rfq_comparison_currency_data || {}), active_currency)}</td>
				<td style="font-weight: bold;">
					${item.best_supplier}
					<span class="indicator-pill green">✓</span>
				</td>
			</tr>
		`;
	});

	html += `
					</tbody>
				</table>
			</div>
		</div>
	</div>
	`;

	return html;
}


function attach_comparison_events(dialog, frm, data, state) {
	/**
	 * Attach event listeners to comparison buttons
	 */
	window.__rfq_comparison_currency_data = data;
	const wrapper = dialog.$body;

	// Currency selector
	wrapper.find('.comparison-currency-select').off('change').on('change', function () {
		state.selected_currency = $(this).val();
		const html = build_comparison_html(data, state.selected_currency);
		dialog.fields_dict.comparison_html.$wrapper.html(html);
		attach_comparison_events(dialog, frm, data, state);
	});

	// Comparison type toggle
	wrapper.find('.comparison-btn').click(function () {
		const type = $(this).data('type');

		// Update button states
		wrapper.find('.comparison-btn').removeClass('btn-primary').addClass('btn-default');
		$(this).removeClass('btn-default').addClass('btn-primary');

		// Show/hide views
		if (type === 'total') {
			wrapper.find('.total-comparison-view').show();
			wrapper.find('.itemwise-comparison-view').hide();
		} else {
			wrapper.find('.total-comparison-view').hide();
			wrapper.find('.itemwise-comparison-view').show();
		}
	});

	// Award supplier buttons
	wrapper.find('.award-btn').click(function () {
		const supplier = $(this).data('supplier');
		const award_type = $(this).data('type');

		award_supplier(frm, supplier, award_type, data, dialog, state.selected_currency);
	});
}


function award_supplier(frm, supplier, award_type, comparison_data, dialog, selected_currency) {
	/**
	 * Award a supplier and create Purchase Order
	 */
	const company_currency = (comparison_data.currency_meta && comparison_data.currency_meta.company_currency)
		|| selected_currency
		|| frappe.defaults.get_default('currency')
		|| 'USD';
	const display_total = convert_amount(
		comparison_data.supplier_totals[supplier].base_total || comparison_data.supplier_totals[supplier].total,
		company_currency,
		selected_currency || company_currency,
		comparison_data
	);

	frappe.confirm(
		`Award supplier <strong>${supplier}</strong> and create Purchase Order?<br><br>
		<strong>Award Type:</strong> ${award_type === 'total' ? 'Best Total Price' : 'Best Item Prices'}<br>
		<strong>Total Amount:</strong> ${format_currency(display_total, selected_currency || company_currency)}`,
		function () {
			// Get the supplier's quotation
			const sq_name = comparison_data.supplier_totals[supplier].sq_name;

			// Show progress indicator
			frappe.show_alert({
				message: __('Creating Purchase Order for {0}...', [supplier]),
				indicator: 'blue'
			}, 3);

			// Create PO from Supplier Quotation (allow creation, validate on save)
			frappe.call({
				method: 'next_custom_app.next_custom_app.utils.procurement_workflow.make_procurement_document',
				args: {
					source_name: sq_name,
					target_doctype: 'Purchase Order'
				},
				callback: function (r) {
					if (r.message) {
						// Close the comparison dialog
						dialog.hide();

						// Sync and open the new PO
						frappe.model.sync(r.message);
						frappe.set_route('Form', 'Purchase Order', r.message.name);

						// Success message
						frappe.show_alert({
							message: __('Purchase Order {0} created. Adjust quantities if needed and save.', [r.message.name]),
							indicator: 'green'
						}, 5);
					} else {
						frappe.msgprint({
							title: __('No Purchase Order Created'),
							message: __('Unable to create Purchase Order.'),
							indicator: 'orange'
						});
					}
				},
				error: function (r) {
					let error_message = __('Failed to create Purchase Order');
					let error_title = __('Error');

					// Extract error from server response
					if (r && r._server_messages) {
						try {
							const messages = JSON.parse(r._server_messages);
							if (messages && messages.length > 0) {
								const msg = JSON.parse(messages[0]);
								if (msg.message) {
									error_message = msg.message.replace(/\n/g, '<br>');
								}
								if (msg.title) {
									error_title = msg.title;
								}
							}
						} catch (e) {
							console.error('Error parsing:', e);
						}
					}

					frappe.msgprint({
						title: error_title,
						message: error_message,
						indicator: 'red'
					});
				}
			});
		}
	);
}


function format_currency(value, currency) {
	/**
	 * Format currency value
	 */
	const options = { fieldtype: 'Currency' };
	if (currency) {
		options.options = currency;
	}
	return frappe.format(value, options);
}


function convert_amount(value, source_currency, target_currency, comparison_data) {
	if (value === null || value === undefined) return value;

	const source = source_currency || target_currency;
	const target = target_currency || source;
	if (source === target) return value;

	const meta = (comparison_data && comparison_data.currency_meta) || {};
	const rates = meta.exchange_rates_to_company || {};
	const company_currency = meta.company_currency || source;

	const source_to_company = source === company_currency ? 1 : rates[source];
	const target_to_company = target === company_currency ? 1 : rates[target];

	if (!source_to_company || !target_to_company) {
		return value;
	}

	const base_value = value * source_to_company;
	return base_value / target_to_company;
}


console.log('=== RFQ Comparison Script Loaded ===');
