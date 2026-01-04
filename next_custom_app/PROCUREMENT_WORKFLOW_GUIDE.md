# Procurement Workflow Engine - User Guide

## Overview

This custom ERPNext Custom App provides a fully configurable procurement workflow engine where the sequence of documents, validation rules, and item restrictions are defined through configuration rather than hardcoded logic.

## Features

✅ **Dynamic Workflow Configuration**: Define document sequences through UI
✅ **Quantity Validation**: Automatic enforcement of quantity limits across workflow steps
✅ **Item Restrictions**: Ensure only approved items flow through the procurement chain
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

Navigate to: **Desk → Next Custom App → Procurement Flow**

## Configuration

### Step 1: Create a Procurement Flow

1. Go to **Procurement Flow** list
2. Click **New**
3. Fill in the details:
   - **Flow Name**: e.g., "Standard Procurement Flow"
   - **Is Active**: Check this box (only one flow can be active)
   - **Description**: Optional description of the workflow

### Step 2: Define Workflow Steps

In the **Flow Steps** table, add steps in sequential order:

| Step No | DocType | Allowed Actions | Requires Source |
|---------|---------|----------------|-----------------|
| 1 | Material Request | Create | ☐ |
| 2 | Purchase Requisition | Create | ☑ |
| 3 | Request for Quotation | Create | ☑ |
| 4 | Supplier Quotation | Create | ☑ |
| 5 | Purchase Order | Create | ☑ |
| 6 | Purchase Receipt | Create | ☑ |
| 7 | Purchase Invoice | Create | ☑ |

**Field Descriptions:**
- **Step No**: Sequential number (must be 1, 2, 3, etc.)
- **DocType**: The document type for this step
- **Allowed Actions**: Create, Update, or Complete (for future extensibility)
- **Requires Source**: If checked, documents must be created from previous step

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

#### 2. Create Purchase Requisition (from Material Request)

**Option A: From Material Request**
1. Open the submitted Material Request
2. Click **Create → Purchase Requisition**
3. The system automatically:
   - Links to source Material Request
   - Validates items exist in source
   - Checks quantity limits

**Option B: Manual Creation**
1. Go to **Purchase Requisition → New**
2. Set custom fields:
   - **Procurement Source DocType**: Material Request
   - **Procurement Source Name**: MR-00001
3. Add items (must exist in source MR)

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

When creating a document from a source:

1. **Available Quantities Display**: Each item row shows:
   ```
   Available: 50 (Source: 100, Consumed: 50)
   ```

2. **Automatic Validation**: System prevents:
   - Adding items not in source document
   - Exceeding available quantities
   - Over-consumption across multiple child documents

3. **Real-time Updates**: Quantities update as you modify the document

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

**Rule**: Total quantities across all child documents cannot exceed source quantities

**Example**: 
- Material Request has 100 units of Item A
- PR-001 uses 60 units
- PR-002 can only use maximum 40 units

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
   - Sequential ordering enforced

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

Edit [`next_custom_app/public/js/procurement_workflow.js`](next_custom_app/public/js/procurement_workflow.js):

```javascript
next_custom_app.procurement_workflow.custom_action = function(frm) {
    // Your custom UI logic
};
```

### Extending to New DocTypes

1. Add doctype to PROCUREMENT_DOCTYPES in [`procurement_workflow.py`](next_custom_app/next_custom_app/utils/procurement_workflow.py)
2. Add items field mapping in get_items_field_name()
3. Run setup_custom_fields()
4. Update hooks.py with doc_events

## Best Practices

### 1. Workflow Design

- ✅ Keep workflows simple and linear
- ✅ Use meaningful step numbers (1, 2, 3...)
- ✅ Always set "Requires Source" for dependent steps
- ❌ Avoid circular dependencies

### 2. Document Creation

- ✅ Always create from source documents when available
- ✅ Submit documents in sequence
- ✅ Review available quantities before creating child docs
- ❌ Don't manually set source references unless necessary

### 3. Cancellation

- ✅ Cancel in reverse order (child -> parent)
- ✅ Check for dependent documents before cancelling
- ❌ Don't force-cancel documents with children

### 4. Testing

- ✅ Test workflow with sample data first
- ✅ Verify quantity validations work correctly
- ✅ Test cancellation protection
- ❌ Don't activate untested workflows in production

## Support and Contribution

For issues, feature requests, or contributions:
- GitHub: [Repository URL]
- Email: info@nextcoretechnologies.com

## License

MIT License - See LICENSE file for details

## Version History

**v1.0.0** (2025-11-26)
- Initial release
- Dynamic workflow configuration
- Quantity validation
- Document chain tracking
- UI enhancements