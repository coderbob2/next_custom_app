import frappe
from frappe.utils import now_datetime

from next_custom_app.next_custom_app.push_notifications.service import send_push_to_user


FINAL_STATE_FALLBACKS = {"Approved", "Completed", "Final Approved", "Finance Approved"}


def get_active_workflow(doctype):
	"""Return active Workflow doc (dict) for a doctype, if any."""
	workflow = frappe.get_all(
		"Workflow",
		filters={"document_type": doctype, "is_active": 1},
		fields=["name", "workflow_state_field"],
		limit=1,
	)
	return workflow[0] if workflow else None


def _get_source_state(transition_row):
	return (
		getattr(transition_row, "source_state", None)
		or getattr(transition_row, "state", None)
		or getattr(transition_row, "from_state", None)
	)


def _get_next_state(transition_row):
	return getattr(transition_row, "next_state", None) or getattr(transition_row, "state", None)


def get_next_workflow_state(doc, workflow):
	"""Return one possible next workflow state from the current state."""
	workflow_doc = frappe.get_doc("Workflow", workflow["name"])
	workflow_state_field = workflow.get("workflow_state_field") or "workflow_state"
	current_state = doc.get(workflow_state_field)

	if not current_state:
		return None

	for row in workflow_doc.transitions:
		if _get_source_state(row) == current_state:
			next_state = _get_next_state(row)
			if next_state and next_state != current_state:
				return next_state

	return None


def get_roles_for_workflow_state(workflow, state):
	"""Resolve roles allowed for a target workflow state from workflow states + transitions."""
	if not workflow or not state:
		return []

	workflow_doc = frappe.get_doc("Workflow", workflow["name"])
	roles = set()

	for row in workflow_doc.states:
		if row.state == state and getattr(row, "allow_edit", None):
			roles.add(row.allow_edit)

	for row in workflow_doc.transitions:
		next_state = _get_next_state(row)
		if next_state == state and getattr(row, "allowed", None):
			roles.add(row.allowed)

	return list(roles)


def get_users_with_roles(roles):
	"""Return enabled users for any role in roles (excluding Guest/Administrator)."""
	if not roles:
		return []

	users = frappe.db.sql(
		"""
		SELECT DISTINCT u.name
		FROM `tabUser` u
		INNER JOIN `tabHas Role` hr ON hr.parent = u.name
		WHERE hr.role IN %(roles)s
		  AND u.enabled = 1
		  AND u.name NOT IN ('Guest', 'Administrator')
		""",
		{"roles": tuple(roles)},
		as_dict=True,
	)

	return [u.name for u in users]


def _notification_exists(user, subject, document_type, document_name):
	"""Avoid duplicate alerts for same subject/document/user in recent time window."""
	return bool(
		frappe.db.exists(
			"Notification Log",
			{
				"for_user": user,
				"subject": subject,
				"document_type": document_type,
				"document_name": document_name,
				"creation": [">", frappe.utils.add_to_date(now_datetime(), minutes=-5)],
			},
		)
	)


def create_notification_log(user, subject, message, document_type, document_name):
	if _notification_exists(user, subject, document_type, document_name):
		return False

	frappe.get_doc(
		{
			"doctype": "Notification Log",
			"subject": subject,
			"email_content": message,
			"for_user": user,
			"type": "Alert",
			"document_type": document_type,
			"document_name": document_name,
			"from_user": frappe.session.user,
		}
	).insert(ignore_permissions=True)
	return True


def _publish_desktop_notification(user, subject, message, doctype, docname, state):
	frappe.publish_realtime(
		event="custom_workflow_desktop_notification",
		message={
			"title": subject,
			"body": message,
			"doctype": doctype,
			"docname": docname,
			"workflow_state": state,
			"route": ["Form", doctype, docname],
			"timestamp": str(now_datetime()),
		},
		user=user,
	)

	send_push_to_user(
		user,
		{
			"title": subject,
			"body": message,
			"url": f"/app/{frappe.scrub(doctype)}/{docname}",
			"tag": f"{doctype}-{docname}-{state}",
			"doctype": doctype,
			"docname": docname,
			"workflow_state": state,
		},
	)


def _is_final_state(workflow, state):
	if not workflow or not state:
		return False

	workflow_doc = frappe.get_doc("Workflow", workflow["name"])
	for row in workflow_doc.states:
		if row.state == state and int(getattr(row, "doc_status", 0) or 0) == 1:
			return True

	return state in FINAL_STATE_FALLBACKS


def send_desktop_workflow_notification(doc, next_state=None, final=False):
	"""Main dispatcher for workflow realtime + Notification Log fallback/in-app alerts."""
	workflow = get_active_workflow(doc.doctype)
	if not workflow:
		return

	workflow_state_field = workflow.get("workflow_state_field") or "workflow_state"
	current_state = doc.get(workflow_state_field)

	if final or _is_final_state(workflow, current_state):
		target_users = [doc.owner] if doc.owner else []
		subject = f"{doc.doctype} {doc.name} Approved"
		message = f"Your document {doc.doctype} {doc.name} has been approved."
		state_for_message = current_state
	else:
		target_state = next_state or get_next_workflow_state(doc, workflow)
		if not target_state:
			return

		roles = get_roles_for_workflow_state(workflow, target_state)
		target_users = get_users_with_roles(roles)
		subject = f"{doc.doctype} {doc.name} requires {target_state}"
		message = f"{doc.doctype} {doc.name} is now waiting for {target_state}."
		state_for_message = target_state

	for user in set(target_users):
		if user in {"Guest", "Administrator"}:
			continue
		created = create_notification_log(user, subject, message, doc.doctype, doc.name)
		if created:
			_publish_desktop_notification(user, subject, message, doc.doctype, doc.name, state_for_message)


def handle_workflow_notification(doc, method=None):
	"""Doc event handler: only notify when active workflow state changes on update."""
	if getattr(doc.flags, "in_insert", False):
		return

	workflow = get_active_workflow(doc.doctype)
	if not workflow:
		return

	workflow_state_field = workflow.get("workflow_state_field") or "workflow_state"
	if not hasattr(doc, "has_value_changed"):
		return

	if not doc.has_value_changed(workflow_state_field):
		return

	current_state = doc.get(workflow_state_field)
	if not current_state:
		return

	if _is_final_state(workflow, current_state):
		send_desktop_workflow_notification(doc, final=True)
		return

	# When workflow_state changes, the document is already in the newly assigned state.
	# Notify users responsible for this new state.
	send_desktop_workflow_notification(doc, next_state=current_state)
