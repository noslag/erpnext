from __future__ import annotations

from datetime import datetime

import frappe
from frappe.model.document import Document


class EbayListing(Document):
	@frappe.whitelist()
	def sync_from_ebay(self):
		if not self.sku:
			frappe.throw("SKU is required to sync from eBay")

		settings = frappe.get_single("eBay Settings")
		client = settings.build_client()

		try:
			item = client.get_inventory_item(self.sku)
			self.update_from_item(item)
			self.mark_sync_success(item)
			self.save()
			frappe.msgprint("Synced successfully")
		except Exception as e:
			self.mark_sync_failure(str(e))
			frappe.msgprint(f"Sync failed: {str(e)}")

	@frappe.whitelist()
	def push_to_ebay(self):
		if not self.sku:
			frappe.throw("SKU is required to push to eBay")

		settings = frappe.get_single("eBay Settings")
		client = settings.build_client()

		item_details = self.build_item_details()

		try:
			client.create_or_replace_inventory_item(self.sku, item_details)
			self.mark_sync_success(item_details)
			self.save()
			frappe.msgprint("Pushed successfully")
		except Exception as e:
			self.mark_sync_failure(str(e))
			frappe.msgprint(f"Push failed: {str(e)}")

	def update_from_item(self, item: dict):
		product = item.get("product", {})
		self.title = product.get("title")
		self.description = product.get("description")
		
		image_urls = product.get("imageUrls", [])
		if image_urls:
			self.image_url = image_urls[0]
			self.image_html = f'<img src="{self.image_url}" style="max-height: 100px; max-width: 100px; object-fit: contain;" />'
		else:
			self.image_url = None
			self.image_html = None
		
		availability = item.get("availability", {})
		pickup_at_location_availability = availability.get("pickupAtLocationAvailability", [])
		ship_to_location_availability = availability.get("shipToLocationAvailability", {})
		
		self.quantity = ship_to_location_availability.get("quantity", 0)
		
		# Note: Price is usually in Offer, not Inventory Item directly unless it's a fixed price item?
		# Inventory Item has 'condition', 'product', 'availability'.
		# Offers link Inventory Item to Price and Marketplace.
		
	def build_item_details(self) -> dict:
		# Minimal payload for createOrReplaceInventoryItem
		# https://developer.ebay.com/api-docs/sell/inventory/resources/inventory_item/methods/createOrReplaceInventoryItem
		product = {
			"title": self.title,
			"description": self.description or self.title,
		}
		
		if self.image_url:
			product["imageUrls"] = [self.image_url]

		return {
			"product": product,
			"condition": "NEW", # Default to NEW for now. TODO: Add condition field.
			"availability": {
				"shipToLocationAvailability": {
					"quantity": self.quantity or 0
				}
			}
		}

	def mark_sync_success(self, payload: dict):
		self.db_set("raw_payload", frappe.as_json(payload))
		self.db_set("notes", None)
		self.db_set("last_synced_at", datetime.utcnow())

	def mark_sync_failure(self, error: str):
		self.db_set("notes", error)
