from __future__ import annotations

from datetime import datetime

import frappe
from frappe.model.document import Document


class EbaySyncLog(Document):
	def on_update(self):
		if self.started_at and self.completed_at and not self.duration_ms:
			self.db_set(
				"duration_ms",
				int((self.completed_at - self.started_at).total_seconds() * 1000),
			)

	def mark_running(self):
		self.db_set("status", "Running")
		self.db_set("started_at", datetime.utcnow())

	def mark_finished(self, status: str, payload: dict | None = None):
		self.db_set("status", status)
		self.db_set("completed_at", datetime.utcnow())
		if payload is not None:
			self.db_set("response_payload", frappe.as_json(payload))

	def mark_error(self, message: str, payload: dict | None = None):
		self.db_set("status", "Failed")
		self.db_set("completed_at", datetime.utcnow())
		self.db_set("error_message", message)
		if payload is not None:
			self.db_set("response_payload", frappe.as_json(payload))
