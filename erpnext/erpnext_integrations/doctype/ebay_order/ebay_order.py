from __future__ import annotations

from datetime import datetime

import frappe
from frappe.model.document import Document


class eBayOrder(Document):
	def mark_sync_success(self, payload: dict, *, change_token: str | None = None):
		self.db_set("raw_payload", frappe.as_json(payload))
		self.db_set("last_error", None)
		self.db_set("last_synced_at", datetime.utcnow())
		if change_token:
			self.db_set("change_token", change_token)

	def mark_sync_failure(self, error: str):
		self.db_set("last_error", error)
