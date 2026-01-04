# Next Custom App

Custom ERPNext application for extended functionality and custom requirements.

## Features

### 🔄 Dynamic Procurement Workflow Engine

A fully configurable procurement workflow system that enables:
- Dynamic document sequencing through UI configuration
- Automatic quantity validation across procurement chains
- Complete document tracking and history
- Item restriction enforcement
- Cancellation protection for documents with children

**Key Capabilities:**
- Configure workflow steps (MR → PR → RFQ → SQ → PO → GRN/PI)
- Enforce quantity limits automatically
- Track complete document chains
- Real-time available quantity display
- Prevent over-consumption and unauthorized items

📖 **[Full Procurement Workflow Documentation →](README_PROCUREMENT.md)**

📚 **[Detailed User Guide →](PROCUREMENT_WORKFLOW_GUIDE.md)**

## Installation

```bash
# Get the app
cd ~/frappe-bench
bench get-app https://github.com/your-org/next_custom_app

# Install on your site
bench --site your-site.local install-app next_custom_app

# Migrate and clear cache
bench --site your-site.local migrate
bench --site your-site.local clear-cache
```

## Quick Start - Procurement Workflow

1. **Setup Custom Fields** (if not auto-created during installation):
```bash
bench --site your-site.local console
>>> from next_custom_app.next_custom_app.utils.procurement_workflow import setup_custom_fields
>>> setup_custom_fields()
```

2. **Create a Procurement Flow**:
   - Navigate to: **Desk → Procurement Flow → New**
   - Add workflow steps in sequential order
   - Activate the flow

3. **Start Using**:
   - Create documents following the configured workflow
   - System automatically validates quantities and items
   - View document chains in real-time

## Project Structure

```
next_custom_app/
├── next_custom_app/
│   ├── doctype/                    # Custom DocTypes
│   │   ├── procurement_flow/
│   │   ├── procurement_flow_steps/
│   │   ├── procurement_rule_set/
│   │   └── procurement_document_link/
│   ├── utils/                      # Utility modules
│   │   └── procurement_workflow.py
│   └── install.py                  # Installation scripts
├── public/
│   └── js/                         # Client-side scripts
│       └── procurement_workflow.js
├── hooks.py                        # ERPNext hooks
├── README_PROCUREMENT.md           # Detailed feature docs
└── PROCUREMENT_WORKFLOW_GUIDE.md  # User guide
```

## Documentation

- **[Main README](README.md)** - This file
- **[Procurement System Overview](README_PROCUREMENT.md)** - Feature documentation
- **[Procurement User Guide](PROCUREMENT_WORKFLOW_GUIDE.md)** - Step-by-step guide
- **[License](license.txt)** - MIT License

## Support

- **Issues**: GitHub Issues
- **Email**: info@nextcoretechnologies.com

## License

MIT License - See [license.txt](license.txt)

---

**Developed by**: Nextcore Technologies  
**Version**: 1.0.0  
**Compatible with**: ERPNext 15.x