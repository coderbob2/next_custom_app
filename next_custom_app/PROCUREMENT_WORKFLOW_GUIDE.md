# Procurement Workflow Engine - User Guide

## Overview

This custom ERPNext Custom App provides a fully configurable procurement workflow engine where the sequence of documents, validation rules, and item restrictions are defined through configuration rather than hardcoded logic.

## Features

✅ **Dynamic Workflow Configuration**: Define document sequences through UI
✅ **Zero-Flicker Button Override**: Default ERPNext "Create" buttons are suppressed at the controller level via `add_custom_button` interceptor — no DOM hacks, no setTimeout, no MutationObserver
✅ **Dynamic Doctype Discovery**: Procurement doctypes are fetched from the active flow; a hardcoded fallback ensures immediate coverage
✅ **Permission-Aware Creation**: Server-side permission check when creating the next document
✅ **Quantity Validation**: Automatic enforcement of quantity limits across workflow steps (server-side), including indirect chain tracking (PO → SQ → RFQ)
✅ **Duplicate PO Prevention**: Draft and submitted POs are both counted against RFQ quantities, preventing duplicate Purchase Orders from the same RFQ
✅ **Source Document Enforcement**: When `Requires Source` is checked, documents cannot be created without a valid source
✅ **Item Restrictions**: Ensure only approved items flow through the procurement chain
✅ **Field Propagation**: Common header fields (project, cost center, supplier, terms, etc.) are automatically copied to the next document
✅ **Non-Items Doctype Support**: Doctypes without items tables (e.g., Payment Entry, Payment Request) are supported via reference field mapping
✅ **Document Linking**: Complete forward and backward document tracking
✅ **Cancellation Protection**: Prevent deletion/cancellation when child documents exist
✅ **Real-time UI Updates**: View document chains and available quantities in real-time
✅ **Audit Trail**: Complete history of all procurement document relationships

## Installation

### 1. Install the App

```bash
cd /path/to/frappe-bench
bench get-app https://github.com/your-repo/next_custom_app
bench --site your-site.local install-app next_custom_app
```

### 2. Setup Custom Fields

The app automatically creates custom fields during installation. If you need to run setup manually:

```python
# In bench console
bench --site your-site.local console

# Run:
from next_custom_app.next_custom_app.utils.procurement_workflow import setup_custom_fields
setup_custom_fields()
```

### 3. Verify Installation

Navigate to: **Settings → Search for "Procurement Flow"** (or use global search/smart bar)

**Note:** The Procurement Workflow workspace is intentionally hidden from the desk sidebar to keep the interface clean. Access it via Settings or global search.

## Configuration

### Step 1: Create a Procurement Flow

1. Go to **Procurement Flow** list
2. Click **New**
3. Fill in the details:
   - **Flow Name**: e.g., "Standard Procurement Flow"
   - **Is Active**: Check this box (only one flow can be active)
   - **Description**: Optional description of the workflow

### Step 2: Define Workflow Steps

In the **Flow Steps** table, add steps in sequential order. Parallel steps are allowed by using the same **Step No** and a shared **Step Group**.

| Step No | DocType | Step Group | Allowed Actions | Requires Source | Is Final Step |
|---------|---------|------------|----------------|-----------------|---------------|
| 1 | Material Request | S1 | Create | ☐ | ☐ |
| 2 | Purchase Requisition | S2_PARALLEL | Create | ☑ | ☐ |
| 2 | Stock Entry | S2_PARALLEL | Create | ☑ | ☑ |
| 3 | Request for Quotation | S3 | Create | ☑ | ☐ |
| 4 | Supplier Quotation | S4 | Create | ☑ | ☐ |
| 5 | Purchase Order | S5 | Create | ☑ | ☐ |
| 6 | Purchase Receipt | S6 | Create | ☑ | ☐ |
| 7 | Purchase Invoice | S7 | Create | ☑ | ☑ |

**Field Descriptions:**
- **Step No**: Sequential number (must be 1, 2, 3, etc.). Duplicates are allowed for parallel steps.
- **DocType**: The document type for this step
- **Step Group**: Optional label to group parallel steps (e.g., `S2_PARALLEL`)
- **Allowed Actions**: Create, Update, or Complete (for future extensibility)
- **Requires Source**: If checked, documents must be created from previous step
- **Is Final Step**: Marks a terminal step in any branch (no next-step buttons shown)

### Step 3: Define Validation Rules (Optional)

In the **Rule Sets** table, you can add custom validation rules:

| Rule Type | Apply to Step | Rule Value |
|-----------|--------------|------------|
| Quantity Limit | 2 | {"max_qty": 1000} |
| Item Restriction | 3 | {"allowed_groups": ["Raw Materials"]} |

**Note**: Rule values are stored as JSON for extensibility.

### Step 4: Activate the Flow

1. Check the **Is Active** checkbox
2. Save the document
3. The system will validate that no other flow is active
4. Once saved, all procurement documents will follow this workflow

## Usage

### Creating Documents in Sequence

#### 1. Create Material Request (First Step)

1. Go to **Buying → Material Request → New**
2. Add items with quantities
3. Save and Submit

#### 2. Create Purchase Requisition or Stock Entry (from Material Request)

**From Material Request (Recommended)**
1. Open the submitted Material Request
2. Click the **Create Purchase Requisition** button (or **Create** dropdown if parallel steps exist)
3. A confirmation dialog shows the source document chain
4. Click **Create** to proceed — the system automatically:
   - Checks your permission to create the target doctype
   - Links to source Material Request
   - Copies items, project, cost center, and other common fields
   - Validates items exist in source
   - Checks quantity limits across parallel steps

> **Note**: If `Requires Source` is checked in the workflow step, manual creation (without a source document) is blocked. The document must be created through the workflow **Create** button.

#### 3. Continue Through Workflow

Follow the same pattern for each subsequent step:
- Request for Quotation (from PR)
- Supplier Quotation (from RFQ)
- Purchase Order (from SQ)
- Purchase Receipt (from PO)
- Purchase Invoice (from PO or PR)

### Viewing Document Chain

When viewing any procurement document, you'll see a **"Document Chain"** section in the sidebar showing:

**Source Documents (Backward Chain)**
- All parent documents leading to current document

**Current Document**
- Highlighted with background color

**Child Documents (Forward Chain)**
- All documents created from this document

### Quantity Tracking

Quantity validation is enforced **server-side** when saving or submitting documents:

1. **Automatic Validation**: The system prevents:
   - Adding items not in source document
   - Exceeding available quantities
   - Over-consumption across multiple child documents (including parallel steps)
   - Creating duplicate Purchase Orders that exceed RFQ quantities

2. **Detailed Error Messages**: When validation fails, a rich HTML error shows:
   - Source quantity, consumed quantity, and available quantity
   - Links to the documents that have already consumed quantities (with draft/submitted status)
   - A tip with the maximum allowed quantity

3. **Parallel Step Awareness**: Quantities consumed by parallel steps (e.g., Purchase Requisition and Stock Entry from the same Material Request) are aggregated correctly

4. **Indirect Chain Tracking (RFQ → SQ → PO)**: When a Purchase Order is created from a Supplier Quotation (which came from an RFQ), the system tracks quantities against the original RFQ — not just the immediate Supplier Quotation. This prevents over-ordering when multiple Supplier Quotations exist for the same RFQ. Both **draft** and **submitted** POs are counted against the RFQ limit.

5. **Special Cases**:
   - **RFQ**: Quantity validation is skipped — multiple RFQs can request the same quantities for different suppliers
   - **Supplier Quotation**: Quantity validation is skipped — multiple SQs quote for the same quantities from different suppliers
   - **Purchase Order**: Quantities are tracked against the original RFQ (not the SQ) to prevent over-allocation across suppliers

## Validation Rules

### 1. Step Order Validation

**Rule**: Documents must be created in the correct order

**Example**: Cannot create Purchase Order without Request for Quotation

**Error Message**:
```
This document requires a source document from the previous step.
Please create it from the appropriate source document.
```

### 2. Quantity Limit Validation

**Rule**: Total quantities across all child documents in the same step number (parallel steps) cannot exceed source quantities

**Example (Parallel Steps)**: 
- Material Request has 100 units of Item A
- Stock Entry uses 30 units
- PR-001 uses 50 units
- PR-002 can only use maximum 20 units

**Example (RFQ → SQ → PO Chain)**:
- RFQ has 100 units of Item A
- Supplier Quotation from Supplier X quotes 100 units
- Supplier Quotation from Supplier Y quotes 100 units
- PO-001 (from SQ-X) orders 60 units → allowed
- PO-002 (from SQ-Y) tries to order 50 units → **blocked** (only 40 available across all POs from this RFQ)

**Error Message**:
```
Quantity for item [Item Code] exceeds available quantity.
Available: 40, Requested: 50, Already consumed: 60
```

### 3. Item Restriction Validation

**Rule**: Only items from source document can be included

**Example**: Cannot add Item B to Purchase Requisition if it doesn't exist in source Material Request

**Error Message**:
```
Item [Item Code] does not exist in source document [MR-00001]
```

### 4. Cancellation Protection

**Rule**: Documents with child documents cannot be cancelled

**Example**: Cannot cancel Purchase Requisition if RFQs exist

**Error Message**:
```
Cannot cancel this document. It has child documents:
Request for Quotation: RFQ-00001, RFQ-00002
```

## API Methods

### Python API

```python
import frappe
from next_custom_app.next_custom_app.utils.procurement_workflow import (
    get_active_flow,
    get_flow_steps,
    get_document_chain,
    get_available_quantities
)

# Get active workflow
flow = get_active_flow()

# Get workflow steps
steps = get_flow_steps(flow.name)

# Get document chain
chain = get_document_chain("Material Request", "MR-00001")

# Get available quantities
available = get_available_quantities(
    "Material Request",
    "MR-00001",
    "Purchase Requisition"
)
```

### REST API

```javascript
// Get active flow
frappe.call({
    method: "next_custom_app.next_custom_app.doctype.procurement_flow.procurement_flow.get_active_flow",
    callback: function(r) {
        console.log(r.message);
    }
});

// Get document chain
frappe.call({
    method: "next_custom_app.next_custom_app.utils.procurement_workflow.get_document_chain",
    args: {
        doctype: "Material Request",
        docname: "MR-00001"
    },
    callback: function(r) {
        console.log(r.message);
    }
});

// Get available quantities
frappe.call({
    method: "next_custom_app.next_custom_app.utils.procurement_workflow.get_available_quantities",
    args: {
        source_doctype: "Material Request",
        source_name: "MR-00001",
        target_doctype: "Purchase Requisition"
    },
    callback: function(r) {
        console.log(r.message);
    }
});
```

## Database Schema

### Custom Fields Added

All procurement doctypes (MR, PR, RFQ, SQ, PO, GRN, PI) receive these fields:

1. **procurement_links** (Table)
   - Links to child documents created from this document

2. **procurement_source_doctype** (Link)
   - DocType of the source document

3. **procurement_source_name** (Dynamic Link)
   - Name of the source document

### Custom DocTypes

1. **Procurement Flow**
   - Defines the overall workflow configuration
   - Only one can be active at a time

2. **Procurement Flow Steps** (Child Table)
   - Defines individual steps in the workflow
   - Sequential ordering enforced; duplicates allowed for parallel branches

3. **Procurement Rule Set** (Child Table)
   - Extensible rule definitions
   - JSON-based for flexibility

4. **Procurement Document Link** (Child Table)
   - Tracks document relationships
   - Stored in each parent document

## Troubleshooting

### Issue: "Another active flow exists"

**Solution**: Deactivate the existing flow before activating a new one

```python
# In bench console
flow = frappe.get_doc("Procurement Flow", "Old Flow Name")
flow.is_active = 0
flow.save()
```

### Issue: Custom fields not appearing

**Solution**: Reload/rebuild doctypes

```bash
bench --site your-site.local migrate
bench --site your-site.local clear-cache
```

**Or run setup manually:**
```python
from next_custom_app.next_custom_app.utils.procurement_workflow import setup_custom_fields
setup_custom_fields()
```

### Issue: Validation errors not showing

**Solution**: Check if flow is active

```python
from next_custom_app.next_custom_app.utils.procurement_workflow import get_active_flow
flow = get_active_flow()
print(flow)  # Should return active flow
```

### Issue: Document chain not showing

**Solution**: 
1. Ensure documents are submitted (not draft)
2. Check that procurement_links table has entries
3. Verify JavaScript is loaded: Check browser console for errors

## Advanced Configuration

### Customizing Validation Logic

Edit [`next_custom_app/next_custom_app/utils/procurement_workflow.py`](next_custom_app/next_custom_app/utils/procurement_workflow.py) to add custom validation:

```python
def validate_custom_rule(doc):
    """Add your custom validation logic"""
    if doc.custom_field == "value":
        frappe.throw("Custom validation failed")

# Add to validate_procurement_document function
```

### Adding Custom UI Elements

Edit [`next_custom_app/public/js/procurement_custom_tabs.js`](next_custom_app/public/js/procurement_custom_tabs.js) for per-doctype UI enhancements.

### Extending to New DocTypes

**For doctypes with items tables** (e.g., Purchase Receipt, Purchase Invoice):
1. Add doctype to `PROCUREMENT_DOCTYPES` in [`procurement_workflow.py`](next_custom_app/next_custom_app/utils/procurement_workflow.py)
2. Add items field mapping in `get_items_field_name()`
3. Run `setup_custom_fields()`
4. Update [`hooks.py`](next_custom_app/hooks.py) with `doc_events` and `doctype_js`
5. The button override will automatically pick up new doctypes from the active flow

**For doctypes without items tables** (e.g., Payment Entry, Payment Request):
1. Add the doctype to the Procurement Flow Steps in the UI
2. The `make_procurement_document()` function will automatically detect that the target has no items table and use reference field mapping instead (via `_set_reference_fields()`)
3. Update [`hooks.py`](next_custom_app/hooks.py) with `doc_events` if validation is needed
4. Optionally extend `_set_reference_fields()` in [`procurement_workflow.py`](next_custom_app/next_custom_app/utils/procurement_workflow.py) for doctype-specific field mapping

## Payment Request Customization

The app includes automatic customization for Payment Request documents:

### Features

1. **Payment Request Type**: Automatically set to "Outward" and disabled
2. **Custom Fields**:
   - `custom_requested_by`: Stores the full name of the user who created the request
   - `custom_requested_by_email`: Stores the email of the user who created the request
3. **Mode of Payment**: Automatically set to "Cash" if available (not disabled, can be changed)
4. **Field Copying**: Automatically copies `project` and `cost_center` from the linked Purchase Order

### Custom Fields Setup

Custom fields are automatically created during app installation and after migration via the `after_migrate` hook. To manually set up:

```python
# In bench console
bench --site <site> console

from next_custom_app.next_custom_app.utils.payment_request_utils import setup_all_payment_request_fields
setup_all_payment_request_fields()
```

## User Custom Fields (Purchaser Management)

The app adds custom fields to the User doctype for purchaser management:

### Custom Fields

1. **Is Purchaser** (`custom_is_purchaser`): Check field to mark users as purchasers in the procurement workflow
2. **Suspense Account** (`custom_suspense_account`): Link to Account - used as the parent account for the user's receivable accounts

### Linking Suspense Accounts

When a user with `custom_is_purchaser` enabled saves, their receivable accounts can be automatically linked to the suspense account as the parent.

To manually link suspense accounts for all purchaser users:

```python
# In bench console
bench --site <site> console

from next_custom_app.next_custom_app.utils.payment_request_utils import link_suspense_account_to_receivables
link_suspense_account_to_receivables()
```

This will find all receivable accounts matching the user's name/email and set their `parent_account` to the user's suspense account.

## Architecture

### File Structure

 | File | Purpose |
 |------|---------|
 | [`procurement_button_override.js`](next_custom_app/public/js/procurement_button_override.js) | Global script (via `app_include_js`) that intercepts `make_custom_buttons` and `add_custom_button` to suppress ERPNext default buttons on submitted procurement documents — zero flicker |
 | [`procurement_custom_tabs.js`](next_custom_app/public/js/procurement_custom_tabs.js) | Per-doctype script (via `doctype_js`) that adds workflow "Create" buttons, document flow section, and linked document display |
 | [`purchase_order_po_control.js`](next_custom_app/public/js/purchase_order_po_control.js) | PO-specific: supplier validation when created from Supplier Quotation |
 | [`payment_request.js`](next_custom_app/public/js/payment_request.js) | Payment Request customization: sets payment_request_type to Outward, adds requested_by fields, copies project/cost_center from PO |
 | [`procurement_workflow.py`](next_custom_app/next_custom_app/utils/procurement_workflow.py) | Server-side: all validation, document creation, quantity tracking, indirect chain resolution, and API endpoints |
 | [`payment_request_utils.py`](next_custom_app/next_custom_app/utils/payment_request_utils.py) | Payment Request and User custom fields setup, suspense account linking utilities |
 | [`po_quantity_control.py`](next_custom_app/next_custom_app/utils/po_quantity_control.py) | PO-specific: RFQ quantity enforcement, dynamic ordered quantity calculation, RFQ ordered_qty field updates |
 | [`hooks.py`](next_custom_app/hooks.py) | App configuration: JS load order, doc_events, doctype_js |

### Button Override Strategy

ERPNext form controllers (e.g., `material_request.js`, `purchase_order.js`) add default "Create ▼" dropdown buttons via two mechanisms:
1. `make_custom_buttons()` method — called during `refresh`
2. Direct `frm.add_custom_button()` calls in the `refresh` handler (e.g., "Update Items", "Close", "Payment")

Our override uses a **two-layer zero-flicker approach**:

**Layer 1: `make_custom_buttons` interception**
1. **`procurement_button_override.js`** loads globally via `app_include_js` — before any doctype JS
2. It registers `frappe.ui.form.on(doctype, { setup() })` for all procurement doctypes
3. In `setup`, it monkey-patches `frm.events.make_custom_buttons` to be a no-op for submitted docs (`docstatus >= 1`)
4. For draft docs (`docstatus === 0`), the original ERPNext behaviour is preserved

**Layer 2: `add_custom_button` interceptor**
1. In the `refresh` handler, for submitted docs, an interceptor is installed on `frm.add_custom_button`
2. The interceptor blocks known default ERPNext button labels (e.g., "Purchase Receipt", "Update Items", "Payment") before they reach the DOM
3. Workflow buttons from `procurement_custom_tabs.js` are allowed through via a `_procurement_allow_buttons` flag
4. This prevents flicker because buttons are never added to the DOM in the first place

**Doctype Discovery**: The list of doctypes is fetched dynamically from the active Procurement Flow via `get_procurement_doctypes()` API, with a hardcoded fallback for immediate coverage

### Field Propagation

When creating the next document via `make_procurement_document()`, these header fields are automatically copied (when present in both source and target):

- **Core**: company, currency, conversion_rate
- **Accounting**: cost_center, project
- **Pricing**: buying_price_list, price_list_currency, plc_conversion_rate
- **Taxes**: taxes_and_charges, shipping_rule
- **Discounts**: apply_discount_on, additional_discount_percentage, discount_amount
- **Terms**: tc_name, terms
- **Printing**: letter_head, select_print_heading, language
- **Warehouse**: set_warehouse, set_from_warehouse, set_reserve_warehouse
- **Supplier**: supplier, supplier_name, supplier_address, contact_person, etc.
- **Payment**: payment_terms_template
- **Type**: material_request_type

Item-level fields copied: item_code, qty, uom, item_name, description, rate, warehouse, schedule_date, project, cost_center, conversion_factor, stock_uom, stock_qty, image, item_group, brand, manufacturer, manufacturer_part_no.

## Best Practices

### 1. Workflow Design

- ✅ Keep workflows simple and linear
- ✅ Use meaningful step numbers (1, 2, 3...)
- ✅ Always set "Requires Source" for dependent steps
- ✅ Use Step Groups for parallel steps (e.g., `S2_PARALLEL`)
- ❌ Avoid circular dependencies

### 2. Document Creation

- ✅ Always create from the workflow **Create** button on submitted documents
- ✅ Submit documents in sequence
- ✅ The system enforces quantity limits automatically on save
- ❌ Don't manually create documents when `Requires Source` is checked in the workflow

### 3. Cancellation

- ✅ Cancel in reverse order (child → parent)
- ✅ Check for dependent documents before cancelling
- ❌ Don't force-cancel documents with children

### 4. Testing

- ✅ Test workflow with sample data first
- ✅ Verify quantity validations work correctly
- ✅ Test cancellation protection
- ✅ Test with users who have limited permissions
- ❌ Don't activate untested workflows in production

## Support and Contribution

For issues, feature requests, or contributions:
- GitHub: [Repository URL]
- Email: info@nextcoretechnologies.com

## License

MIT License - See LICENSE file for details

## Version History

**v1.3.0** (2026-03-17)
- **Fixed PO quantity limit enforcement**: Purchase Orders created from RFQ → Supplier Quotation flow now correctly enforce quantity limits. The system resolves the indirect chain (PO → SQ → RFQ) to track consumed quantities across all POs from the same RFQ
- **Duplicate PO prevention**: Both draft and submitted POs are counted against RFQ quantities, preventing duplicate Purchase Orders. Previously only submitted POs were counted, allowing unlimited draft POs
- **Enhanced button override**: Added `add_custom_button` interceptor layer to suppress ERPNext buttons added directly in controller `refresh` handlers (e.g., "Update Items", "Close", "Payment" on Purchase Order) — zero flicker
- **Non-items doctype support**: `make_procurement_document()` now handles doctypes without items tables (e.g., Payment Entry, Payment Request) via reference field mapping instead of throwing "Cannot map items between these document types"
- **Detailed PO error messages**: Quantity exceeded errors now show a breakdown of all existing POs (with draft/submitted status) and links to each document
- **Dynamic quantity calculation**: `validate_po_against_rfq()` now uses dynamic calculation from database instead of relying on stored `ordered_qty` field, which was only updated on PO submit

**v1.2.0** (2026-03-17)
- **Zero-flicker button override**: Default ERPNext "Create" buttons are now suppressed at the controller level via `procurement_button_override.js` — no DOM hacks
- **Dynamic doctype discovery**: Procurement doctypes are fetched from the active Procurement Flow via `get_procurement_doctypes()` API
- **Permission check on creation**: Server-side `frappe.has_permission()` check when creating the next document
- **Expanded field propagation**: 40+ header fields (project, cost center, supplier, terms, etc.) are now copied to the next document
- **Source document enforcement**: When `Requires Source` is checked, manual creation without a source is blocked
- **Removed PO grid indicators**: RFQ quantity indicators removed from PO items grid (quantity validation is server-side)
- **Renamed button group**: "Next Step" dropdown renamed to "Create" for consistency
- **Deleted `material_request_override.js`**: Replaced by the global `procurement_button_override.js`
- **Removed `override_doctype_class`**: Python-side Material Request override was a no-op

**v1.1.0** (2025-12-xx)
- Document flow visualization
- Procurement analysis dialog
- RFQ pivot view and comparison
- PO quantity control

**v1.0.0** (2025-11-26)
- Initial release
- Dynamic workflow configuration
- Quantity validation
- Document chain tracking
- UI enhancements
