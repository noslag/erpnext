from __future__ import annotations

from http import HTTPStatus
from typing import Any

import frappe
from frappe import _
from frappe.utils import escape_html


def _get_settings():
	settings = frappe.get_single("eBay Settings")
	if not settings.enabled:
		frappe.throw(_("Enable eBay Settings before starting OAuth."))
	return settings


@frappe.whitelist()
def start_authorization_flow() -> dict[str, Any]:
	"""Return an authorization URL that the Desk can open in a new window."""
	settings = _get_settings()
	url = settings.generate_authorization_url()
	return {"authorization_url": url, "state": settings.state_token}


@frappe.whitelist(allow_guest=True)
def complete_oauth_flow() -> None:
	"""Handle the redirect from eBay and persist refreshed tokens."""
	form = frappe.form_dict
	code = form.get("code")
	state = form.get("state")
	error = form.get("error")

	if error:
		return _respond_with_message(_("Unable to connect to eBay: {0}").format(error), success=False)
	if not code or not state:
		return _respond_with_message(_("Missing OAuth parameters from eBay."), success=False)

	settings = _get_settings()
	if not settings.state_token or settings.state_token != state:
		return _respond_with_message(_("State token mismatch. Please restart the connection process."), success=False)

	try:
		service = settings.build_oauth_service()
		response = service.exchange_authorization_code(code, scopes=settings.get_scopes())
		token = response.to_token()
		settings._persist_token(token)
		settings.db_set("state_token", None)
		success = True
		message = _("eBay store connected successfully. You can close this tab and return to ERPNext.")
	except Exception as exc:  # noqa: BLE001
		frappe.log_error(message="Failed to complete eBay OAuth", reference=str(exc))
		success = False
		message = _("Failed to complete eBay connection. Please retry from eBay Settings.")

	return _respond_with_message(message, success=success)


def _respond_with_message(message: str, *, success: bool) -> None:
	status = HTTPStatus.OK if success else HTTPStatus.BAD_REQUEST
	frappe.respond_as_web_page(
		title=_("eBay Connection"),
		html=f"<p>{escape_html(message)}</p>",
		status_code=status,
	)