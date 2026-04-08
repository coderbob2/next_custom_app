# Payment Voucher Print Format – Setup Guide

Custom Jinja print format for **Payment Entry** showing Purchase Order / Payment Request
references, paid amount with currency, account details, and signature blocks.

---

## Step 1 – Open Print Format builder

1. Log in as **Administrator**.
2. Go to: `/app/print-format/new?doc_type=Payment+Entry`

## Step 2 – Fill header fields

| Field                | Value              |
|----------------------|--------------------|
| Name                 | Payment Voucher    |
| DocType              | Payment Entry      |
| Module               | Next Custom App    |
| Print Format Type    | Jinja              |
| Custom Format        | ✅ checked         |

## Step 3 – Paste the HTML below into the **HTML** field

```html
<style>
.pv { font-family: Arial, Helvetica, sans-serif; font-size: 11px; color: #222; line-height: 1.5; }
.pv-title-row { display: table; width: 100%; margin-bottom: 8px; }
.pv-title-left { display: table-cell; width: 60%; vertical-align: bottom; }
.pv-title-right { display: table-cell; width: 40%; text-align: right; vertical-align: bottom; }
.pv-title-left h2 { font-size: 15px; font-weight: 700; margin: 0; text-transform: uppercase; letter-spacing: 1px; }
.pv-title-left .vno { font-size: 11px; color: #444; }
.pv-title-right .vdate { font-size: 12px; color: #333; }
.pv-hr { border: none; border-top: 1px solid #aaa; margin: 4px 0 8px 0; }
.pv-dl { display: table; width: 100%; margin-bottom: 2px; }
.pv-dl .l { display: table-cell; width: 110px; font-size: 11px; font-weight: 600; color: #555; padding: 2px 6px 2px 0; vertical-align: top; }
.pv-dl .v { display: table-cell; font-size: 12px; font-weight: 700; color: #111; padding: 2px 0; vertical-align: top; }
.pv-amt { border: 2px solid #222; text-align: center; padding: 6px 10px; margin: 10px 0; }
.pv-amt .al { font-size: 9px; text-transform: uppercase; letter-spacing: 1px; color: #666; }
.pv-amt .av { font-size: 18px; font-weight: 700; }
.pv-st { font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; color: #555; border-bottom: 1px solid #bbb; padding-bottom: 2px; margin: 10px 0 5px 0; }
.pv-alloc { width: 100%; border-collapse: collapse; margin-bottom: 6px; font-size: 10px; }
.pv-alloc th { background: #eee; border: 1px solid #ccc; padding: 3px 6px; text-align: left; font-size: 9px; text-transform: uppercase; font-weight: 700; }
.pv-alloc td { border: 1px solid #ccc; padding: 3px 6px; }
.pv-alloc .r { text-align: right; }
.pv-rem { border: 1px solid #ccc; padding: 4px 8px; font-size: 10px; margin-bottom: 6px; background: #fafafa; }
.pv-sig { margin-top: 25px; page-break-inside: avoid; }
.pv-sig-row { display: table; width: 100%; margin-top: 8px; }
.pv-sig-cell { display: table-cell; width: 33.33%; text-align: center; padding: 0 8px; vertical-align: bottom; }
.pv-sig-line { border-bottom: 1px solid #222; height: 35px; }
.pv-sig-title { font-size: 9px; font-weight: 700; text-transform: uppercase; color: #444; margin-top: 3px; }
.pv-sig-fields { margin-top: 6px; }
.pv-sig-fields .sf { display: table; width: 100%; margin-bottom: 3px; }
.pv-sig-fields .sf .sl { display: table-cell; width: 40px; font-size: 8px; color: #888; text-align: left; vertical-align: bottom; }
.pv-sig-fields .sf .sv { display: table-cell; border-bottom: 1px dotted #aaa; font-size: 8px; vertical-align: bottom; height: 14px; }
.pv-ref-row { display: table; width: 100%; margin-bottom: 2px; }
.pv-ref-row .rl { display: table-cell; width: 140px; font-size: 10px; font-weight: 600; color: #555; padding: 1px 6px 1px 0; vertical-align: top; }
.pv-ref-row .rv { display: table-cell; font-size: 11px; font-weight: 600; color: #222; padding: 1px 0; vertical-align: top; }
</style>
<div class="pv">

<!-- Title: name left, date right -->
<div class="pv-title-row">
<div class="pv-title-left">
<h2>Payment Voucher</h2>
<span class="vno">{{ doc.name }}</span>
</div>
<div class="pv-title-right">
<span class="vdate">Date: <strong>{{ frappe.format_date(doc.posting_date) }}</strong></span>
</div>
</div>
<hr class="pv-hr">

<!-- Payment details -->
<div class="pv-dl"><span class="l">Type:</span><span class="v">{{ doc.payment_type or '' }}</span></div>
<div class="pv-dl"><span class="l">Mode:</span><span class="v">{{ doc.mode_of_payment or '—' }}</span></div>
<div class="pv-dl"><span class="l">Party:</span><span class="v">{{ doc.party_name or doc.party or '—' }}{% if doc.party_type %} ({{ doc.party_type }}){% endif %}</span></div>
<div class="pv-dl"><span class="l">Paid From:</span><span class="v">{{ doc.paid_from or '' }} ({{ doc.paid_from_account_currency or '' }})</span></div>
<div class="pv-dl"><span class="l">Paid To:</span><span class="v">{{ doc.paid_to or '' }} ({{ doc.paid_to_account_currency or '' }})</span></div>

<!-- Amount -->
<div class="pv-amt">
<div class="al">Paid Amount</div>
<div class="av">{{ doc.paid_from_account_currency or '' }} {{ frappe.utils.fmt_money(doc.paid_amount, currency=doc.paid_from_account_currency) }}</div>
{% if doc.paid_from_account_currency != doc.paid_to_account_currency %}
<div style="font-size:10px;color:#666;margin-top:2px;">Received: {{ doc.paid_to_account_currency }} {{ frappe.utils.fmt_money(doc.received_amount, currency=doc.paid_to_account_currency) }}</div>
{% endif %}
</div>

<!-- Allocated references -->
{% if doc.references and doc.references | length > 0 %}
<div class="pv-st">Allocated Against</div>
<table class="pv-alloc">
<thead><tr><th>Type</th><th>Name</th><th class="r">Total</th><th class="r">Outstanding</th><th class="r">Allocated</th></tr></thead>
<tbody>
{% for ref in doc.references %}
<tr><td>{{ ref.reference_doctype }}</td><td>{{ ref.reference_name }}</td><td class="r">{{ frappe.utils.fmt_money(ref.total_amount or 0, currency=doc.paid_from_account_currency) }}</td><td class="r">{{ frappe.utils.fmt_money(ref.outstanding_amount or 0, currency=doc.paid_from_account_currency) }}</td><td class="r">{{ frappe.utils.fmt_money(ref.allocated_amount or 0, currency=doc.paid_from_account_currency) }}</td></tr>
{% endfor %}
</tbody>
</table>
{% endif %}

<!-- Remarks -->
{% if doc.remarks %}
<div class="pv-st">Remarks</div>
<div class="pv-rem">{{ doc.remarks }}</div>
{% endif %}

<!-- Authorizations -->
<div class="pv-sig">
<div class="pv-st">Authorizations</div>
<div class="pv-sig-row">
<div class="pv-sig-cell">
<div class="pv-sig-line"></div>
<div class="pv-sig-title">Prepared By</div>
<div class="pv-sig-fields">
<div class="sf"><span class="sl">Name:</span><span class="sv"></span></div>
<div class="sf"><span class="sl">Date:</span><span class="sv"></span></div>
</div>
</div>
<div class="pv-sig-cell">
<div class="pv-sig-line"></div>
<div class="pv-sig-title">Checked By</div>
<div class="pv-sig-fields">
<div class="sf"><span class="sl">Name:</span><span class="sv"></span></div>
<div class="sf"><span class="sl">Date:</span><span class="sv"></span></div>
</div>
</div>
<div class="pv-sig-cell">
<div class="pv-sig-line"></div>
<div class="pv-sig-title">Received By</div>
<div class="pv-sig-fields">
<div class="sf"><span class="sl">Name:</span><span class="sv"></span></div>
<div class="sf"><span class="sl">Date:</span><span class="sv"></span></div>
</div>
</div>
</div>
</div>

<!-- Procurement references at the very bottom -->
{% set ns = namespace(po='', pr='') %}
{% if doc.procurement_source_doctype == 'Payment Request' and doc.procurement_source_name %}
{% set ns.pr = doc.procurement_source_name %}
{% endif %}
{% if not ns.pr and doc.reference_no and frappe.db.exists('Payment Request', doc.reference_no) %}
{% set ns.pr = doc.reference_no %}
{% endif %}
{% if ns.pr %}
{% set _pr_data = frappe.db.get_value('Payment Request', ns.pr, ['reference_doctype','reference_name'], as_dict=1) %}
{% if _pr_data and _pr_data.reference_doctype == 'Purchase Order' %}{% set ns.po = _pr_data.reference_name %}{% endif %}
{% endif %}
{% if not ns.po %}{% for ref in doc.references or [] %}{% if ref.reference_doctype == 'Purchase Order' %}{% set ns.po = ref.reference_name %}{% endif %}{% endfor %}{% endif %}
<div class="pv-st" style="margin-top: 15px;">Procurement References</div>
<div class="pv-ref-row"><span class="rl">Purchase Order:</span><span class="rv">{{ ns.po or '—' }}</span></div>
<div class="pv-ref-row"><span class="rl">Payment Request:</span><span class="rv">{{ ns.pr or '—' }}</span></div>

</div>
```

## Step 4 – Save

Click **Save**. The print format is ready.

## Step 5 – Test

1. Open any Payment Entry → click the **printer icon** → select **Payment Voucher**.
2. Select a **Letter Head** if desired — the template does not override it.
3. Everything should fit on one page with compact layout.

---

## Alternative: Create via bench console

```bash
bench --site <site> console
```

```python
import frappe

html = """<paste the HTML from Step 3 above>"""

if frappe.db.exists("Print Format", "Payment Voucher"):
    pf = frappe.get_doc("Print Format", "Payment Voucher")
    pf.html = html
    pf.save(ignore_permissions=True)
else:
    frappe.get_doc({
        "doctype": "Print Format",
        "name": "Payment Voucher",
        "doc_type": "Payment Entry",
        "module": "Next Custom App",
        "print_format_type": "Jinja",
        "standard": "No",
        "custom_format": 1,
        "html": html,
    }).insert(ignore_permissions=True)

frappe.db.commit()
```

## Set as default (optional)

Go to **Customize Form → Payment Entry** and set **Default Print Format** = `Payment Voucher`.

---

## Layout Summary

| Section                | Position     | Content                                                |
|------------------------|--------------|--------------------------------------------------------|
| **Title**              | Top          | "PAYMENT VOUCHER" left, Date right                     |
| **Payment Details**    | Upper        | Type, Mode, Party, Paid From, Paid To (bold values)    |
| **Paid Amount**        | Center       | Prominent bordered box with currency + amount          |
| **Allocated Against**  | Middle       | Table of referenced documents with amounts             |
| **Remarks**            | Middle       | Remarks text box                                       |
| **Authorizations**     | Lower        | 3 signature blocks: Prepared By, Checked By, Received By (with Name/Date fields) |
| **Procurement Refs**   | Bottom       | Purchase Order, Payment Request                        |
