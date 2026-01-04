// Copyright (c) 2025, Nextcore Technologies and contributors
// For license information, please see license.txt

console.log("=== PROCUREMENT WORKFLOW JS FILE LOADED ===");

// Use frappe.ready to ensure frappe is fully loaded
frappe.ready(function() {
	console.log("=== FRAPPE READY - Initializing Procurement Workflow ===");
	
	frappe.provide("next_custom_app.procurement_workflow");

next_custom_app.procurement_workflow = {
	setup: function(frm) {
		// Add custom buttons and UI enhancements
		if (frm.doc.__islocal) {
			return; // Skip for new documents
		}

		console.log("Procurement workflow setup called for:", frm.doctype, frm.docname);
		console.log("About to call show_linked_documents_nav");

		// Show linked documents navigation bar (top, like Odoo smart buttons)
		this.show_linked_documents_nav(frm);
		console.log("show_linked_documents_nav called");

		// If document has a source, show available quantities
		if (frm.doc.procurement_source_doctype && frm.doc.procurement_source_name) {
			this.show_available_quantities(frm);
		}
		
		// Add create button for next document type
		if (frm.doc.docstatus === 1) {
			console.log("Document is submitted, adding create buttons...");
			this.add_create_buttons(frm);
		}
	},
	
	show_linked_documents_nav: function(frm) {
		console.log("=== SHOW LINKED DOCS NAV STARTED ===");
		console.log("Form doctype:", frm.doctype);
		console.log("Form docname:", frm.docname);
		
		// Get linked documents with counts
		frappe.call({
			method: "next_custom_app.next_custom_app.utils.procurement_workflow.get_linked_documents_with_counts",
			args: {
				doctype: frm.doctype,
				docname: frm.docname
			},
			callback: function(r) {
				console.log("API Response received:", r);
				
				if (r.message) {
					const linked_docs = r.message;
					console.log("Linked docs data:", linked_docs);
					
					const has_backward = linked_docs.backward && linked_docs.backward.length > 0;
					const has_forward = linked_docs.forward && linked_docs.forward.length > 0;
					
					console.log("Has backward:", has_backward, "Has forward:", has_forward);
					
					// Only display if there are linked documents
					if (!has_backward && !has_forward) {
						console.log("No linked documents found, exiting");
						return;
					}
					
					// Remove existing nav bar if present
					$('.procurement-linked-docs-nav').remove();
					
					// Build the navigation bar HTML
					let nav_html = '<div class="procurement-linked-docs-nav">';
					
					// Backward links (source documents)
					if (has_backward) {
						nav_html += '<div class="nav-section nav-backward">';
						nav_html += '<div class="nav-label">Source Documents:</div>';
						nav_html += '<div class="nav-buttons">';
						
						linked_docs.backward.forEach(function(link) {
							nav_html += `
								<button class="btn btn-sm btn-default procurement-nav-btn"
										data-doctype="${link.doctype}"
										data-documents='${JSON.stringify(link.documents)}'
										data-direction="backward">
									<span class="btn-label">${link.doctype}</span>
									<span class="btn-badge">${link.count}</span>
								</button>
							`;
						});
						
						nav_html += '</div></div>';
					}
					
					// Forward links (child documents)
					if (has_forward) {
						nav_html += '<div class="nav-section nav-forward">';
						nav_html += '<div class="nav-label">Child Documents:</div>';
						nav_html += '<div class="nav-buttons">';
						
						linked_docs.forward.forEach(function(link) {
							nav_html += `
								<button class="btn btn-sm btn-default procurement-nav-btn"
										data-doctype="${link.doctype}"
										data-documents='${JSON.stringify(link.documents)}'
										data-direction="forward">
									<span class="btn-label">${link.doctype}</span>
									<span class="btn-badge">${link.count}</span>
								</button>
							`;
						});
						
						nav_html += '</div></div>';
					}
					
					nav_html += '</div>';
					
					console.log("HTML generated:", nav_html.substring(0, 200) + "...");
					
					// Remove any existing nav bar
					$('.procurement-linked-docs-nav').remove();
					console.log("Removed existing nav bars");
					
					// Insert at the very top of form content (like Odoo smart buttons)
					// Position: After form title, before all form sections
					const $form_container = frm.page.page_form;
					console.log("Form container found:", $form_container.length > 0);
					
					if ($form_container.length) {
						// Find the first form section and insert before it
						const $first_section = $form_container.find('.form-section, .form-column, .form-layout').first();
						console.log("First section found:", $first_section.length > 0);
						
						if ($first_section.length) {
							$(nav_html).insertBefore($first_section);
							console.log("Inserted before first section");
						} else {
							// Fallback: prepend to form container
							$(nav_html).prependTo($form_container);
							console.log("Prepended to form container");
						}
						
						// Verify insertion
						const inserted = $('.procurement-linked-docs-nav');
						console.log("Navigation bar inserted successfully. Count:", inserted.length);
						console.log("Nav bar HTML:", inserted.html());
					} else {
						console.error("Form container not found!");
					}
					
					// Add click handlers for navigation buttons
					$('.procurement-nav-btn').on('click', function(e) {
						e.preventDefault();
						const doctype = $(this).data('doctype');
						const documents = $(this).data('documents');
						const direction = $(this).data('direction');
						
						// Navigate based on document count
						if (documents.length === 1) {
							// Single document - navigate directly
							frappe.set_route('Form', doctype, documents[0]);
						} else {
							// Multiple documents - show list filtered to these documents
							frappe.set_route('List', doctype, {
								name: ['in', documents.join(',')]
							});
						}
					});
				} else {
					console.log("No message in response");
				}
			},
			error: function(err) {
				console.error("Error calling API:", err);
			}
		});
	},
	
	add_create_buttons: function(frm) {
		console.log("add_create_buttons called for:", frm.doctype);
		
		// Only show create buttons for submitted documents
		if (!frm.doc.docstatus || frm.doc.docstatus !== 1) {
			console.log("Document not submitted, skipping button creation");
			return;
		}
		
		// Get the next step in workflow
		frappe.call({
			method: "next_custom_app.next_custom_app.utils.procurement_workflow.get_next_step",
			args: {
				current_doctype: frm.doctype
			},
			callback: function(r) {
				console.log("get_next_step response:", r);
				
				if (r.message && r.message.doctype_name) {
					const next_doctype = r.message.doctype_name;
					const next_doctype_label = next_doctype;
					
					console.log("Adding button for:", next_doctype_label);
					
					// Add custom button under "Create" dropdown
					frm.add_custom_button(__(next_doctype_label), function() {
						console.log("Create button clicked for:", next_doctype);
						console.log("Calling with source:", frm.docname, "target:", next_doctype);
						
						frappe.call({
							method: "next_custom_app.next_custom_app.utils.procurement_workflow.make_procurement_document",
							args: {
								source_name: frm.docname,
								target_doctype: next_doctype
							},
							callback: function(r) {
								if (r.message) {
									console.log("Response received:", r.message);
									console.log("Source fields set:", r.message.procurement_source_doctype, r.message.procurement_source_name);
									
									// Sync the document to client
									frappe.model.sync(r.message);
									
									// Navigate to the new document
									frappe.set_route("Form", r.message.doctype, r.message.name);
									
									// After navigation, make source fields read-only
									setTimeout(function() {
										var new_frm = cur_frm;
										if (new_frm && new_frm.docname === r.message.name) {
											new_frm.set_df_property('procurement_source_doctype', 'read_only', 1);
											new_frm.set_df_property('procurement_source_name', 'read_only', 1);
											new_frm.refresh_field('procurement_source_doctype');
											new_frm.refresh_field('procurement_source_name');
										}
									}, 500);
								}
							},
							error: function(r) {
								console.error("Error creating document:", r);
							}
						});
					}, __("Create"));
					
					console.log("Button added successfully");
				} else {
					console.log("No next step found or invalid response");
				}
			},
			error: function(r) {
				console.error("Error getting next step:", r);
			}
		});
	},


	show_available_quantities: function(frm) {
		if (!frm.doc.procurement_source_doctype || !frm.doc.procurement_source_name) {
			return;
		}

		frappe.call({
			method: "next_custom_app.next_custom_app.utils.procurement_workflow.get_available_quantities",
			args: {
				source_doctype: frm.doc.procurement_source_doctype,
				source_name: frm.doc.procurement_source_name,
				target_doctype: frm.doctype
			},
			callback: function(r) {
				if (r.message) {
					const available_qty = r.message;
					
					// Add indicator to items table
					frm.fields_dict.items.grid.wrapper.find('.grid-body .grid-row').each(function(i, row) {
						const item = frm.doc.items[i];
						if (item && available_qty[item.item_code]) {
							const qty_info = available_qty[item.item_code];
							const $row = $(row);
							
							// Remove existing indicators
							$row.find('.qty-indicator').remove();
							
							// Add new indicator
							const indicator_html = `
								<div class="qty-indicator" style="font-size: 11px; color: #888; margin-top: 2px;">
									Available: ${qty_info.available_qty} 
									(Source: ${qty_info.source_qty}, Consumed: ${qty_info.consumed_qty})
								</div>
							`;
							$row.find('[data-fieldname="qty"]').append(indicator_html);
						}
					});
				}
			}
		});
	},

	validate_quantities: function(frm) {
		// Client-side validation to warn about quantity issues
		if (!frm.doc.procurement_source_doctype || !frm.doc.procurement_source_name) {
			return true;
		}

		return new Promise((resolve) => {
			frappe.call({
				method: "next_custom_app.next_custom_app.utils.procurement_workflow.get_available_quantities",
				args: {
					source_doctype: frm.doc.procurement_source_doctype,
					source_name: frm.doc.procurement_source_name,
					target_doctype: frm.doctype
				},
				callback: function(r) {
					if (r.message) {
						const available_qty = r.message;
						let has_issues = false;
						let issues = [];

						frm.doc.items.forEach(function(item) {
							if (available_qty[item.item_code]) {
								const qty_info = available_qty[item.item_code];
								if (item.qty > qty_info.available_qty) {
									has_issues = true;
									issues.push(`${item.item_code}: Requested ${item.qty}, Available ${qty_info.available_qty}`);
								}
							}
						});

						if (has_issues) {
							frappe.msgprint({
								title: __('Quantity Validation'),
								indicator: 'red',
								message: __('The following items exceed available quantities:<br>' + issues.join('<br>'))
							});
							resolve(false);
						} else {
							resolve(true);
						}
					} else {
						resolve(true);
					}
				}
			});
		});
	}
};

// Setup for all procurement doctypes
const procurement_doctypes = [
	'Material Request',
	'Purchase Requisition',
	'Request for Quotation',
	'Supplier Quotation',
	'Purchase Order',
	'Purchase Receipt',
	'Purchase Invoice'
];

console.log("Registering procurement workflow for doctypes:", procurement_doctypes);

// Add event handlers for each procurement doctype
procurement_doctypes.forEach(function(doctype) {
	frappe.ui.form.on(doctype, {
		refresh: function(frm) {
			console.log("Refresh event fired for:", doctype);
			// Setup procurement workflow features
			next_custom_app.procurement_workflow.setup(frm);
		},
		
		onload: function(frm) {
			console.log("Onload event fired for:", doctype);
			// Additional setup on load if needed
			if (frm.doc.docstatus === 1) {
				next_custom_app.procurement_workflow.add_create_buttons(frm);
			}
		},
		
		onload_post_render: function(frm) {
			// Make source fields read-only if they have values
			if (frm.doc.procurement_source_doctype && frm.doc.procurement_source_name) {
				frm.set_df_property('procurement_source_doctype', 'read_only', 1);
				frm.set_df_property('procurement_source_name', 'read_only', 1);
			}
		}
	});
});

	console.log("=== PROCUREMENT WORKFLOW: Registering event handlers for doctypes ===");
	
	// If a form is already loaded, apply the setup immediately
	if (typeof cur_frm !== 'undefined' && cur_frm && procurement_doctypes.includes(cur_frm.doctype)) {
		console.log("=== APPLYING TO ALREADY LOADED FORM:", cur_frm.doctype, "===");
		next_custom_app.procurement_workflow.setup(cur_frm);
	}
	
	console.log("Procurement workflow JS loaded successfully");
	console.log("=== END OF PROCUREMENT WORKFLOW JS ===");

}); // End of frappe.ready