import frappe
from frappe.utils import add_days, now_datetime

from frappe_lms_commerce.commerce.services.entitlements import (
	grant_manual_entitlement,
	revoke_manual_entitlement,
)
from frappe_lms_commerce.tests.test_helpers import CommerceIntegrationTestCase


class TestEntitlementService(CommerceIntegrationTestCase):
	def create_manager(self):
		return self.create_user(
			"commerce-manager",
			roles=["Commerce Manager"],
			user_type="System User",
		)

	def test_manager_can_grant_exact_replay_and_revoke_idempotently(self):
		manager = self.create_manager()
		member = self.create_user()
		course = self.create_course()
		frappe.set_user(manager.name)
		key = f"manual-{frappe.generate_hash(length=10)}"
		starts_on = add_days(now_datetime(), -1)
		ends_on = add_days(now_datetime(), 5)
		name = grant_manual_entitlement(
			member.name,
			"Target",
			target_doctype="LMS Course",
			target_name=course.name,
			starts_on=starts_on,
			ends_on=ends_on,
			idempotency_key=key,
		)
		self.cleanup_items.append(("Commerce Entitlement", name))
		replay = grant_manual_entitlement(
			member.name,
			"Target",
			target_doctype="LMS Course",
			target_name=course.name,
			starts_on=starts_on,
			ends_on=ends_on,
			idempotency_key=key,
		)
		self.assertEqual(replay, name)

		self.assertEqual(revoke_manual_entitlement(name), name)
		self.assertEqual(revoke_manual_entitlement(name), name)
		row = frappe.db.get_value(
			"Commerce Entitlement",
			name,
			["status", "granted_by", "revoked_by", "revoked_on"],
			as_dict=True,
		)
		self.assertEqual(row.status, "Revoked")
		self.assertEqual(row.granted_by, manager.name)
		self.assertEqual(row.revoked_by, manager.name)
		self.assertTrue(row.revoked_on)

	def test_idempotency_key_cannot_cross_identity_or_window(self):
		manager = self.create_manager()
		member = self.create_user()
		first_course = self.create_course()
		second_course = self.create_course()
		frappe.set_user(manager.name)
		key = f"manual-{frappe.generate_hash(length=10)}"
		name = grant_manual_entitlement(
			member.name,
			"Target",
			target_doctype="LMS Course",
			target_name=first_course.name,
			ends_on=add_days(now_datetime(), 5),
			idempotency_key=key,
		)
		self.cleanup_items.append(("Commerce Entitlement", name))
		with self.assertRaises(frappe.ValidationError):
			grant_manual_entitlement(
				member.name,
				"Target",
				target_doctype="LMS Course",
				target_name=second_course.name,
				ends_on=add_days(now_datetime(), 5),
				idempotency_key=key,
			)
		with self.assertRaises(frappe.ValidationError):
			grant_manual_entitlement(
				member.name,
				"Target",
				target_doctype="LMS Course",
				target_name=first_course.name,
				ends_on=add_days(now_datetime(), 6),
				idempotency_key=key,
			)

	def test_different_active_or_future_window_conflicts(self):
		manager = self.create_manager()
		member = self.create_user()
		tier = self.create_tier()
		frappe.set_user(manager.name)
		starts_on = add_days(now_datetime(), 2)
		ends_on = add_days(now_datetime(), 10)
		name = grant_manual_entitlement(
			member.name,
			"Tier",
			tier=tier.name,
			starts_on=starts_on,
			ends_on=ends_on,
		)
		self.cleanup_items.append(("Commerce Entitlement", name))
		self.assertEqual(
			grant_manual_entitlement(
				member.name,
				"Tier",
				tier=tier.name,
				starts_on=starts_on,
				ends_on=ends_on,
			),
			name,
		)
		with self.assertRaises(frappe.ValidationError):
			grant_manual_entitlement(
				member.name,
				"Tier",
				tier=tier.name,
				starts_on=add_days(now_datetime(), 3),
				ends_on=add_days(now_datetime(), 10),
			)

	def test_mixed_scope_arguments_are_rejected(self):
		manager = self.create_manager()
		member = self.create_user()
		course = self.create_course()
		tier = self.create_tier()
		frappe.set_user(manager.name)
		with self.assertRaises(frappe.ValidationError):
			grant_manual_entitlement(
				member.name,
				"Target",
				target_doctype="LMS Course",
				target_name=course.name,
				tier=tier.name,
			)
		with self.assertRaises(frappe.ValidationError):
			grant_manual_entitlement(
				member.name,
				"Tier",
				target_doctype="LMS Course",
				target_name=course.name,
				tier=tier.name,
			)

	def test_portal_user_cannot_grant_or_revoke(self):
		manager = self.create_manager()
		member = self.create_user()
		course = self.create_course()
		frappe.set_user(manager.name)
		name = grant_manual_entitlement(
			member.name,
			"Target",
			target_doctype="LMS Course",
			target_name=course.name,
		)
		self.cleanup_items.append(("Commerce Entitlement", name))

		frappe.set_user(member.name)
		with self.assertRaises(frappe.PermissionError):
			grant_manual_entitlement(
				member.name,
				"Target",
				target_doctype="LMS Course",
				target_name=course.name,
			)
		with self.assertRaises(frappe.PermissionError):
			revoke_manual_entitlement(name)
