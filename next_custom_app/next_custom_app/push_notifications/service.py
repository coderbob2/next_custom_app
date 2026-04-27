import json
import time

import frappe


def _get_vapid_keys():
	conf = frappe.conf or {}
	public_key = conf.get("vapid_public_key")
	private_key = conf.get("vapid_private_key")
	return public_key, private_key


def _get_vapid_subject():
	conf = frappe.conf or {}
	return conf.get("vapid_subject") or conf.get("push_vapid_subject") or "mailto:info@nextcoretechnologies.com"


def _detect_browser(user_agent):
	ua = (user_agent or "").lower()
	if "edg" in ua:
		return "Edge"
	if "chrome" in ua and "edg" not in ua:
		return "Chrome"
	if "firefox" in ua:
		return "Firefox"
	if "safari" in ua and "chrome" not in ua:
		return "Safari"
	return "Unknown"


@frappe.whitelist()
def get_push_public_key():
	public_key, _ = _get_vapid_keys()
	return public_key


@frappe.whitelist()
def save_push_subscription(subscription, browser=None):
	if frappe.session.user == "Guest":
		frappe.throw("Login required")

	if isinstance(subscription, str):
		subscription = json.loads(subscription)

	endpoint = (subscription or {}).get("endpoint")
	keys = (subscription or {}).get("keys") or {}
	p256dh = keys.get("p256dh")
	auth = keys.get("auth")
	browser = _detect_browser(browser or frappe.form_dict.get("browser") or frappe.get_request_header("User-Agent"))

	if not endpoint or not p256dh or not auth:
		frappe.throw("Invalid push subscription payload")

	existing_name = frappe.db.get_value("Push Subscription", {"endpoint": endpoint}, "name")
	if existing_name:
		doc = frappe.get_doc("Push Subscription", existing_name)
		doc.user = frappe.session.user
		doc.p256dh = p256dh
		doc.auth = auth
		doc.browser = browser
		doc.enabled = 1
		doc.save(ignore_permissions=True)
	else:
		frappe.get_doc(
			{
				"doctype": "Push Subscription",
				"user": frappe.session.user,
				"endpoint": endpoint,
				"p256dh": p256dh,
				"auth": auth,
				"browser": browser,
				"enabled": 1,
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
			vapid_claims={"sub": _get_vapid_subject()},
		)
		return True
	except WebPushException as exc:
		status = getattr(getattr(exc, "response", None), "status_code", None)
		frappe.log_error(
			message=f"WebPushException status={status} endpoint={subscription_info.get('endpoint')} error={exc}",
			title="Workflow Web Push Error",
		)
		if status in (404, 410):
			endpoint = subscription_info.get("endpoint")
			if endpoint:
				name = frappe.db.get_value("Push Subscription", {"endpoint": endpoint}, "name")
				if name:
					frappe.delete_doc("Push Subscription", name, ignore_permissions=True, force=1)
		return False
	except Exception:
		frappe.log_error(frappe.get_traceback(), "Workflow Web Push Unexpected Error")
		return False


def send_push_to_user(user, payload):
	if not user or user in {"Guest", "Administrator"}:
		return False

	rows = frappe.get_all(
		"Push Subscription",
		filters={"user": user, "enabled": 1},
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


@frappe.whitelist()
def send_test_push_notification(delay_seconds=5, doctype=None, docname=None):
	"""Trigger delayed test push for current user to validate closed-tab background notifications."""
	if frappe.session.user == "Guest":
		frappe.throw("Login required")

	try:
		delay = max(0, int(delay_seconds or 0))
	except Exception:
		delay = 5

	frappe.enqueue(
		"next_custom_app.next_custom_app.push_notifications.service._send_test_push_notification_job",
		queue="short",
		user=frappe.session.user,
		delay_seconds=delay,
		doctype=doctype,
		docname=docname,
	)

	return {"queued": True, "delay_seconds": delay}


def _send_test_push_notification_job(user, delay_seconds=5, doctype=None, docname=None):
	if delay_seconds:
		time.sleep(int(delay_seconds))

	url = "/app"
	title = "ERPNext Test Push"
	body = f"Background test push for {user} delivered after {delay_seconds}s."
	if doctype and docname:
		url = f"/app/{frappe.scrub(doctype)}/{docname}"
		title = f"{doctype} {docname}"
		body = f"Test notification from {doctype} {docname}."

	send_push_to_user(
		user,
		{
			"title": title,
			"body": body,
			"url": url,
			"doctype": doctype,
			"docname": docname,
			"route": ["Form", doctype, docname] if doctype and docname else ["desk"],
			"tag": f"erpnext-test-push-{user}-{doctype or 'desk'}-{docname or 'home'}",
			"requireInteraction": True,
		},
	)
