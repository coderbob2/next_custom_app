# Dynamic Procurement Workflow Engine for ERPNext

A fully configurable procurement workflow system for ERPNext 15 that enables dynamic document sequencing, quantity validation, and complete procurement chain tracking without hardcoded logic.

## 🎯 Key Features

- **100% Configuration-Driven**: Define workflows through UI, not code
- **Automatic Quantity Validation**: Prevents over-consumption across document chains
- **Item Restriction Enforcement**: Only approved items flow through the workflow
- **Complete Document Tracking**: Full backward and forward document chain visibility
- **Cancellation Protection**: Prevents deletion when child documents exist
- **Real-time UI Updates**: Live tracking of available quantities and document chains
- **Extensible Architecture**: JSON-based rule system for custom validations

## 📋 Supported Documents

- Material Request (MR)
- Purchase Requisition (PR)
- Request for Quotation (RFQ)
- Supplier Quotation (SQ)
- Purchase Order (PO)
- Purchase Receipt (GRN)
- Purchase Invoice (PI)

## 🚀 Quick Start

### Installation

```bash
# 1. Get the app
cd ~/frappe-bench
bench get-app https://github.com/your-org/next_custom_app

# 2. Install on your site
bench --site your-site.local install-app next_custom_app

# 3. Setup custom fields (if not auto-installed)
bench --site your-site.local console
>>> from next_custom_app.next_custom_app.utils.procurement_workflow import setup_custom_fields
>>> setup_custom_fields()
```

### Basic Configuration

1. **Create a Procurement Flow**
   ```
   Navigate to: Desk → Procurement Flow → New
   
   - Flow Name: "Standard Procurement"
   - Is Active: ✓ (checked)
   - Add Steps (in order):
     1. Material Request (no source required)
     2. Purchase Requisition (requires source)
     3. Request for Quotation (requires source)
     4. Supplier Quotation (requires source)
     5. Purchase Order (requires source)
     6. Purchase Receipt (requires source)
     7. Purchase Invoice (requires source)
   ```

2. **Use the Workflow**
   ```
   Create Material Request → Submit
   Create PR from MR → System validates items & quantities
   Create RFQ from PR → System tracks chain
   ... continue through workflow
   ```

## 🏗️ Architecture

### DocTypes Created

1. **Procurement Flow** - Main configuration doctype
2. **Procurement Flow Steps** - Child table for workflow steps
3. **Procurement Rule Set** - Child table for validation rules
4. **Procurement Document Link** - Child table for document tracking

### Custom Fields Added

Each procurement document gets:
- `procurement_source_doctype` - Link to source document type
- `procurement_source_name` - Name of source document
- `procurement_links` - Table of child documents

### Workflow Hooks

```python
doc_events = {
    "<Procurement DocType>": {
        "validate": "validate_procurement_document",
        "on_submit": "on_procurement_submit",
        "before_cancel": "check_can_cancel"
    }
}
```

## 📖 Usage Examples

### Example 1: Standard Procurement Flow

```python
# 1. Create Material Request
mr = frappe.get_doc({
    "doctype": "Material Request",
    "transaction_date": today(),
    "items": [{
        "item_code": "ITEM-001",
        "qty": 100,
        "schedule_date": today()
    }]
})
mr.insert()
mr.submit()

# 2. Create Purchase Requisition from MR
pr = frappe.get_doc({
    "doctype": "Purchase Requisition",
    "procurement_source_doctype": "Material Request",
    "procurement_source_name": mr.name,
    "items": [{
        "item_code": "ITEM-001",
        "qty": 60  # System validates: 60 ≤ 100 ✓
    }]
})
pr.insert()
pr.submit()

# 3. Another PR from same MR
pr2 = frappe.get_doc({
    "doctype": "Purchase Requisition",
    "procurement_source_doctype": "Material Request",
    "procurement_source_name": mr.name,
    "items": [{
        "item_code": "ITEM-001",
        "qty": 45  # System validates: 60 + 45 ≤ 100 ✗ Will fail!
    }]
})
# This will throw: Quantity exceeds requested quantity
```

### Example 2: Query Document Chain

```python
from next_custom_app.next_custom_app.utils.procurement_workflow import get_document_chain

chain = get_document_chain("Purchase Order", "PO-00001")

print(chain)
# {
#     "backward": [
#         {"doctype": "Material Request", "name": "MR-00001"},
#         {"doctype": "Purchase Requisition", "name": "PR-00001"},
#         {"doctype": "Request for Quotation", "name": "RFQ-00001"},
#         {"doctype": "Supplier Quotation", "name": "SQ-00001"}
#     ],
#     "forward": [
#         {"doctype": "Purchase Receipt", "name": "GRN-00001"}
#     ]
# }
```

### Example 3: Check Available Quantities

```python
from next_custom_app.next_custom_app.utils.procurement_workflow import get_available_quantities

available = get_available_quantities(
    source_doctype="Material Request",
    source_name="MR-00001",
    target_doctype="Purchase Requisition"
)

print(available)
# {
#     "ITEM-001": {
#         "source_qty": 100,
#         "consumed_qty": 60,
#         "available_qty": 40
#     }
# }
```

## 🔒 Validation Rules

### 1. Step Order Validation
- Documents must be created from correct source
- Enforces sequential workflow

### 2. Quantity Validation
- Tracks consumed quantities per item
- Prevents over-consumption
- Validates across multiple child documents

### 3. Item Validation
- Only items from source can be used
- No unauthorized items allowed

### 4. Cancellation Protection
- Cannot cancel if child documents exist
- Must cancel in reverse order

## 🛠️ API Reference

### Python API

```python
from next_custom_app.next_custom_app.utils.procurement_workflow import (
    # Configuration
    get_active_flow,
    get_flow_steps,
    get_current_step,
    get_previous_step,
    get_next_step,
    
    # Validation
    validate_step_order,
    validate_quantity_limits,
    validate_items_against_source,
    
    # Document Operations
    get_document_chain,
    get_available_quantities,
    create_backward_link,
    check_can_cancel,
    
    # Setup
    setup_custom_fields
)
```

### REST API

```javascript
// Get active flow
frappe.call({
    method: "next_custom_app.next_custom_app.doctype.procurement_flow.procurement_flow.get_active_flow"
});

// Get document chain
frappe.call({
    method: "next_custom_app.next_custom_app.utils.procurement_workflow.get_document_chain",
    args: {doctype: "Material Request", docname: "MR-00001"}
});

// Get available quantities
frappe.call({
    method: "next_custom_app.next_custom_app.utils.procurement_workflow.get_available_quantities",
    args: {
        source_doctype: "Material Request",
        source_name: "MR-00001",
        target_doctype: "Purchase Requisition"
    }
});
```

## 📁 Project Structure

```
next_custom_app/
├── next_custom_app/
│   ├── doctype/
│   │   ├── procurement_flow/              # Main workflow config
│   │   ├── procurement_flow_steps/        # Workflow step definitions
│   │   ├── procurement_rule_set/          # Validation rules
│   │   └── procurement_document_link/     # Document relationships
│   ├── utils/
│   │   └── procurement_workflow.py        # Core workflow logic
│   └── install.py                         # Installation script
├── public/
│   └── js/
│       └── procurement_workflow.js        # Client-side enhancements
├── hooks.py                               # Frappe hooks
├── PROCUREMENT_WORKFLOW_GUIDE.md         # Detailed user guide
└── README_PROCUREMENT.md                 # This file
```

## 🧪 Testing

### Test Workflow Configuration

```bash
# In bench console
bench --site your-site.local console

# Test 1: Create and activate flow
flow = frappe.get_doc({
    "doctype": "Procurement Flow",
    "flow_name": "Test Flow",
    "is_active": 1,
    "flow_steps": [
        {"step_no": 1, "doctype_name": "Material Request", "requires_source": 0},
        {"step_no": 2, "doctype_name": "Purchase Requisition", "requires_source": 1}
    ]
})
flow.insert()

# Test 2: Verify active flow
from next_custom_app.next_custom_app.utils.procurement_workflow import get_active_flow
active = get_active_flow()
print(active)

# Test 3: Test quantity validation
# Create MR, then PR with excess quantity - should fail
```

## 🐛 Troubleshooting

### Custom Fields Not Showing

```bash
# Solution 1: Clear cache
bench --site your-site.local clear-cache

# Solution 2: Migrate
bench --site your-site.local migrate

# Solution 3: Manually run setup
bench --site your-site.local console
>>> from next_custom_app.next_custom_app.utils.procurement_workflow import setup_custom_fields
>>> setup_custom_fields()
```

### Validation Not Working

```python
# Check if flow is active
from next_custom_app.next_custom_app.utils.procurement_workflow import get_active_flow
flow = get_active_flow()
if not flow:
    print("No active flow found!")
```

### Document Chain Not Displaying

1. Check browser console for JavaScript errors
2. Verify documents are submitted (not draft)
3. Check procurement_links table has data

## 🤝 Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open Pull Request

## 📄 License

MIT License - See LICENSE file

## 📞 Support

- **Documentation**: See [PROCUREMENT_WORKFLOW_GUIDE.md](PROCUREMENT_WORKFLOW_GUIDE.md)
- **Issues**: GitHub Issues
- **Email**: info@nextcoretechnologies.com

## 🎉 Credits

Developed by Nextcore Technologies for ERPNext 15

---

**Version**: 1.0.0  
**Last Updated**: 2025-11-26  
**ERPNext Version**: 15.x