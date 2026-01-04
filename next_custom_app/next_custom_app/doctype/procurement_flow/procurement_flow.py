# Copyright (c) 2025, Nextcore Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class ProcurementFlow(Document):
	def validate(self):
		"""Validate the procurement flow configuration"""
		self.validate_step_numbers()
		self.validate_only_one_active_flow()
		self.validate_step_sequence()
	
	def validate_step_numbers(self):
		"""Ensure step numbers are unique and sequential"""
		step_numbers = [step.step_no for step in self.flow_steps]
		if len(step_numbers) != len(set(step_numbers)):
			frappe.throw("Step numbers must be unique")
		
		# Check for sequential ordering
		sorted_steps = sorted(step_numbers)
		if sorted_steps != list(range(1, len(sorted_steps) + 1)):
			frappe.throw("Step numbers must be sequential starting from 1")
	
	def validate_only_one_active_flow(self):
		"""Ensure only one flow is active at a time"""
		if self.is_active:
			existing_active = frappe.db.exists(
				"Procurement Flow",
				{
					"is_active": 1,
					"name": ["!=", self.name]
				}
			)
			if existing_active:
				frappe.throw(
					f"Another active flow exists: {existing_active}. "
					"Please deactivate it before activating this flow."
				)
	
	def validate_step_sequence(self):
		"""Validate that required source steps exist in proper sequence"""
		for i, step in enumerate(self.flow_steps):
			if step.requires_source and i == 0:
				frappe.throw(
					f"Step {step.step_no} ({step.doctype_name}) cannot require a source "
					"as it is the first step in the workflow"
				)


@frappe.whitelist()
def get_active_flow():
	"""Get the currently active procurement flow"""
	active_flow = frappe.db.get_value(
		"Procurement Flow",
		{"is_active": 1},
		["name", "flow_name"],
		as_dict=True
	)
	return active_flow


@frappe.whitelist()
def get_flow_steps(flow_name):
	"""Get all steps for a specific procurement flow"""
	flow = frappe.get_doc("Procurement Flow", flow_name)
	return [
		{
			"step_no": step.step_no,
			"doctype_name": step.doctype_name,
			"allowed_actions": step.allowed_actions,
			"requires_source": step.requires_source
		}
		for step in flow.flow_steps
	]


@frappe.whitelist()
def get_previous_step(current_doctype):
	"""Get the previous step in the workflow for a given doctype"""
	active_flow = get_active_flow()
	if not active_flow:
		return None
	
	steps = get_flow_steps(active_flow.name)
	for i, step in enumerate(steps):
		if step["doctype_name"] == current_doctype and i > 0:
			return steps[i - 1]
	
	return None


@frappe.whitelist()
def get_next_step(current_doctype):
	"""Get the next step in the workflow for a given doctype"""
	active_flow = get_active_flow()
	if not active_flow:
		return None
	
	steps = get_flow_steps(active_flow.name)
	for i, step in enumerate(steps):
		if step["doctype_name"] == current_doctype and i < len(steps) - 1:
			return steps[i + 1]
	
	return None