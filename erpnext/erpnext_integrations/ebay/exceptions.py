from __future__ import annotations

import json
from typing import Any

import frappe


class EbayConfigurationError(frappe.ValidationError):
	"""Raised when required configuration is missing."""


class EbayAPIError(Exception):
	"""Raised when the eBay API returns an error payload."""

	def __init__(self, message: str, *, status: int | None = None, payload: Any | None = None):
		super().__init__(message)
		self.status = status
		self.payload = payload

	def as_dict(self) -> dict[str, Any]:
		return {
			"message": str(self),
			"status": self.status,
			"payload": self.payload if isinstance(self.payload, dict) else self._safe_payload(),
		}

	def _safe_payload(self) -> Any:
		if self.payload is None:
			return None
		try:
			return json.loads(self.payload)
		except Exception:  # pragma: no cover - diagnostic fallback
			return self.payload
