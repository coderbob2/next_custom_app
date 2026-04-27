# NYG Custom App — Project Understanding

## What this project is

`next_custom_app` is a custom Frappe/ERPNext app built on top of ERPNext 15.x.

From the files I reviewed, this app is primarily a **procurement workflow extension** for ERPNext, with additional customization around:

- a configurable procurement document flow
- a custom **Purchase Requisition** DocType
- quantity and item-control rules across procurement documents
- document-chain tracking between procurement records
- RFQ supplier comparison and award tooling
- Payment Request / Payment Entry customization for purchaser-driven suspense-account handling
- UI overrides to replace ERPNext's default procurement buttons with this app's controlled workflow actions

---

## My high-level understanding of the business goal

The app is trying to make ERPNext procurement behave in a stricter, more guided, and more traceable way than standard ERPNext.

Instead of letting users freely create downstream procurement documents with default ERPNext buttons, this app introduces a **controlled workflow engine** where:

1. the allowed sequence of documents is configurable
2. source-document relationships are enforced
3. quantities cannot be over-consumed across the chain
4. users see only the next valid actions
5. all related documents are linked into a visible audit trail

In short:

> this app turns procurement into a configuration-driven workflow with server-side validation and custom UX.

---

## Core architecture I found

## 1. Hooks-driven customization layer

The main integration point is `hooks.py`.

What it does:

- registers client scripts for procurement doctypes
- injects global JS and CSS
- runs install / migrate hooks
- attaches server-side document event handlers
- overrides linked-document behavior for procurement visibility

Important hook patterns I found:

- `after_install` -> creates/setup custom doctypes + custom fields
- `after_migrate` -> re-runs centralized custom field setup
- `doc_events` -> enforces workflow validation and submit/cancel logic
- `override_whitelisted_methods` -> custom linked-doc behavior
- `app_include_js` -> globally loads procurement button override before form scripts

This tells me the app is designed to integrate deeply into ERPNext lifecycle events rather than acting as a standalone module.

---

## 2. Central procurement workflow engine

The heart of the project is:

- `next_custom_app/next_custom_app/utils/procurement_workflow.py`

This is the core engine.

From the functions and code I reviewed, it handles:

- resolving the active procurement flow
- reading flow steps
- identifying previous / next steps
- validating source-document order
- validating quantity limits
- validating item consistency against source docs
- normalizing source references
- creating backward links between documents
- building document chains and flow trees
- cancellation protection
- calculating consumed and available quantities
- creating the next procurement document (`make_procurement_document`)
- RFQ pivot data / supplier quotation generation
- payment request / payment entry submission linking

This file is effectively the domain service layer for procurement.

---

## 3. Configuration-driven workflow model

The procurement process is not fully hardcoded. It is defined through custom DocTypes:

### Custom DocTypes identified

- `Procurement Flow`
- `Procurement Flow Steps`
- `Procurement Rule Set`
- `Procurement Document Link`
- `Purchase Requisition`
- `Purchase Requisition Item`
- `RFQ Supplier Rule`
- `Supplier Comparison` (+ child doctypes)

### What they appear to do

#### Procurement Flow
Stores the master workflow definition:
- flow name
- active flag
- description
- child table of steps
- child table of validation rules

#### Procurement Flow Steps
Defines each step in sequence with:
- `step_no`
- target `doctype_name`
- `step_group` for parallel branches
- `allowed_actions`
- optional role restriction
- `requires_source`
- `is_final_step`

This is important because it means the project supports:
- sequential flows
- parallel steps
- role-filtered create actions
- terminal steps

#### Procurement Rule Set
Stores JSON-based rules such as:
- quantity limit
- item restriction
- source required
- backward-link required

This suggests extensibility was intended beyond the currently implemented logic.

#### Procurement Document Link
Acts as the relational audit table that stores:
- source doctype/docname
- target doctype/docname
- link date

This supports the document-chain UI and cancellation protection.

---

## 4. Custom Purchase Requisition layer

A major customization is the custom `Purchase Requisition` DocType.

From the JSON definition, it behaves like a structured procurement document with:

- naming series
- requisition purpose
- company
- dates
- warehouse defaults
- items child table
- terms/conditions
- progress fields like ordered / received percentages

From `custom_fields.py`, I also saw the app ensures header-level fields like:
- `project`
- `cost_center`

exist on Purchase Requisition, likely because the business expects those dimensions to propagate from Material Request and into downstream documents.

The Python controller itself is minimal, which means most business logic is not in the DocType class, but in the workflow utility layer and hooks.

---

## 5. Centralized custom field management

The project has a clear pattern for schema customization:

- `next_custom_app/next_custom_app/custom_fields.py`

This is the single source of truth for custom fields.

It adds procurement tracking fields to multiple doctypes:

- Material Request
- Purchase Requisition
- Request for Quotation
- Supplier Quotation
- Purchase Order
- Purchase Receipt
- Purchase Invoice
- Stock Entry
- Payment Request
- Payment Entry

Common tracking fields include:
- `procurement_source_doctype`
- `procurement_source_name`
- `procurement_links`

This tells me the app wants every procurement document to be source-aware and chain-aware.

It also adds specialized fields for:

### Payment Request
- destination selection
- requested-by fields
- purchase user
- suspense account

### User
- purchaser flag
- purchaser suspense parent account

So the app has two major customization domains:
1. procurement chain tracking
2. purchaser/payment accounting behavior

---

## 6. Payment Request / Payment Entry customization

Another strong subsystem is:

- `next_custom_app/next_custom_app/utils/payment_request_utils.py`
- `public/js/payment_request.js`
- `public/js/payment_entry.js`
- `public/js/user.js`

### What I understood

This part customizes how payment requests and payment entries behave when they are created from the procurement flow.

Main concepts:

- Payment Request type is forced to `Outward`
- a custom destination determines whether payment goes to:
  - purchaser suspense
  - direct supplier payment
- purchaser identity is tracked using custom fields
- purchaser-specific suspense accounts are resolved dynamically
- Payment Entry can be forced into **Internal Transfer** mode for suspense flows
- user records can be marked as purchasers and linked to suspense accounts

### Business interpretation

This looks like a business process where purchase-related cash movements may first be posted to a purchaser-specific suspense structure before final settlement, instead of always going directly through the normal supplier flow.

That means this app is not only extending procurement documents, but also aligning procurement with a custom accounting/payment control model.

---

## 7. RFQ and supplier comparison tooling

I found two RFQ-related UX features:

### A. RFQ pivot pricing entry
Files:
- `public/js/rfq_pivot_view.js`
- backend support in `procurement_workflow.py`

This provides a pivot-style dialog where users can:
- see RFQ items vs suppliers
- enter supplier prices in a matrix
- bulk-create Supplier Quotations from that matrix
- optionally work across currencies

### B. RFQ supplier comparison and award
Files:
- `public/js/rfq_comparison.js`
- `doctype/supplier_comparison/supplier_comparison.py`

This provides live comparison of submitted Supplier Quotations, including:
- supplier totals
- item-wise price comparison
- multi-currency normalization to company currency
- winner by total price
- winner by best item prices
- action to award supplier and create Purchase Order

### Business interpretation

This means the project is not only about moving documents through a workflow. It also supports supplier-selection decision making inside ERPNext.

---

## 8. Purchase Order quantity control against RFQ

I reviewed:

- `next_custom_app/next_custom_app/utils/po_quantity_control.py`
- `public/js/purchase_order_po_control.js`

Key understanding:

When a Purchase Order is created from a Supplier Quotation, the app traces back to the original RFQ and validates quantities against the RFQ total, not only against the immediate SQ.

This is important because multiple suppliers may quote against the same RFQ, and the project wants to prevent the total PO quantity across all awarded suppliers from exceeding the RFQ quantity.

The module also counts:
- draft POs
- submitted POs

That means the project intentionally prevents duplicate or parallel over-allocation before submission, not only after submission.

This is one of the most business-critical controls in the codebase.

---

## 9. UI strategy: replace ERPNext default create flow

A very important frontend pattern appears in:

- `public/js/procurement_button_override.js`
- `public/js/procurement_custom_tabs.js`

### What these scripts do

#### procurement_button_override.js
- globally intercepts ERPNext `make_custom_buttons`
- suppresses default ERPNext create buttons for submitted procurement docs
- prevents UI flicker by blocking buttons before they render
- installs an interceptor on `frm.add_custom_button`
- allows only the custom workflow buttons when procurement flow is active

#### procurement_custom_tabs.js
This is a large client-side orchestration script that appears to:
- add next-step buttons in the form header
- fetch next valid steps from backend
- filter actions by role
- remove ERPNext default actions that bypass interception
- enforce strict PO Create-menu options
- show linked docs / chain / counts / statuses
- cache workflow metadata client-side
- avoid duplicate handler registration in Frappe Desk SPA

### Why this matters

The project is deliberately replacing ERPNext's standard procurement UX with a controlled guided UX.

So the backend rules and frontend actions are tightly coupled.

---

## 10. Validation philosophy

The app clearly follows a **server-side validation first** philosophy.

Even though there are many client-side enhancements, the core business rules are enforced in Python hooks.

Examples I found:

- step order validation
- source document requirement
- quantity-limit enforcement
- item restriction enforcement
- supplier match enforcement
- cancellation blocking when child docs exist
- payment suspense validation

This is good architecture for ERPNext customizations because it protects data integrity even if UI behavior changes.

---

## 11. Cancellation and document-chain protection

The app maintains backward and forward links between procurement documents and uses them to:

- display chain information
- compute flow trees
- block cancellation when child docs exist
- require reverse-order unwinding of the process

That means the app treats procurement as a linked process, not as independent forms.

---

## 12. Parallel workflow support

One detail that stands out is support for `step_group`.

From the guide and backend logic, the project supports parallel branches such as:

- Material Request -> Purchase Requisition
- Material Request -> Stock Entry

at the same step level.

And the quantity engine aggregates consumption across those branches.

That is more advanced than a simple linear document flow.

---

## 13. Role-aware action visibility

From `Procurement Flow Steps.role` and the client script logic, the app allows create buttons to be shown only for users with specific roles.

So the workflow is not only sequence-aware, but also permission-aware at the business-process level.

---

## Important files I believe are central

### Core backend
- `next_custom_app/hooks.py`
- `next_custom_app/next_custom_app/utils/procurement_workflow.py`
- `next_custom_app/next_custom_app/custom_fields.py`
- `next_custom_app/next_custom_app/install.py`
- `next_custom_app/next_custom_app/utils/payment_request_utils.py`
- `next_custom_app/next_custom_app/utils/po_quantity_control.py`

### Key custom doctypes
- `next_custom_app/next_custom_app/doctype/procurement_flow/*`
- `next_custom_app/next_custom_app/doctype/procurement_flow_steps/*`
- `next_custom_app/next_custom_app/doctype/procurement_rule_set/*`
- `next_custom_app/next_custom_app/doctype/procurement_document_link/*`
- `next_custom_app/next_custom_app/doctype/purchase_requisition/*`
- `next_custom_app/next_custom_app/doctype/rfq_supplier_rule/*`
- `next_custom_app/next_custom_app/doctype/supplier_comparison/*`

### Key frontend
- `next_custom_app/public/js/procurement_button_override.js`
- `next_custom_app/public/js/procurement_custom_tabs.js`
- `next_custom_app/public/js/rfq_pivot_view.js`
- `next_custom_app/public/js/rfq_comparison.js`
- `next_custom_app/public/js/payment_request.js`
- `next_custom_app/public/js/payment_entry.js`
- `next_custom_app/public/js/purchase_order_po_control.js`

### Key documentation
- `README.md`
- `README_PROCUREMENT.md`
- `PROCUREMENT_WORKFLOW_GUIDE.md`

---

## My current mental model of the end-to-end flow

The intended happy path seems to be approximately:

1. User configures an active `Procurement Flow`
2. User creates and submits a root procurement document, usually `Material Request`
3. App shows only valid next-step actions
4. App creates next docs through `make_procurement_document()`
5. Source references + document links are stored automatically
6. Quantities are validated against source and parallel consumption
7. RFQ and SQ stages support supplier pricing and comparison workflows
8. Purchase Orders are controlled against RFQ totals
9. Downstream documents like Purchase Receipt / Purchase Invoice / Payment Request / Payment Entry continue the linked chain
10. Cancellation is protected when descendants exist

---

## What seems especially important for future development

If I continue working on this project, I should treat these areas as high-risk / high-impact:

### 1. `procurement_workflow.py`
This is the main engine. Changes here can affect all document creation, validation, linking, and chain visibility.

### 2. `hooks.py`
This defines when logic runs. Hook order matters a lot in Frappe.

### 3. Client-side button override behavior
Any regression here could re-enable standard ERPNext create flows and bypass the intended UX.

### 4. Quantity validation rules
Especially around:
- parallel steps
- RFQ -> SQ -> PO indirect chain
- draft vs submitted consumption

### 5. Payment suspense logic
This looks business-specific and accounting-sensitive.

### 6. Custom field setup on migrate
Because this app relies heavily on custom fields, schema drift between environments could break forms or hooks.

---

## Gaps / caveats in my understanding

I reviewed the key architecture and many important files, but I have not yet exhaustively traced every line of every file.

So this document is my **working understanding** of the project, based on the main code paths and docs I inspected.

Possible areas to inspect next for deeper understanding:

- exact linked-document rendering logic inside the rest of `procurement_custom_tabs.js`
- remaining portions of `procurement_workflow.py`, especially document-tree rendering and submission handlers
- deployment / patch scripts and one-off migration files
- any environment-specific SQL or restoration scripts
- whether `next_app/` is legacy/duplicate code or still part of the live app structure

---

## Final summary

My current understanding is:

`next_custom_app` is a **custom ERPNext procurement-control app** that replaces standard ERPNext document progression with a **configurable workflow engine**.

Its main strengths are:
- strict source/sequence enforcement
- cross-document quantity control
- full chain traceability
- advanced RFQ/SQ comparison flows
- tailored payment handling for purchaser suspense accounting
- custom UI that guides users through only the allowed next actions

So if I continue as the NYG Custom App developer, I should think of this codebase as:

> **a procurement orchestration layer on top of ERPNext, not just a collection of small custom scripts.**
