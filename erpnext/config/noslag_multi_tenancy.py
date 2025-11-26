import frappe


def get_data():
	return [
		{
			"module_name": "NoSlag Multi Tenancy",
			"category": "Modules",
			"label": "NoSlag Multi Tenancy",
			"color": "#0a4fd3",
			"icon": "octicon octicon-organization",
			"type": "module",
			"description": "Tenant registry, provisioning, and lifecycle tools for the NoSlag SaaS offering.",
			"onboard": 1,
			"hidden": 0,
			"links": [
				{
					"label": "Tenants",
					"type": "doctype",
					"name": "NoSlag Tenant"
				}
			],
		}
	]
