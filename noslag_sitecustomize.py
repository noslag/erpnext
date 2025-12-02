"""Compatibility shims for running modern ERPNext against older Frappe builds.

This module is intended to be copied into the Python environment as ``sitecustomize``
so it executes automatically on interpreter startup, before any Frappe imports.
"""
from __future__ import annotations

try:  # pragma: no cover - optional shim
	import frappe  # type: ignore
except Exception:  # pragma: no cover - frappe not yet importable
	frappe = None  # type: ignore


if frappe:
	if not hasattr(frappe, "get_single_value"):

		def _get_single_value(doctype: str, fieldname: str, cache: bool = True):
			return frappe.db.get_single_value(doctype, fieldname, cache=cache)

		frappe.get_single_value = _get_single_value  # type: ignore[attr-defined]

	if not hasattr(frappe, "in_test"):
		frappe.in_test = False  # type: ignore[attr-defined]
