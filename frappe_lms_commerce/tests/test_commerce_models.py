import frappe
from frappe.utils import add_days, now_datetime

from frappe_lms_commerce.commerce.services.entitlements import revoke_manual_entitlement
from frappe_lms_commerce.commerce.utils import is_active_window
from frappe_lms_commerce.tests.test_helpers import CommerceIntegrationTestCase


class TestCommerceModels(CommerceIntegrationTestCase):
	def test_tier_rank_must_be_positive(self):
		with self.assertRaises(frappe.ValidationError):
			frappe.get_doc(
				{
					"doctype": "Commerce Tier",
					"tier_name": f"Invalid {frappe.generate_hash(length=6)}",
					"rank": 0,
				}
			).insert(ignore_permissions=True)

	def test_offering_policy_combinations_and_safe_urls(self):
		course = self.create_course()
		tier = self.create_tier(rank=1000 + int(frappe.generate_hash(length=3), 36))
		with self.assertRaises(frappe.ValidationError):
			self.create_offering(course, "Tier")
		with self.assertRaises(frappe.ValidationError):
			self.create_offering(course, "Purchase", amount=0)

		offering = self.create_offering(
			course,
			"Tier or Purchase",
			tier,
			purchase_url="/commerce/buy",
			upgrade_url="https://commerce.example.com/plans",
		)
		self.assertEqual(offering.required_tier, tier.name)
		self.assertEqual(offering.active_target_key, f"LMS Course:{course.name}")

	def test_urls_match_lms_contract_safety(self):
		unsafe = (
			"javascript:alert(1)",
			"//commerce.example.com/plans",
			"https://user:secret@commerce.example.com/plans",
			"https://commerce.example.com/plans\\evil",
			"https://commerce.example.com/plans\x7f",
		)
		for url in unsafe:
			course = self.create_course()
			with self.assertRaises(frappe.ValidationError, msg=url):
				self.create_offering(course, "Purchase", purchase_url=url)

	def test_only_one_enabled_offering_per_target(self):
		course = self.create_course()
		self.create_offering(course)
		with self.assertRaises(frappe.ValidationError):
			self.create_offering(course)

	def test_entitlement_period_terminal_state_and_audit_actor(self):
		user = self.create_user()
		course = self.create_course()
		frappe.set_user("Administrator")
		entitlement = frappe.get_doc(
			{
				"doctype": "Commerce Entitlement",
				"member": user.name,
				"scope": "Target",
				"target_doctype": "LMS Course",
				"target_name": course.name,
				"starts_on": add_days(now_datetime(), -1),
				"ends_on": add_days(now_datetime(), 1),
				"source_type": "Manual",
				"granted_by": user.name,
			}
		).insert(ignore_permissions=True)
		self.cleanup_items.append(("Commerce Entitlement", entitlement.name))
		self.assertTrue(entitlement.is_current())
		self.assertEqual(entitlement.granted_by, "Administrator")

		entitlement.granted_by = user.name
		with self.assertRaises(frappe.ValidationError):
			entitlement.save(ignore_permissions=True)
		entitlement.reload()

		entitlement.status = "Revoked"
		with self.assertRaises(frappe.ValidationError):
			entitlement.save(ignore_permissions=True)
		entitlement.reload()

		revoke_manual_entitlement(entitlement.name)
		entitlement.reload()
		self.assertEqual(entitlement.status, "Revoked")
		self.assertEqual(entitlement.revoked_by, "Administrator")
		self.assertTrue(entitlement.revoked_on)

		original_revoked_on = entitlement.revoked_on
		for field, value in (
			("status", "Expired"),
			("revoked_by", user.name),
			("revoked_on", add_days(original_revoked_on, 1)),
		):
			entitlement.reload()
			entitlement.set(field, value)
			with self.assertRaises(frappe.ValidationError):
				entitlement.save(ignore_permissions=True)

	def test_new_terminal_status_is_rejected(self):
		user = self.create_user()
		course = self.create_course()
		with self.assertRaises(frappe.ValidationError):
			frappe.get_doc(
				{
					"doctype": "Commerce Entitlement",
					"member": user.name,
					"scope": "Target",
					"target_doctype": "LMS Course",
					"target_name": course.name,
					"source_type": "Manual",
					"status": "Revoked",
				}
			).insert(ignore_permissions=True)

	def test_ended_active_entitlement_is_normalized_to_expired(self):
		user = self.create_user()
		course = self.create_course()
		entitlement = frappe.get_doc(
			{
				"doctype": "Commerce Entitlement",
				"member": user.name,
				"scope": "Target",
				"target_doctype": "LMS Course",
				"target_name": course.name,
				"starts_on": add_days(now_datetime(), -3),
				"ends_on": add_days(now_datetime(), -1),
				"source_type": "Manual",
				"status": "Active",
			}
		).insert(ignore_permissions=True)
		self.cleanup_items.append(("Commerce Entitlement", entitlement.name))
		self.assertEqual(entitlement.status, "Expired")
		self.assertFalse(entitlement.active_grant_key)

	def test_active_window_boundaries_are_inclusive(self):
		boundary = now_datetime()
		self.assertTrue(is_active_window(boundary, boundary, at=boundary))
		self.assertFalse(is_active_window(add_days(boundary, 1), None, at=boundary))
		self.assertFalse(is_active_window(None, add_days(boundary, -1), at=boundary))
