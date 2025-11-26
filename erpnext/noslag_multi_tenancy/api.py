from __future__ import annotations

import re
from typing import Iterable

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import validate_email_address


def _require_system_manager():
	if not frappe.has_permission(doctype="NoSlag Tenant", ptype="write"):
		raise frappe.PermissionError(_("System Manager permission is required for tenant provisioning."))


@frappe.whitelist()
def create_tenant_and_provision(
	tenant_name: str,
	site_name: str,
	*,
	plan: str = "Growth",
	primary_domain: str | None = None,
	billing_customer: str | None = None,
	admin_password: str | None = None,
	mariadb_root_password: str | None = None,
	install_apps: Iterable[str] | None = None,
	fixtures: Iterable[str] | None = None,
) -> dict:
	"""Create a NoSlag Tenant record and immediately enqueue provisioning.

	Returns a dict with the tenant name and enqueued job ID so callers can track status.
	"""

	_require_system_manager()

	doc = frappe.get_doc(
		{
			"doctype": "NoSlag Tenant",
			"tenant_name": tenant_name,
			"site_name": site_name,
			"primary_domain": primary_domain,
			"plan": plan,
			"billing_customer": billing_customer,
		}
	).insert(ignore_permissions=False)

	job_id = doc.enqueue_provisioning(
		admin_password=admin_password,
		mariadb_root_password=mariadb_root_password,
		install_apps=install_apps,
		fixtures=fixtures,
	)

	return {"tenant": doc.name, "job_id": job_id}


@frappe.whitelist()
def enqueue_existing_tenant(
	tenant: str,
	*,
	admin_password: str | None = None,
	mariadb_root_password: str | None = None,
	install_apps: Iterable[str] | None = None,
	fixtures: Iterable[str] | None = None,
) -> dict:
	"""Queue provisioning for an existing NoSlag Tenant doc without recreating it."""

	_require_system_manager()
	doc: Document = frappe.get_doc("NoSlag Tenant", tenant)
	job_id = doc.enqueue_provisioning(
		admin_password=admin_password,
		mariadb_root_password=mariadb_root_password,
		install_apps=install_apps,
		fixtures=fixtures,
	)
	return {"tenant": doc.name, "job_id": job_id}


@frappe.whitelist(allow_guest=True)
def public_signup(
	company_name: str,
	*,
	site_name: str | None = None,
	admin_email: str,
	plan: str = "Growth",
	contact_name: str | None = None,
	team_size: str | None = None,
	use_case: str | None = None,
	signup_token: str | None = None,
):
	"""Guest-accessible entry point for the landing-page signup form."""

	_validate_signup_token(signup_token)
	company = (company_name or "").strip()
	if not company:
		raise frappe.ValidationError(_("Company name is required."))
	email = (admin_email or "").strip()
	if not email or not validate_email_address(email):
		raise frappe.ValidationError(_("Enter a valid work email."))
	slug = _normalize_site_name(site_name, company)
	if frappe.db.exists("NoSlag Tenant", slug):
		raise frappe.ValidationError(_("This site name is already registered. Pick another."))

	doc = frappe.get_doc(
		{
			"doctype": "NoSlag Tenant",
			"tenant_name": company,
			"site_name": slug,
			"primary_domain": slug,
			"plan": plan or "Growth",
			"billing_email": email,
			"notes": _build_signup_notes(contact_name, team_size, use_case),
		}
	).insert(ignore_permissions=True)
	doc.append_provisioning_log("Signup submitted via public landing page.")
	job_id = doc.enqueue_provisioning(install_apps=None, fixtures=None)
	return {"tenant": doc.name, "site_name": doc.site_name, "job_id": job_id}


def _build_signup_notes(contact_name: str | None, team_size: str | None, use_case: str | None) -> str | None:
	parts: list[str] = []
	if contact_name:
		parts.append(f"Contact: {contact_name.strip()}")
	if team_size:
		parts.append(f"Team size: {team_size.strip()}")
	if use_case:
		parts.append(f"Use case: {use_case.strip()}")
	return " | ".join(parts) if parts else None


def _validate_signup_token(token: str | None):
	expected = frappe.conf.get("noslag_public_signup_token")
	if expected and token != expected:
		raise frappe.PermissionError(_("Invalid signup token."))


def _normalize_site_name(raw_site: str | None, fallback: str) -> str:
	source = (raw_site or fallback).lower().strip()
	if not source:
		raise frappe.ValidationError(_("Site name is required."))
	slug = re.sub(r"[^a-z0-9.-]", "-", source)
	slug = re.sub(r"-+", "-", slug).strip("-.")
	if not slug:
		raise frappe.ValidationError(_("Site name is required."))
	if "." not in slug:
		suffix = frappe.conf.get("noslag_signup_domain")
		if suffix:
			slug = f"{slug}.{suffix}"
	return slug
