from __future__ import annotations

import json
import logging
import shlex
import subprocess
from pathlib import Path
from typing import Iterable, Sequence

import frappe
from frappe.utils import now_datetime

logger = logging.getLogger(__name__)


DEFAULT_APPS: Sequence[str] = ("erpnext", "premium_theme")


def enqueue_provisioning(
	tenant_name: str,
	*,
	admin_password: str | None = None,
	mariadb_root_password: str | None = None,
	install_apps: Iterable[str] | None = None,
	fixtures: Iterable[str] | None = None,
	queue: str | None = None,
):
	"""Queue a background job that provisions a new site for the given tenant.

	The sensitive credentials (admin + MariaDB root passwords) are passed at call time
	and NEVER written to the database.
	"""

	admin_password = admin_password or _get_secret("noslag_admin_password")
	mariadb_root_password = mariadb_root_password or _get_secret("noslag_mariadb_root_password")

	apps = list(DEFAULT_APPS)
	if install_apps:
		for app in install_apps:
			if app not in apps:
				apps.append(app)

	job = frappe.enqueue(
		"erpnext.noslag_multi_tenancy.provisioning._provision_site",
		queue=queue or ("short" if frappe.conf.developer_mode else "long"),
		job_name=f"Provision tenant {tenant_name}",
		tenant_name=tenant_name,
		admin_password=admin_password,
		mariadb_root_password=mariadb_root_password,
		apps=apps,
		fixtures=list(fixtures or []),
	)
	logger.info("Queued provisioning job %s for tenant %s", job.id, tenant_name)
	return job.id


def build_new_site_command(
	site_name: str,
	*,
	admin_password: str,
	mariadb_root_password: str,
	apps: Sequence[str],
) -> list[str]:
	cmd: list[str] = [
		"bench",
		"new-site",
		site_name,
		"--admin-password",
		admin_password,
		"--mariadb-root-password",
		mariadb_root_password,
	]
	for app in apps:
		cmd.extend(["--install-app", app])
	cmd.append("--no-proxy")
	cmd.append("--no-mariadb-socket")
	return cmd


def _provision_site(
	tenant_name: str,
	*,
	admin_password: str,
	mariadb_root_password: str,
	apps: Sequence[str],
	fixtures: list[str],
):
	tenant = frappe.get_doc("NoSlag Tenant", tenant_name)
	tenant.db_set({"provisioning_state": "Provisioning"})
	tenant.append_provisioning_log("Provisioning job started")

	cmd = build_new_site_command(
		tenant.site_name,
		admin_password=admin_password,
		mariadb_root_password=mariadb_root_password,
		apps=apps,
	)

	try:
		_run_bench_command(cmd)
	except subprocess.CalledProcessError as exc:
		logger.exception("Provisioning failed for %s", tenant_name)
		tenant.db_set({"provisioning_state": "Failed"})
		tenant.append_provisioning_log(f"Provisioning failed: {exc}")
		raise

	tenant.reload()
	tenant.db_set(
		{
			"provisioning_state": "Ready",
			"status": "Active",
			"last_provisioned_at": now_datetime(),
		}
	)
	tenant.append_provisioning_log("Site created successfully via bench new-site.")

	if fixtures:
		_apply_fixtures(tenant.site_name, fixtures)
		tenant.append_provisioning_log(f"Applied fixtures: {', '.join(fixtures)}")


def _apply_fixtures(site_name: str, fixtures: list[str]):
	for fixture_path in fixtures:
		cmd = [
			"bench",
			"--site",
			site_name,
			"execute",
			"frappe.core.doctype.data_import.data_import.import_file",
			"--kwargs",
			json.dumps({"path": fixture_path, "overwrite": True}),
		]
		_run_bench_command(cmd)


def _run_bench_command(cmd: Sequence[str]):
	bench_dir = _get_bench_dir()
	logger.info("Running bench command: %s", " ".join(shlex.quote(part) for part in cmd))
	result = subprocess.run(cmd, cwd=str(bench_dir), check=True, capture_output=True, text=True)
	logger.debug("stdout: %s", result.stdout)
	if result.stderr:
		logger.debug("stderr: %s", result.stderr)


def _get_secret(key: str) -> str:
	value = frappe.conf.get(key)
	if value:
		return value
	raise frappe.ValidationError(
		f"Missing required provisioning secret '{key}'. Set it in site_config.json or pass it explicitly."
	)


def _get_bench_dir() -> Path:
	site_path = Path(frappe.get_site_path()).resolve()
	# .../frappe-bench/sites/<site_name>
	return site_path.parent.parent
