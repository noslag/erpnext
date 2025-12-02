import frappe
from frappe.model.utils.rename_field import rename_field


def _rename_custom_field(field_docname: str, new_fieldname: str):
	"""Minimal replacement for the removed rename_fieldname helper."""
	data = frappe.db.get_value("Custom Field", field_docname, ["dt", "fieldname"], as_dict=True)
	if not data:
		return
	if data.fieldname == new_fieldname:
		return

	new_name = f"{data.dt}-{new_fieldname}"
	frappe.db.set_value("Custom Field", field_docname, "fieldname", new_fieldname)
	if field_docname != new_name:
		frappe.db.sql("update `tabCustom Field` set name=%s where name=%s", (new_name, field_docname))


def execute():
	doctypes = frappe.get_all("Service Level Agreement", pluck="document_type", distinct=True)
	for doctype in doctypes:
		if doctype == "Issue":
			continue

		if frappe.db.exists(
			"Custom Field", {"name": doctype + "-resolution_by", "fieldname": "resolution_by"}
		):
			_rename_custom_field(doctype + "-resolution_by", "sla_resolution_by")

		if frappe.db.exists(
			"Custom Field", {"name": doctype + "-resolution_date", "fieldname": "resolution_date"}
		):
			_rename_custom_field(doctype + "-resolution_date", "sla_resolution_date")

	rename_field("Issue", "resolution_by", "sla_resolution_by")
	rename_field("Issue", "resolution_date", "sla_resolution_date")
