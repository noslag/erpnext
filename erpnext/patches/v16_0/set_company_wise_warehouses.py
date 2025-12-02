import frappe


def execute():
	fields = [
		"default_wip_warehouse",
		"default_fg_warehouse",
		"default_scrap_warehouse",
	]

	settings = frappe.get_single("Manufacturing Settings")
	warehouses = {field: settings.get(field) for field in fields}

	for name, warehouse in warehouses.items():
		if warehouse:
			company = frappe.get_value("Warehouse", warehouse, "company")
			frappe.db.set_value("Company", company, name, warehouse)
