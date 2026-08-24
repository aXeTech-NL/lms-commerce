import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import get_datetime, now_datetime

from frappe_lms_commerce.commerce.utils import is_active_window, target_key


class CommerceEntitlement(Document):
	def before_validate(self):
		if self.is_new():
			self.flags.requested_status = self.status or "Active"
			self.granted_by = frappe.session.user
		self.source_type = self.source_type or "Manual"

	def validate(self):
		self.validate_member()
		self.validate_scope()
		self.validate_period()
		self.validate_source()
		self.protect_identity()
		self.protect_terminal_state()
		self.set_active_grant_key()

	def validate_member(self):
		if not self.member or self.member == "Guest" or not frappe.db.exists("User", self.member):
			frappe.throw(_("A registered user is required for an entitlement."))

	def validate_scope(self):
		if self.scope == "Target":
			if self.tier:
				frappe.throw(_("Target entitlements cannot also grant a Tier."))
			self.target_key = target_key(self.target_doctype, self.target_name)
			if not frappe.db.exists(self.target_doctype, self.target_name):
				frappe.throw(_("The selected LMS target does not exist."))
			self.tier = None
		elif self.scope == "Tier":
			if self.target_doctype or self.target_name:
				frappe.throw(_("Tier entitlements cannot also grant a Target."))
			if not self.tier or not frappe.db.get_value("Commerce Tier", self.tier, "enabled"):
				frappe.throw(_("An enabled Commerce Tier is required."))
			self.target_doctype = None
			self.target_name = None
			self.target_key = None
		else:
			frappe.throw(_("Entitlement scope must be Target or Tier."))

	def validate_period(self):
		if self.starts_on and self.ends_on and get_datetime(self.ends_on) < get_datetime(self.starts_on):
			frappe.throw(_("Entitlement end cannot be before its start."))
		if self.status == "Active" and self.ends_on and get_datetime(self.ends_on) < now_datetime():
			self.status = "Expired"

	def validate_source(self):
		if self.source_type != "Manual":
			frappe.throw(_("Only Manual entitlement sources are supported in this milestone."))
		if bool(self.source_doctype) != bool(self.source_name):
			frappe.throw(_("Source Type and Source Document must be provided together."))
		if self.source_doctype and not frappe.db.exists(self.source_doctype, self.source_name):
			frappe.throw(_("The source document does not exist."))

	def protect_identity(self):
		if self.is_new():
			return
		previous = self.get_doc_before_save()
		for field in (
			"member",
			"scope",
			"target_doctype",
			"target_name",
			"tier",
			"source_type",
			"source_doctype",
			"source_name",
			"idempotency_key",
			"granted_by",
		):
			if previous and previous.get(field) != self.get(field):
				frappe.throw(_("Entitlement identity, source, and grant actor are immutable."))

	def protect_terminal_state(self):
		if self.is_new():
			if self.flags.requested_status != "Active":
				frappe.throw(_("New entitlements must start in Active status."))
			if self.revoked_by or self.revoked_on:
				frappe.throw(_("A new entitlement cannot contain revocation audit data."))
			return

		previous = self.get_doc_before_save()
		if not previous:
			return

		if previous.status in ("Revoked", "Expired"):
			for field in ("status", "revoked_by", "revoked_on"):
				if previous.get(field) != self.get(field):
					frappe.throw(_("Terminal entitlement status and audit fields are immutable."))
			return

		if self.revoked_by != previous.revoked_by or self.revoked_on != previous.revoked_on:
			frappe.throw(_("Revocation audit fields are controlled by the entitlement service."))

		if self.status == previous.status:
			return

		# Expiry is derived from a period that has actually elapsed. Explicit
		# revocation goes through revoke_manual_entitlement(), which stamps actor
		# and time with a locked raw update.
		naturally_expired = (
			self.status == "Expired" and self.ends_on and get_datetime(self.ends_on) < now_datetime()
		)
		if not naturally_expired:
			frappe.throw(_("Entitlement status is controlled by the entitlement service."))

	def set_active_grant_key(self):
		if self.status != "Active":
			self.active_grant_key = None
			return
		identity = self.target_key if self.scope == "Target" else f"Commerce Tier:{self.tier}"
		self.active_grant_key = f"{self.member}:{self.scope}:{identity}"

	def is_current(self, at=None) -> bool:
		return self.status == "Active" and is_active_window(self.starts_on, self.ends_on, at=at)
