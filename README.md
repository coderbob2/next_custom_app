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

### 🔔 Background Desktop Notifications (WhatsApp-Web Style)

This app supports two delivery channels:

- **Realtime (`frappe.publish_realtime`)**: works while a Desk tab is open.
- **Web Push + Service Worker**: works even when ERPNext is not open in any tab (browser may be running in background).

#### Requirements

- HTTPS (or localhost in development)
- Browser notification permission: **Allow**
- Service Worker registration
- Stored push subscription per user
- Backend package: `pywebpush`
- VAPID keys in site config

#### Setup

1. Install push package:

```bash
bench pip install pywebpush
bench restart
```

2. Generate VAPID keys (inside the **bench Python environment**):

```bash
bench pip install pywebpush py-vapid
bench --site your-site.local console
# then run inside console:
from py_vapid import Vapid
from cryptography.hazmat.primitives import serialization
import base64

v = Vapid()
v.generate_keys()

public_bytes = v.public_key.public_bytes(
    encoding=serialization.Encoding.X962,
    format=serialization.PublicFormat.UncompressedPoint,
)
private_bytes = v.private_key.private_numbers().private_value.to_bytes(32, "big")

public_key = base64.urlsafe_b64encode(public_bytes).rstrip(b"=").decode("utf-8")
private_key = base64.urlsafe_b64encode(private_bytes).rstrip(b"=").decode("utf-8")

print(public_key)
print(private_key)
```

If you run [`python3 -m pywebpush --generate-vapid-keys`](README.md:52) with system Python, it may fail with `No module named pywebpush` because the package is installed in bench env, not system env.

3. Add keys to site config (`sites/<site>/site_config.json`):

```json
{
  "vapid_public_key": "<YOUR_PUBLIC_KEY>",
  "vapid_private_key": "<YOUR_PRIVATE_KEY>",
  "vapid_subject": "mailto:info@nextcoretechnologies.com"
}
```

4. Build assets and clear cache:

```bash
bench build --app next_custom_app
bench clear-cache
bench restart
```

#### Data model used for subscriptions

DocType: **Push Subscription**

- `user` (Link → User)
- `endpoint` (Data, unique)
- `p256dh` (Data)
- `auth` (Data)
- `browser` (Data)
- `enabled` (Check)

Only subscriptions with `enabled = 1` are used for push delivery.

#### Runtime behavior

- Workflow state changes are detected in backend document events.
- Backend sends:
  - Notification Log (in-app fallback)
  - Realtime event (when user is online in Desk)
  - Web Push payload (for OS notification cards/background delivery)
- Service Worker shows OS notification card and opens/focuses ERPNext route on click.

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
