import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint


class CommerceTier(Document):
	def validate(self):
		if cint(self.rank) <= 0:
			frappe.throw(_("Tier rank must be greater than zero."))
		if self.enabled:
			return

		tier = self.name if not self.is_new() else self.tier_name
		if tier and frappe.db.exists("Commerce Offering", {"enabled": 1, "required_tier": tier}):
			frappe.throw(_("Disable offerings that require this tier before disabling the tier."))
