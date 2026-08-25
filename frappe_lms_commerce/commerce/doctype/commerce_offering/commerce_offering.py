import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt

from frappe_lms_commerce.commerce.utils import target_key, validate_safe_url

TIER_POLICIES = {"Tier", "Tier or Purchase"}
PURCHASE_POLICIES = {"Purchase", "Tier or Purchase"}
ACCESS_POLICIES = {"Free", *TIER_POLICIES, "Purchase"}


class CommerceOffering(Document):
	def before_validate(self):
		if self.access_policy in PURCHASE_POLICIES and not self.currency:
			self.currency = frappe.db.get_single_value("Commerce Settings", "default_currency")

	def validate(self):
		self.validate_target()
		self.validate_policy()
		self.purchase_url = validate_safe_url(self.purchase_url)
		self.upgrade_url = validate_safe_url(self.upgrade_url)

	def validate_target(self):
		key = target_key(self.target_doctype, self.target_name)
		if not frappe.db.exists(self.target_doctype, self.target_name):
			frappe.throw(_("The selected LMS target does not exist."))

		self.active_target_key = key if self.enabled else None
		if not self.title:
			self.title = (
				frappe.db.get_value(self.target_doctype, self.target_name, "title") or self.target_name
			)

		if not self.enabled:
			return
		existing = frappe.db.exists(
			"Commerce Offering",
			{"active_target_key": key, "name": ["!=", self.name]},
		)
		if existing:
			frappe.throw(_("Only one enabled Commerce Offering is allowed per LMS target."))

	def validate_policy(self):
		if self.access_policy not in ACCESS_POLICIES:
			frappe.throw(_("Select a supported access policy."))

		has_tier = self.access_policy in TIER_POLICIES
		has_purchase = self.access_policy in PURCHASE_POLICIES
		if has_tier:
			if not self.required_tier or not frappe.db.get_value(
				"Commerce Tier", self.required_tier, "enabled"
			):
				frappe.throw(_("An enabled Commerce Tier is required for this policy."))
		else:
			self.required_tier = None
			self.upgrade_url = None

		if has_purchase:
			if flt(self.amount) <= 0 or not self.currency:
				frappe.throw(_("A positive amount and currency are required for purchase policies."))
		else:
			self.amount = 0
			self.currency = None
			self.purchase_url = None
