import frappe
from frappe.tests import IntegrationTestCase


class TestUTMCampaign(IntegrationTestCase):
	def tearDown(self):
		frappe.delete_doc("UTM Campaign", "_Test UTM Campaign", ignore_missing=True)

	def test_can_create_and_read_campaign(self):
		if frappe.db.exists("UTM Campaign", "_Test UTM Campaign"):
			frappe.delete_doc("UTM Campaign", "_Test UTM Campaign", ignore_missing=True)

		doc = frappe.get_doc(
			{
				"doctype": "UTM Campaign",
				"name": "_Test UTM Campaign",
				"campaign_description": "Automated test campaign",
			}
		).insert(ignore_permissions=True)

		self.assertEqual(doc.campaign_description, "Automated test campaign")
		self.assertTrue(frappe.db.exists("UTM Campaign", "_Test UTM Campaign"))
