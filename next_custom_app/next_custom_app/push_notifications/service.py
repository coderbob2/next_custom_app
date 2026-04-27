import json

import frappe


def _get_vapid_keys():
	conf = frappe.conf or {}
	public_key = conf.get("vapid_public_key")
	private_key = conf.get("vapid_private_key")
	return public_key, private_key


@frappe.whitelist()
def get_push_public_key():
	public_key, _ = _get_vapid_keys()
	return public_key


@frappe.whitelist()
def save_push_subscription(subscription):
	if frappe.session.user == "Guest":
		frappe.throw("Login required")

	if isinstance(subscription, str):
		subscription = json.loads(subscription)

	endpoint = (subscription or {}).get("endpoint")
	keys = (subscription or {}).get("keys") or {}
	p256dh = keys.get("p256dh")
	auth = keys.get("auth")

	if not endpoint or not p256dh or not auth:
		frappe.throw("Invalid push subscription payload")

	existing_name = frappe.db.get_value("Push Subscription", {"endpoint": endpoint}, "name")
	if existing_name:
		doc = frappe.get_doc("Push Subscription", existing_name)
		doc.user = frappe.session.user
		doc.p256dh = p256dh
		doc.auth = auth
		doc.save(ignore_permissions=True)
	else:
		frappe.get_doc(
			{
				"doctype": "Push Subscription",
				"user": frappe.session.user,
				"endpoint": endpoint,
				"p256dh": p256dh,
				"auth": auth,
			}
		).insert(ignore_permissions=True)

	return {"ok": True}


def _send_webpush(subscription_info, payload):
	public_key, private_key = _get_vapid_keys()
	if not public_key or not private_key:
		return False

	try:
		from pywebpush import WebPushException, webpush
	except Exception:
		return False

	try:
		webpush(
			subscription_info=subscription_info,
			data=json.dumps(payload),
			vapid_private_key=private_key,
			vapid_claims={"sub": "mailto:admin@example.com"},
		)
		return True
	except WebPushException as exc:
		status = getattr(getattr(exc, "response", None), "status_code", None)
		if status in (404, 410):
			endpoint = subscription_info.get("endpoint")
			if endpoint:
				name = frappe.db.get_value("Push Subscription", {"endpoint": endpoint}, "name")
				if name:
					frappe.delete_doc("Push Subscription", name, ignore_permissions=True, force=1)
		return False
	except Exception:
		return False


def send_push_to_user(user, payload):
	if not user or user in {"Guest", "Administrator"}:
		return False

	rows = frappe.get_all(
		"Push Subscription",
		filters={"user": user},
		fields=["name", "endpoint", "p256dh", "auth"],
	)

	ok = False
	for row in rows:
		subscription_info = {
			"endpoint": row.endpoint,
			"keys": {"p256dh": row.p256dh, "auth": row.auth},
		}
		ok = _send_webpush(subscription_info, payload) or ok

	return ok


def notify_sales_invoice_submit(doc, method=None):
	"""Placeholder to keep existing Sales Invoice hook import valid."""
	return

