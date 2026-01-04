// Copyright (c) 2025, Nextcore Technologies and contributors
// Custom Tab Enhancement for All Procurement Workflow Doctypes

// Log script initialization
console.log('=== Procurement Custom Tabs Script Initializing ===');
console.log('Script file loaded at:', new Date().toISOString());

// List of procurement doctypes this applies to
const PROCUREMENT_DOCTYPES = [
    'Material Request',
    'Purchase Requisition',
    'Request for Quotation',
    'Supplier Quotation',
    'Purchase Order',
    'Purchase Receipt',
    'Purchase Invoice'
];

// Cache for active flow check (session-level cache)
let active_flow_cache = null;
let active_flow_cache_time = null;
const CACHE_DURATION = 30000; // 30 seconds

// Debounce helper
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// Register event handlers for all procurement doctypes
PROCUREMENT_DOCTYPES.forEach(function(doctype) {
    frappe.ui.form.on(doctype, {
        refresh: function(frm) {
            console.log(`=== ${doctype} REFRESH Event ===`);
            console.log('Document Name:', frm.doc.name);
            console.log('Document Status:', frm.doc.status);
            console.log('Document docstatus:', frm.doc.docstatus);
            console.log('Doctype:', frm.doctype);
            
            // Add a custom section with button (debounced)
            add_custom_section_debounced(frm);
            
            // Add custom create button if document is submitted
            if (frm.doc.docstatus === 1) {
                console.log('=== Document is SUBMITTED, adding custom create button ===');
                add_custom_create_button(frm);
            } else {
                console.log('=== Document NOT submitted (docstatus: ' + frm.doc.docstatus + '), skipping button ===');
            }
        },
        
        onload: function(frm) {
            console.log(`=== ${doctype} ONLOAD Event ===`);
            console.log('Form loaded for:', frm.doc.name);
            
            // Clear any leftover references from previous form
            frm.custom_section_wrapper = null;
            frm.linked_docs_container = null;
            frm._adding_custom_section = false;
        },
        
        before_save: function(frm) {
            console.log(`=== ${doctype} BEFORE SAVE ===`);
        },
        
        after_save: function(frm) {
            console.log(`=== ${doctype} AFTER SAVE - Refreshing linked documents ===`);
            // Only refresh the data, not recreate the whole section
            if (frm.custom_section_wrapper && frm.linked_docs_container && frm.linked_docs_container.length > 0) {
                const container = frm.linked_docs_container;
                container.html(`
                    <div style="display: flex; gap: 8px; align-items: center;">
                        <div style="width: 120px; height: 28px; background: linear-gradient(90deg, #e0e0e0 25%, #f0f0f0 50%, #e0e0e0 75%); background-size: 200% 100%; animation: loading 1.5s ease-in-out infinite; border-radius: 4px;"></div>
                    </div>
                `);
                load_linked_documents(frm, container);
            }
        },
        
        onload_post_render: function(frm) {
            // Cleanup any duplicate sections that might have been created
            const sections = $('.custom-tab-section');
            if (sections.length > 1) {
                console.log(`>>> Found ${sections.length} sections, removing duplicates`);
                sections.slice(1).remove();
                // Update frm reference to point to the remaining section
                frm.custom_section_wrapper = sections.first();
                frm.linked_docs_container = sections.first().find('.linked-docs-container');
            }
        }
    });
});

// Create debounced version of add_custom_section
const add_custom_section_debounced = debounce(add_custom_section, 150);

function add_custom_create_button(frm) {
    console.log('>>> add_custom_create_button() called');
    console.log('>>> Checking for next step in workflow...');
    
    // Get the next step in workflow
    frappe.call({
        method: "next_custom_app.next_custom_app.utils.procurement_workflow.get_next_step",
        args: {
            current_doctype: frm.doctype
        },
        callback: function(r) {
            console.log('*** get_next_step API response:', r);
            
            if (r.message && r.message.doctype_name) {
                const next_doctype = r.message.doctype_name;
                console.log('*** Next doctype found:', next_doctype);
                console.log('*** Adding custom button under Create dropdown');
                
                // Add custom button under "Create" dropdown with a custom label
                frm.add_custom_button(__('Custom: ' + next_doctype), function() {
                    console.log('*** CUSTOM CREATE BUTTON CLICKED ***');
                    console.log('*** Target doctype:', next_doctype);
                    show_custom_create_dialog(frm, next_doctype);
                }, __("Create"));
                
                console.log('*** Custom button added successfully');
            } else {
                console.log('*** No next step found in workflow');
            }
        },
        error: function(err) {
            console.error('*** Error getting next step:', err);
        }
    });
}

function show_custom_create_dialog(frm, next_doctype) {
    console.log('*** Showing custom create dialog for:', next_doctype);
    
    let dialog = new frappe.ui.Dialog({
        title: __('Create {0} from Custom Tab', [next_doctype]),
        fields: [
            {
                fieldtype: 'HTML',
                fieldname: 'info',
                options: `
                    <div style="padding: 15px;">
                        <h4>Custom Create Action</h4>
                        <p>This will create a <strong>${next_doctype}</strong> from ${frm.doctype}: <strong>${frm.doc.name}</strong></p>
                        <hr>
                        <p>This is a custom implementation showing the procurement workflow.</p>
                    </div>
                `
            }
        ],
        primary_action_label: __('Create {0}', [next_doctype]),
        primary_action: function() {
            console.log('*** Creating document:', next_doctype);
            
            // Call the standard procurement workflow method
            frappe.call({
                method: "next_custom_app.next_custom_app.utils.procurement_workflow.make_procurement_document",
                args: {
                    source_name: frm.docname,
                    target_doctype: next_doctype
                },
                callback: function(r) {
                    if (r.message) {
                        console.log('*** Document created successfully:', r.message.name);
                        frappe.model.sync(r.message);
                        frappe.set_route("Form", r.message.doctype, r.message.name);
                        dialog.hide();
                    }
                },
                error: function(err) {
                    console.error('*** Error creating document:', err);
                }
            });
        }
    });
    
    dialog.show();
    console.log('*** Dialog displayed');
}

function add_custom_section(frm) {
    console.log('>>> add_custom_section() function called');
    console.log('>>> Form object:', frm);
    console.log('>>> Document name:', frm.doc.name);
    
    // Skip for new documents
    if (frm.doc.__islocal) {
        console.log('>>> Skipping custom section for new document');
        return;
    }
    
    // CRITICAL: Remove ALL existing sections from DOM first to prevent duplicates
    $('.custom-tab-section').remove();
    console.log('>>> Removed all existing custom sections from DOM');
    
    // Prevent multiple simultaneous calls
    if (frm._adding_custom_section) {
        console.log('>>> Already adding custom section, skipping duplicate call');
        return;
    }
    
    // Check DOM directly for existing section (not just frm reference)
    const existing_section = $('.custom-tab-section');
    if (existing_section.length > 0 && !existing_section.hasClass('is-loading')) {
        console.log('>>> Section already exists in DOM, refreshing data only');
        frm.custom_section_wrapper = existing_section.first();
        frm.linked_docs_container = existing_section.first().find('.linked-docs-container');
        if (frm.linked_docs_container.length > 0) {
            load_linked_documents(frm, frm.linked_docs_container);
        }
        return;
    }
    
    // Set flag to prevent duplicate calls
    frm._adding_custom_section = true;
    
    // Check cache first
    const now = Date.now();
    if (active_flow_cache !== null && active_flow_cache_time && (now - active_flow_cache_time) < CACHE_DURATION) {
        console.log('>>> Using cached active flow result');
        frm._adding_custom_section = false;
        
        if (active_flow_cache) {
            create_custom_section_ui(frm);
        } else {
            console.log('>>> No active procurement workflow (cached) - skipping custom section');
        }
        return;
    }
    
    // Check if there's an active procurement workflow before showing the section
    console.log('>>> Checking for active procurement workflow...');
    frappe.call({
        method: "next_custom_app.next_custom_app.utils.procurement_workflow.get_active_flow",
        callback: function(r) {
            console.log('>>> Active flow check response:', r);
            
            // Cache the result
            active_flow_cache = r.message || null;
            active_flow_cache_time = Date.now();
            
            // Clear the flag
            frm._adding_custom_section = false;
            
            if (!r.message) {
                console.log('>>> No active procurement workflow found - skipping custom section');
                return;
            }
            
            console.log('>>> Active procurement workflow found:', r.message);
            // Proceed with creating the custom section
            create_custom_section_ui(frm);
        },
        error: function(err) {
            console.error('>>> Error checking active flow:', err);
            // Clear the flag
            frm._adding_custom_section = false;
            // Don't show the section if there's an error
        }
    });
}

function create_custom_section_ui(frm) {
    console.log('>>> create_custom_section_ui() function called');
    
    // CRITICAL: Remove any existing sections first to ensure only one exists
    $('.custom-tab-section').remove();
    console.log('>>> Removed any existing custom sections before creating new one');
    
    // Create a compact custom section in the form layout
    let wrapper = $('<div class="custom-tab-section is-loading"></div>').css({
        'margin': '10px 0',
        'padding': '12px 15px',
        'background-color': '#f8f9fa',
        'border': '1px solid #dee2e6',
        'border-radius': '4px',
        'display': 'flex',
        'flex-direction': 'column',
        'gap': '10px',
        'min-height': '60px',
        'opacity': '1',
        'transition': 'opacity 0.2s ease-in-out'
    });
    
    // Create container for linked documents (horizontal layout) with loading skeleton
    let linked_docs_container = $('<div class="linked-docs-container"></div>').css({
        'display': 'flex',
        'flex-wrap': 'wrap',
        'gap': '8px',
        'align-items': 'center',
        'min-height': '30px'
    });
    
    // Add loading skeleton
    linked_docs_container.html(`
        <div class="loading-skeleton" style="display: flex; gap: 8px; align-items: center;">
            <div style="width: 120px; height: 28px; background: linear-gradient(90deg, #e0e0e0 25%, #f0f0f0 50%, #e0e0e0 75%); background-size: 200% 100%; animation: loading 1.5s ease-in-out infinite; border-radius: 4px;"></div>
            <div style="width: 140px; height: 28px; background: linear-gradient(90deg, #e0e0e0 25%, #f0f0f0 50%, #e0e0e0 75%); background-size: 200% 100%; animation: loading 1.5s ease-in-out infinite; border-radius: 4px; animation-delay: 0.1s;"></div>
            <div style="width: 100px; height: 28px; background: linear-gradient(90deg, #e0e0e0 25%, #f0f0f0 50%, #e0e0e0 75%); background-size: 200% 100%; animation: loading 1.5s ease-in-out infinite; border-radius: 4px; animation-delay: 0.2s;"></div>
        </div>
        <style>
            @keyframes loading {
                0% { background-position: 200% 0; }
                100% { background-position: -200% 0; }
            }
        </style>
    `);
    
    wrapper.append(linked_docs_container);
    
    // Create button container aligned to right bottom
    let button_container = $('<div class="button-container"></div>').css({
        'display': 'flex',
        'justify-content': 'flex-end',
        'align-items': 'center',
        'gap': '8px'
    });
    
    // Create the custom tab button
    let open_tab_button = $('<button class="btn btn-primary btn-sm"></button>')
        .text('Document Flow')
        .on('click', function() {
            console.log('Document flow button clicked');
            show_custom_tab_dialog(frm);
        });
    
    button_container.append(open_tab_button);
    
    // Check if this is a source document (no procurement_source_name) and add View Analysis button
    if (!frm.doc.procurement_source_name && frm.doc.docstatus === 1) {
        let analysis_button = $('<button class="btn btn-default btn-sm"></button>')
            .html('<i class="fa fa-chart-line"></i> View Analysis')
            .on('click', function() {
                console.log('View Analysis button clicked');
                show_analysis_dialog(frm);
            });
        
        button_container.prepend(analysis_button);
    }
    
    wrapper.append(button_container);
    
    // Insert the section right after the form header
    if (frm.layout && frm.layout.wrapper) {
        $(frm.layout.wrapper).prepend(wrapper);
        console.log('>>> Custom section added successfully to layout wrapper');
    } else {
        // Fallback: add to form wrapper
        $(frm.wrapper).find('.form-layout').prepend(wrapper);
        console.log('>>> Custom section added to form wrapper (fallback)');
    }
    
    // Store references
    frm.custom_section_wrapper = wrapper;
    frm.linked_docs_container = linked_docs_container;
    
    // Load and display linked documents
    load_linked_documents(frm, linked_docs_container);
    
    console.log('>>> create_custom_section_ui() completed successfully');
}

function load_linked_documents(frm, container) {
    console.log('>>> load_linked_documents() called');
    console.log('>>> Document:', frm.doctype, frm.docname);
    console.log('>>> Document docstatus:', frm.doc.docstatus);
    
    // Get linked documents with counts
    frappe.call({
        method: "next_custom_app.next_custom_app.utils.procurement_workflow.get_linked_documents_with_counts",
        args: {
            doctype: frm.doctype,
            docname: frm.docname
        },
        callback: function(r) {
            console.log('*** Linked documents API response:', r);
            console.log('*** Response data:', JSON.stringify(r.message, null, 2));
            
            // Remove loading state
            if (frm.custom_section_wrapper) {
                frm.custom_section_wrapper.removeClass('is-loading');
            }
            
            if (r.message) {
                const linked_docs = r.message;
                const has_backward = linked_docs.backward && linked_docs.backward.length > 0;
                const has_forward = linked_docs.forward && linked_docs.forward.length > 0;
                
                console.log('*** Backward docs:', linked_docs.backward);
                console.log('*** Forward docs:', linked_docs.forward);
                console.log('*** Has backward:', has_backward, 'Has forward:', has_forward);
                
                if (!has_backward && !has_forward) {
                    container.html(`
                        <span style="color: #6c757d; font-size: 12px;">
                            <i>No connected documents</i>
                        </span>
                    `);
                    return;
                }
                
                // Clear container
                container.empty();
                
                // Add all buttons horizontally - backward first, then forward
                if (has_backward) {
                    linked_docs.backward.forEach(function(link) {
                        let btn = create_linked_doc_button(link, 'backward');
                        container.append(btn);
                    });
                }
                
                if (has_forward) {
                    linked_docs.forward.forEach(function(link) {
                        let btn = create_linked_doc_button(link, 'forward');
                        container.append(btn);
                    });
                }
                
                console.log('*** Linked documents displayed successfully');
            } else {
                container.html('<span style="color: #6c757d; font-size: 12px;"><i>No connected documents</i></span>');
            }
        },
        error: function(err) {
            console.error('*** Error loading linked documents:', err);
            
            // Remove loading state
            if (frm.custom_section_wrapper) {
                frm.custom_section_wrapper.removeClass('is-loading');
            }
            
            container.html('<span style="color: #dc3545; font-size: 12px;"><i>Error loading</i></span>');
        }
    });
}

function create_linked_doc_button(link, direction) {
    console.log('*** Creating button for:', link.doctype, 'Count:', link.count);
    
    let btn = $('<button class="btn btn-default btn-xs"></button>')
        .css({
            'padding': '4px 10px',
            'border': '1px solid #dee2e6',
            'border-radius': '3px',
            'background-color': direction === 'backward' ? '#e3f2fd' : '#fff3cd',
            'cursor': 'pointer',
            'font-size': '12px',
            'white-space': 'nowrap'
        })
        .html(`
            <span style="font-weight: 500;">${link.doctype}</span>
            <span style="background: #fff; padding: 1px 6px; margin-left: 4px; border-radius: 8px; font-size: 10px; font-weight: 600;">${link.count}</span>
        `)
        .on('click', function() {
            console.log('*** Linked doc button clicked:', link.doctype, 'Documents:', link.documents);
            
            if (link.count === 1) {
                // Single document - navigate directly
                frappe.set_route('Form', link.doctype, link.documents[0]);
            } else {
                // Multiple documents - show list
                frappe.set_route('List', link.doctype, {
                    name: ['in', link.documents]
                });
            }
        })
        .on('mouseenter', function() {
            $(this).css('opacity', '0.8');
        })
        .on('mouseleave', function() {
            $(this).css('opacity', '1');
        });
    
    return btn;
}

function show_custom_tab_dialog(frm) {
    console.log('*** BUTTON CLICKED - Opening custom tab dialog ***');
    console.log('*** Current document:', frm.doc.name);
    
    // Create a dialog to display document flow
    let dialog = new frappe.ui.Dialog({
        title: __('Document Flow - {0}: {1}', [frm.doctype, frm.doc.name]),
        size: 'large',
        fields: [
            {
                fieldtype: 'HTML',
                fieldname: 'flow_content'
            }
        ],
        primary_action_label: __('Close'),
        primary_action: function() {
            dialog.hide();
        }
    });
    
    dialog.show();
    
    // Get the container element after dialog is shown and remove default padding
    let container = dialog.fields_dict.flow_content.$wrapper;
    container.css({
        'margin': '0',
        'padding': '0'
    });
    container.html('<div style="padding: 15px; min-height: 300px;"><p>Loading document flow...</p></div>');
    
    // Load document flow with statuses
    console.log('*** Calling get_document_flow_with_statuses for:', frm.doctype, frm.docname);
    frappe.call({
        method: "next_custom_app.next_custom_app.utils.procurement_workflow.get_document_flow_with_statuses",
        args: {
            doctype: frm.doctype,
            docname: frm.docname
        },
        callback: function(r) {
            console.log('*** Flow API response:', r);
            console.log('*** Flow data:', r.message);
            if (r.message) {
                render_document_flow(r.message, container);
            } else {
                console.error('*** No message in response:', r);
                container.html('<div style="padding: 20px;"><p style="color: #999;">No flow data available.</p></div>');
            }
        },
        error: function(err) {
            console.error('*** Error loading flow:', err);
            const error_msg = err ? (err.message || JSON.stringify(err)) : 'Unknown error';
            container.html('<div style="padding: 20px;"><p style="color: #dc3545;">Error: ' + error_msg + '</p></div>');
        }
    });
}

function show_analysis_dialog(frm) {
    console.log('*** View Analysis button clicked ***');
    
    let dialog = new frappe.ui.Dialog({
        title: __('Procurement Analysis - {0}: {1}', [frm.doctype, frm.doc.name]),
        size: 'large',
        fields: [
            {
                fieldtype: 'HTML',
                fieldname: 'analysis_content'
            }
        ],
        primary_action_label: __('Close'),
        primary_action: function() {
            dialog.hide();
        }
    });
    
    dialog.show();
    
    // Get the container element after dialog is shown and remove default padding
    let container = dialog.fields_dict.analysis_content.$wrapper;
    container.css({
        'margin': '0',
        'padding': '0'
    });
    container.html('<div style="padding: 15px; min-height: 300px;"><p>Loading analysis...</p></div>');
    
    // Load analysis data
    console.log('*** Calling get_procurement_analysis for:', frm.doctype, frm.docname);
    frappe.call({
        method: "next_custom_app.next_custom_app.utils.procurement_workflow.get_procurement_analysis",
        args: {
            doctype: frm.doctype,
            docname: frm.docname
        },
        callback: function(r) {
            console.log('*** Analysis API response:', r);
            console.log('*** Analysis data:', r.message);
            if (r.message) {
                render_analysis(r.message, container);
            } else {
                console.error('*** No message in analysis response:', r);
                container.html('<div style="padding: 20px;"><p style="color: #999;">No analysis data available.</p></div>');
            }
        },
        error: function(err) {
            console.error('*** Error loading analysis:', err);
            const error_msg = err ? (err.message || JSON.stringify(err)) : 'Unknown error';
            container.html('<div style="padding: 20px;"><p style="color: #dc3545;">Error: ' + error_msg + '</p></div>');
        }
    });
}

function render_document_flow(flow_data, container) {
    console.log('*** Rendering document flow:', flow_data);
    
    // Color mapping for different doctypes
    const doctypeColors = {
        'Material Request': { main: '#8e44ad', light: '#e8d5f0', border: '#8e44ad' },
        'Purchase Requisition': { main: '#3498db', light: '#d6eaf8', border: '#3498db' },
        'Request for Quotation': { main: '#e67e22', light: '#fdebd0', border: '#e67e22' },
        'Supplier Quotation': { main: '#16a085', light: '#d1f2eb', border: '#16a085' },
        'Purchase Order': { main: '#2c3e50', light: '#d5dbdb', border: '#2c3e50' },
        'Purchase Receipt': { main: '#27ae60', light: '#d5f4e6', border: '#27ae60' },
        'Purchase Invoice': { main: '#c0392b', light: '#f5d6d3', border: '#c0392b' }
    };
    
    function getDoctypeColor(doctype, is_current, is_grayed) {
        if (is_grayed) {
            return { main: '#9e9e9e', light: '#f5f5f5', border: '#e0e0e0' };
        }
        if (is_current) {
            return { main: '#0d6efd', light: '#e7f1ff', border: '#0d6efd' };
        }
        return doctypeColors[doctype] || { main: '#6c757d', light: '#f8f9fa', border: '#dee2e6' };
    }
    
    function renderCompactNode(node) {
        const colors = getDoctypeColor(node.doctype, node.is_current, node.is_grayed);
        const status = node.workflow_state || node.status || 'Draft';
        
        return `
            <div class="doc-node-compact" style="
                display: flex;
                align-items: center;
                gap: 6px;
                padding: 6px 12px;
                background: ${colors.light};
                border: 1.5px solid ${colors.border};
                border-radius: 20px;
                cursor: pointer;
                font-size: 12px;
                transition: all 0.2s;
                margin: 3px;
                min-width: 200px;
                max-width: 250px;
            " onclick="frappe.set_route('Form', '${node.doctype}', '${node.name}')"
               onmouseover="this.style.transform='scale(1.05)'; this.style.boxShadow='0 2px 8px rgba(0,0,0,0.15)'"
               onmouseout="this.style.transform='scale(1)'; this.style.boxShadow='none'">
                <span style="
                    background: ${colors.main};
                    color: white;
                    padding: 2px 8px;
                    border-radius: 12px;
                    font-size: 9px;
                    font-weight: 700;
                    text-transform: uppercase;
                    letter-spacing: 0.5px;
                ">${node.doctype.split(' ').map(w => w[0]).join('')}</span>
                <span style="
                    color: ${colors.main};
                    font-weight: 600;
                    overflow: hidden;
                    text-overflow: ellipsis;
                    white-space: nowrap;
                    flex: 1;
                ">${node.name}</span>
                <span style="
                    background: ${colors.main}15;
                    color: ${colors.main};
                    padding: 2px 6px;
                    border-radius: 8px;
                    font-size: 9px;
                    font-weight: 600;
                ">${status}</span>
            </div>
        `;
    }
    
    // Build grid structure: rows and columns
    function buildGridStructure(nodes, colIndex = 0, parentCol = null) {
        const grid = [];
        let currentCol = colIndex;
        
        nodes.forEach((node, idx) => {
            // Assign column to node
            node._gridCol = currentCol;
            node._gridRow = parentCol !== null ? parentCol._gridRow + 1 : 0;
            
            // Store parent reference for centering calculation
            node._parent = parentCol;
            
            // Add node to grid
            if (!grid[node._gridRow]) {
                grid[node._gridRow] = [];
            }
            grid[node._gridRow].push(node);
            
            // Process children recursively
            if (node.children && node.children.length > 0) {
                const childGrid = buildGridStructure(node.children, currentCol, node);
                // Merge child grid into main grid
                childGrid.forEach((row, rowIdx) => {
                    const actualRow = node._gridRow + 1 + rowIdx;
                    if (!grid[actualRow]) {
                        grid[actualRow] = [];
                    }
                    grid[actualRow].push(...row);
                });
                
                // Calculate how many columns this branch used
                // Find the maximum column used by any descendant
                let maxColUsed = currentCol;
                childGrid.forEach(row => {
                    row.forEach(childNode => {
                        maxColUsed = Math.max(maxColUsed, childNode._gridCol);
                    });
                });
                
                // Move current column to after all descendants of this node
                currentCol = maxColUsed + 1;
            } else {
                // No children, just move to next column for next sibling
                currentCol++;
            }
        });
        
        return grid;
    }
    
    function renderGrid(nodes) {
        if (!nodes || nodes.length === 0) return '';
        
        // Build grid structure
        const grid = buildGridStructure(nodes);
        
        // Calculate max columns needed
        let maxCol = 0;
        grid.forEach(row => {
            row.forEach(node => {
                maxCol = Math.max(maxCol, node._gridCol);
            });
        });
        const numCols = maxCol + 1;
        
        // Get doctype for each row
        const rowDoctypes = grid.map(row => {
            if (row.length > 0) {
                return row[0].doctype;
            }
            return '';
        });
        
        let html = '';
        
        // Render each row with its label
        grid.forEach((row, rowIdx) => {
            const doctype = rowDoctypes[rowIdx];
            const colors = getDoctypeColor(doctype, false, false);
            
            // Row container
            html += '<div style="display: flex; align-items: flex-start; margin-bottom: 25px; min-width: fit-content;">';
            
            // Row label (doctype)
            html += `<div style="
                min-width: 150px;
                padding: 8px 12px;
                background: ${colors.main}15;
                border-left: 4px solid ${colors.main};
                border-radius: 4px;
                margin-right: 20px;
                position: sticky;
                left: 0;
                background: #f8f9fa;
                z-index: 1;
            ">
                <div style="font-weight: 700; color: ${colors.main}; font-size: 12px; text-transform: uppercase; letter-spacing: 0.5px;">
                    ${doctype}
                </div>
                <div style="font-size: 10px; color: #6c757d; margin-top: 2px;">
                    ${row.length} document${row.length > 1 ? 's' : ''}
                </div>
            </div>`;
            
            // Documents in this row
            html += '<div style="display: flex; gap: 15px; flex-wrap: nowrap; align-items: flex-start; position: relative;">';
            
            // Create a map of column to node for this row
            const colMap = {};
            row.forEach(node => {
                colMap[node._gridCol] = node;
            });
            
            // Check if there are siblings (multiple nodes with same parent)
            const siblingGroups = {};
            row.forEach(node => {
                const parentKey = node._parent ? `${node._parent.doctype}::${node._parent.name}` : 'root';
                if (!siblingGroups[parentKey]) {
                    siblingGroups[parentKey] = [];
                }
                siblingGroups[parentKey].push(node);
            });
            
            // Draw horizontal connector lines for sibling groups
            Object.values(siblingGroups).forEach(siblings => {
                if (siblings.length > 1) {
                    const firstCol = siblings[0]._gridCol;
                    const lastCol = siblings[siblings.length - 1]._gridCol;
                    const parentNode = siblings[0]._parent;
                    
                    if (parentNode) {
                        const nodeColors = getDoctypeColor(parentNode.doctype, parentNode.is_current, parentNode.is_grayed);
                        const lineColor = nodeColors.border;
                        
                        // Calculate positions
                        const cellWidth = 260 + 15; // min-width + gap
                        const leftPos = firstCol * cellWidth + 130; // center of first cell
                        const lineWidth = (lastCol - firstCol) * cellWidth;
                        
                        // Top horizontal line connecting siblings
                        html += `<div style="
                            position: absolute;
                            top: -15px;
                            left: ${leftPos}px;
                            width: ${lineWidth}px;
                            height: 2px;
                            background: ${lineColor};
                            z-index: 0;
                        "></div>`;
                        
                        // Vertical lines dropping down from horizontal line to each sibling
                        siblings.forEach(sibling => {
                            const siblingPos = sibling._gridCol * cellWidth + 130;
                            html += `<div style="
                                position: absolute;
                                top: -15px;
                                left: ${siblingPos}px;
                                width: 2px;
                                height: 15px;
                                background: ${lineColor};
                                z-index: 0;
                            "></div>`;
                        });
                    }
                }
            });
            
            // Render cells for each column
            for (let col = 0; col < numCols; col++) {
                html += '<div style="min-width: 260px; display: flex; flex-direction: column; align-items: center; position: relative; z-index: 1;">';
                
                if (colMap[col]) {
                    // Node exists in this position
                    html += renderCompactNode(colMap[col]);
                    
                    // Add connector line to children if any
                    if (colMap[col].children && colMap[col].children.length > 0) {
                        const nodeColors = getDoctypeColor(colMap[col].doctype, colMap[col].is_current, colMap[col].is_grayed);
                        html += '<div style="width: 2px; height: 20px; background: ' + nodeColors.border + '; margin: 5px auto;"></div>';
                        html += '<div style="text-align: center; color: ' + nodeColors.border + '; font-size: 16px; line-height: 1;">▼</div>';
                    }
                } else {
                    // Empty cell to maintain grid alignment
                    html += '<div style="height: 50px;"></div>';
                }
                
                html += '</div>';
            }
            
            html += '</div>'; // Close documents container
            html += '</div>'; // Close row container
        });
        
        return html;
    }
    
    // Direct scrollable container without nested cards - use full dialog space
    let html = '<div style="overflow-x: auto; overflow-y: auto; height: 100%; padding: 20px; background: #f8f9fa;">';
    
    if (flow_data.nodes && flow_data.nodes.length > 0) {
        html += renderGrid(flow_data.nodes);
    } else {
        html += '<p style="color: #6c757d; text-align: center; padding: 40px;">No document flow available</p>';
    }
    
    html += '</div>';
    
    container.html(html);
}

function render_analysis(analysis_data, container) {
    console.log('*** Rendering analysis:', analysis_data);
    
    // Remove any default padding/margin from container
    container.css({
        'margin': '0',
        'padding': '0'
    });
    
    // Direct content without nested cards - use full dialog space
    let html = '<div style="font-family: -apple-system, BlinkMacSystemFont, \'Segoe UI\', Roboto, sans-serif; padding: 20px; height: 100%; overflow-y: auto;">';
    
    // Summary section
    html += '<h4 style="margin: 0 0 15px 0; color: #495057;">Procurement Summary</h4>';
    html += '<div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin-bottom: 25px;">';
    
    const metrics = [
        { label: 'Total Child Documents', value: analysis_data.total_children || 0, color: '#0d6efd' },
        { label: 'Total Items', value: analysis_data.total_items || 0, color: '#198754' },
        { label: 'Total Quantity', value: analysis_data.total_quantity || 0, color: '#ffc107' },
        { label: 'Completion Rate', value: (analysis_data.completion_rate || 0) + '%', color: '#0dcaf0' }
    ];
    
    metrics.forEach(metric => {
        html += `
            <div style="padding: 15px; background: linear-gradient(135deg, ${metric.color}15 0%, ${metric.color}05 100%); border-left: 4px solid ${metric.color}; border-radius: 4px;">
                <div style="font-size: 24px; font-weight: 700; color: ${metric.color}; margin-bottom: 5px;">
                    ${metric.value}
                </div>
                <div style="font-size: 12px; color: #6c757d; text-transform: uppercase; letter-spacing: 0.5px;">
                    ${metric.label}
                </div>
            </div>
        `;
    });
    
    html += '</div>';
    
    // Item breakdown
    if (analysis_data.items_breakdown && analysis_data.items_breakdown.length > 0) {
        html += '<h4 style="margin: 25px 0 15px 0; color: #495057;">Items Breakdown</h4>';
        html += '<table style="width: 100%; border-collapse: collapse;">';
        html += '<thead><tr style="background: #f8f9fa; border-bottom: 2px solid #dee2e6;">';
        html += '<th style="padding: 10px; text-align: left; font-size: 12px; color: #6c757d; text-transform: uppercase;">Item</th>';
        html += '<th style="padding: 10px; text-align: right; font-size: 12px; color: #6c757d; text-transform: uppercase;">Source Qty</th>';
        html += '<th style="padding: 10px; text-align: right; font-size: 12px; color: #6c757d; text-transform: uppercase;">Consumed</th>';
        html += '<th style="padding: 10px; text-align: right; font-size: 12px; color: #6c757d; text-transform: uppercase;">Available</th>';
        html += '<th style="padding: 10px; text-align: right; font-size: 12px; color: #6c757d; text-transform: uppercase;">% Used</th>';
        html += '</tr></thead><tbody>';
        
        analysis_data.items_breakdown.forEach(item => {
            const percent_used = ((item.consumed / item.source_qty) * 100).toFixed(1);
            const bar_color = percent_used >= 100 ? '#dc3545' : percent_used >= 80 ? '#ffc107' : '#198754';
            
            html += `<tr style="border-bottom: 1px solid #dee2e6;">
                <td style="padding: 10px;">${item.item_code}</td>
                <td style="padding: 10px; text-align: right;">${item.source_qty}</td>
                <td style="padding: 10px; text-align: right;">${item.consumed}</td>
                <td style="padding: 10px; text-align: right; font-weight: 600; color: ${item.available <= 0 ? '#dc3545' : '#198754'};">
                    ${item.available}
                </td>
                <td style="padding: 10px; text-align: right;">
                    <div style="display: flex; align-items: center; justify-content: flex-end; gap: 8px;">
                        <div style="flex: 1; max-width: 100px; height: 8px; background: #e9ecef; border-radius: 4px; overflow: hidden;">
                            <div style="width: ${Math.min(percent_used, 100)}%; height: 100%; background: ${bar_color}; transition: width 0.3s;"></div>
                        </div>
                        <span style="font-weight: 600; color: ${bar_color};">${percent_used}%</span>
                    </div>
                </td>
            </tr>`;
        });
        
        html += '</tbody></table>';
    }
    
    html += '</div>';
    
    container.html(html);
}

// Log at the end of the script
console.log('=== Procurement Custom Tabs Script Loaded Successfully ===');
console.log('=== Registered for doctypes:', PROCUREMENT_DOCTYPES.join(', '), '===');