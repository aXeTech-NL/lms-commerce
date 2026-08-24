import frappe
from frappe import _
from frappe.utils import get_datetime, now_datetime

from frappe_lms_commerce.commerce.utils import require_commerce_manager, target_key


def _normalize_grant(
	scope: str,
	*,
	target_doctype: str | None,
	target_name: str | None,
	tier: str | None,
) -> frappe._dict:
	if scope == "Target":
		if not target_doctype or not target_name or tier:
			frappe.throw(_("Target grants require only a target type and target name."))
		return frappe._dict(
			scope="Target",
			target_doctype=target_doctype,
			target_name=target_name,
			tier=None,
			identity=target_key(target_doctype, target_name),
		)
	if scope == "Tier":
		if not tier or target_doctype or target_name:
			frappe.throw(_("Tier grants require only a Commerce Tier."))
		return frappe._dict(
			scope="Tier",
			target_doctype=None,
			target_name=None,
			tier=tier,
			identity=f"Commerce Tier:{tier}",
		)
	frappe.throw(_("A valid Target or Tier scope is required."))


def _normalize_datetime(value):
	return get_datetime(value) if value else None


def _same_window(row, starts_on, ends_on) -> bool:
	return _normalize_datetime(row.starts_on) == starts_on and _normalize_datetime(row.ends_on) == ends_on


def _grant_identity(member: str, grant: frappe._dict) -> str:
	return f"{member}:{grant.scope}:{grant.identity}"


@frappe.whitelist()
def grant_manual_entitlement(
	member: str,
	scope: str,
	target_doctype: str | None = None,
	target_name: str | None = None,
	tier: str | None = None,
	starts_on: str | None = None,
	ends_on: str | None = None,
	idempotency_key: str | None = None,
	notes: str | None = None,
) -> str:
	"""Create one idempotent manual grant while serializing on its member.

	An exact replay returns the original row. A second active or scheduled grant
	for the same member/scope with a different validity window is rejected rather
	than silently changing which period the caller receives.
	"""
	require_commerce_manager()
	if not frappe.db.exists("User", member):
		frappe.throw(_("The selected user does not exist."))
	grant = _normalize_grant(
		scope,
		target_doctype=target_doctype,
		target_name=target_name,
		tier=tier,
	)
	starts_on = _normalize_datetime(starts_on)
	ends_on = _normalize_datetime(ends_on)
	if starts_on and ends_on and ends_on < starts_on:
		frappe.throw(_("Entitlement end cannot be before its start."))

	frappe.db.get_value("User", member, "name", for_update=True)

	if idempotency_key:
		existing = frappe.db.get_value(
			"Commerce Entitlement",
			{"idempotency_key": idempotency_key},
			[
				"name",
				"member",
				"scope",
				"target_doctype",
				"target_name",
				"tier",
				"starts_on",
				"ends_on",
			],
			as_dict=True,
		)
		if existing:
			expected = (
				member,
				grant.scope,
				grant.target_doctype,
				grant.target_name,
				grant.tier,
			)
			actual = (
				existing.member,
				existing.scope,
				existing.target_doctype,
				existing.target_name,
				existing.tier,
			)
			if actual != expected or not _same_window(existing, starts_on, ends_on):
				frappe.throw(_("The idempotency key is already used for another entitlement."))
			return existing.name

	active_key = _grant_identity(member, grant)
	existing = frappe.db.get_value(
		"Commerce Entitlement",
		{"active_grant_key": active_key},
		["name", "starts_on", "ends_on"],
		as_dict=True,
		for_update=True,
	)
	if existing:
		if existing.ends_on and _normalize_datetime(existing.ends_on) < now_datetime():
			frappe.db.set_value(
				"Commerce Entitlement",
				existing.name,
				{"status": "Expired", "active_grant_key": None},
				update_modified=False,
			)
		elif _same_window(existing, starts_on, ends_on):
			return existing.name
		else:
			frappe.throw(
				_("An active or scheduled entitlement already exists with a different validity window.")
			)

	entitlement = frappe.get_doc(
		{
			"doctype": "Commerce Entitlement",
			"member": member,
			"scope": grant.scope,
			"target_doctype": grant.target_doctype,
			"target_name": grant.target_name,
			"tier": grant.tier,
			"starts_on": starts_on,
			"ends_on": ends_on,
			"source_type": "Manual",
			"status": "Active",
			"idempotency_key": idempotency_key,
			"notes": notes,
		}
	)
	entitlement.insert()
	return entitlement.name


@frappe.whitelist()
def revoke_manual_entitlement(entitlement: str) -> str:
	"""Revoke a manual grant exactly once without deleting its audit row."""
	require_commerce_manager()
	member = frappe.db.get_value("Commerce Entitlement", entitlement, "member")
	if not member:
		frappe.throw(_("The entitlement does not exist."))
	frappe.db.get_value("User", member, "name", for_update=True)
	row = frappe.db.get_value(
		"Commerce Entitlement",
		entitlement,
		["name", "source_type", "status"],
		as_dict=True,
		for_update=True,
	)
	if row.source_type != "Manual":
		frappe.throw(_("Only manual entitlements can be revoked with this action."))
	if row.status in ("Revoked", "Expired"):
		return row.name

	frappe.db.set_value(
		"Commerce Entitlement",
		row.name,
		{
			"status": "Revoked",
			"active_grant_key": None,
			"revoked_by": frappe.session.user,
			"revoked_on": now_datetime(),
		},
		update_modified=False,
	)
	return row.name
