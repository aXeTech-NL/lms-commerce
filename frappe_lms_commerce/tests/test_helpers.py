import frappe
from frappe.tests import IntegrationTestCase

from frappe_lms_commerce.install import create_roles


class CommerceIntegrationTestCase(IntegrationTestCase):
	def setUp(self):
		super().setUp()
		frappe.set_user("Administrator")
		create_roles()
		self.cleanup_items = []
		self.original_settings = (
			frappe.db.get_value(
				"Commerce Settings",
				None,
				["enabled", "portal_path", "default_currency"],
				as_dict=True,
			)
			or frappe._dict()
		)
		settings = frappe.get_single("Commerce Settings")
		settings.enabled = 1
		settings.portal_path = "/commerce"
		settings.contract_version = 1
		settings.save(ignore_permissions=True)

	def tearDown(self):
		frappe.set_user("Administrator")
		for doctype, name in reversed(self.cleanup_items):
			if frappe.db.exists(doctype, name):
				frappe.delete_doc(doctype, name, force=True, ignore_permissions=True)
		settings = frappe.get_single("Commerce Settings")
		settings.enabled = self.original_settings.get("enabled") or 0
		settings.portal_path = self.original_settings.get("portal_path") or "/commerce"
		settings.default_currency = self.original_settings.get("default_currency")
		settings.save(ignore_permissions=True)
		super().tearDown()

	def create_user(self, prefix="commerce-user", roles=None, user_type="Website User"):
		email = f"{prefix}-{frappe.generate_hash(length=8)}@example.com"
		user = frappe.get_doc(
			{
				"doctype": "User",
				"email": email,
				"first_name": "Commerce",
				"last_name": "User",
				"send_welcome_email": 0,
				"user_type": user_type,
			}
		)
		for role in roles or ["LMS Student"]:
			user.append("roles", {"role": role})
		user.insert(ignore_permissions=True)
		self.cleanup_items.append(("User", user.name))
		return user

	def create_course(self, title=None):
		title = title or f"Commerce Course {frappe.generate_hash(length=8)}"
		course = frappe.get_doc(
			{
				"doctype": "LMS Course",
				"title": title,
				"short_introduction": "Commerce integration test course",
				"description": "Commerce integration test course description",
				"published": 1,
				"instructors": [{"instructor": "Administrator"}],
			}
		).insert(ignore_permissions=True)
		self.cleanup_items.append(("LMS Course", course.name))
		return course

	def create_program(self, title=None):
		title = title or f"Commerce Program {frappe.generate_hash(length=8)}"
		program = frappe.get_doc(
			{
				"doctype": "LMS Program",
				"title": title,
				"published": 1,
			}
		).insert(ignore_permissions=True)
		self.cleanup_items.append(("LMS Program", program.name))
		return program

	def create_tier(self, name=None, rank=10):
		name = name or f"Tier {frappe.generate_hash(length=8)}"
		tier = frappe.get_doc(
			{
				"doctype": "Commerce Tier",
				"tier_name": name,
				"rank": rank,
				"enabled": 1,
			}
		).insert(ignore_permissions=True)
		self.cleanup_items.append(("Commerce Tier", tier.name))
		return tier

	def create_offering(self, target, policy="Free", tier=None, **values):
		doc = {
			"doctype": "Commerce Offering",
			"title": target.title,
			"target_doctype": target.doctype,
			"target_name": target.name,
			"access_policy": policy,
			"required_tier": tier and tier.name,
			"enabled": 1,
		}
		if policy in ("Purchase", "Tier or Purchase"):
			doc.update({"amount": 25, "currency": "USD"})
		doc.update(values)
		offering = frappe.get_doc(doc).insert(ignore_permissions=True)
		self.cleanup_items.append(("Commerce Offering", offering.name))
		return offering
