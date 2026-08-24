from unittest.mock import patch

import frappe
from frappe.utils import add_days, now_datetime

from frappe_lms_commerce.commerce.integrations.lms import (
	MAX_CONTEXT_VALUE_LENGTH,
	MAX_KEY_LENGTH,
	MAX_REQUESTS,
	MAX_RESOURCE_NAME_LENGTH,
	decide_many,
)
from frappe_lms_commerce.tests.test_helpers import CommerceIntegrationTestCase


class TestLMSProvider(CommerceIntegrationTestCase):
	def request(self, target, action="catalog", key=None, context=None):
		resource_type = "course" if target.doctype == "LMS Course" else "program"
		return {
			"key": key or f"{resource_type}:{target.name}:{action}",
			"resource_type": resource_type,
			"resource_name": target.name,
			"action": action,
			"context": context or {},
		}

	def grant(self, member, *, target=None, tier=None, starts_on=None, ends_on=None):
		doc = {
			"doctype": "Commerce Entitlement",
			"member": member.name,
			"scope": "Target" if target else "Tier",
			"target_doctype": target and target.doctype,
			"target_name": target and target.name,
			"tier": tier and tier.name,
			"source_type": "Manual",
			"status": "Active",
			"starts_on": starts_on,
			"ends_on": ends_on,
		}
		entitlement = frappe.get_doc(doc).insert(ignore_permissions=True)
		self.cleanup_items.append(("Commerce Entitlement", entitlement.name))
		return entitlement

	def test_single_settings_enabled_and_unmapped_fallback(self):
		course = self.create_course()
		user = self.create_user()
		frappe.db.set_single_value("Commerce Settings", "enabled", 1)
		key = "unmapped"
		self.assertEqual(
			decide_many(user=user.name, requests=[self.request(course, key=key)])[key],
			{"handled": False, "allowed": False},
		)

	def test_disabled_and_unmapped_resources_preserve_legacy(self):
		course = self.create_course()
		user = self.create_user()
		frappe.db.set_single_value("Commerce Settings", "enabled", 0)
		key = "disabled"
		self.assertEqual(
			decide_many(user=user.name, requests=[self.request(course, key=key)])[key],
			{"handled": False, "allowed": False},
		)

		frappe.db.set_single_value("Commerce Settings", "enabled", 1)
		key = "unmapped"
		self.assertEqual(
			decide_many(user=user.name, requests=[self.request(course, key=key)])[key],
			{"handled": False, "allowed": False},
		)

	def test_free_offering_requires_authenticated_user(self):
		course = self.create_course()
		self.create_offering(course, "Free")
		user = self.create_user()
		request = self.request(course)

		guest = decide_many(user="Guest", requests=[request])[request["key"]]
		self.assertTrue(guest["handled"])
		self.assertFalse(guest["allowed"])
		self.assertEqual(guest["reason"], "login_required")
		self.assertEqual(guest["offers"][0]["url"], "/login")

		member = decide_many(user=user.name, requests=[request])[request["key"]]
		self.assertTrue(member["allowed"])
		self.assertEqual(member["reason"], "entitled")

	def test_guest_tier_policy_returns_login_instead_of_provider_error(self):
		course = self.create_course()
		tier = self.create_tier()
		self.create_offering(course, "Tier", tier)
		request = self.request(course)
		decision = decide_many(user="Guest", requests=[request])[request["key"]]
		self.assertTrue(decision["handled"])
		self.assertFalse(decision["allowed"])
		self.assertEqual(decision["reason"], "login_required")
		self.assertEqual(decision["offers"][0]["kind"], "login")

	def test_higher_tier_entitlement_includes_lower_but_not_higher_tier(self):
		basic_course = self.create_course()
		max_course = self.create_course()
		basic = self.create_tier("Basic " + frappe.generate_hash(length=5), rank=10)
		maximum = self.create_tier("Max " + frappe.generate_hash(length=5), rank=20)
		self.create_offering(basic_course, "Tier", basic)
		self.create_offering(max_course, "Tier", maximum)
		user = self.create_user()
		self.grant(user, tier=maximum)

		basic_request = self.request(basic_course, "enroll")
		max_request = self.request(max_course, "consume")
		decisions = decide_many(user=user.name, requests=[basic_request, max_request])
		self.assertTrue(decisions[basic_request["key"]]["allowed"])
		self.assertTrue(decisions[max_request["key"]]["allowed"])

		other = self.create_user()
		self.grant(other, tier=basic)
		self.assertFalse(decide_many(user=other.name, requests=[max_request])[max_request["key"]]["allowed"])

	def test_entitlements_are_isolated_by_user_and_time_window(self):
		course = self.create_course()
		self.create_offering(course, "Purchase")
		granted = self.create_user()
		other = self.create_user()
		request = self.request(course, "consume")
		self.grant(granted, target=course, ends_on=add_days(now_datetime(), 1))
		self.assertTrue(decide_many(user=granted.name, requests=[request])[request["key"]]["allowed"])
		self.assertFalse(decide_many(user=other.name, requests=[request])[request["key"]]["allowed"])

		future_user = self.create_user()
		self.grant(future_user, target=course, starts_on=add_days(now_datetime(), 1))
		self.assertFalse(decide_many(user=future_user.name, requests=[request])[request["key"]]["allowed"])
		expired_user = self.create_user()
		self.grant(expired_user, target=course, ends_on=add_days(now_datetime(), -1))
		self.assertFalse(decide_many(user=expired_user.name, requests=[request])[request["key"]]["allowed"])

	def test_program_requests_and_all_actions_are_consistent(self):
		program = self.create_program()
		tier = self.create_tier()
		self.create_offering(program, "Tier", tier)
		user = self.create_user()
		self.grant(user, tier=tier)
		requests = [
			self.request(program, action, key=action)
			for action in (
				"catalog",
				"view",
				"enroll",
				"consume",
				"progress",
			)
		]
		decisions = decide_many(user=user.name, requests=requests)
		self.assertEqual(set(decisions), {item["key"] for item in requests})
		self.assertTrue(all(decision["allowed"] for decision in decisions.values()))

	def test_bulk_provider_has_constant_total_query_count(self):
		first = self.create_course()
		second = self.create_course()
		tier = self.create_tier()
		self.create_offering(first, "Tier", tier)
		self.create_offering(second, "Tier", tier)
		user = self.create_user()
		self.grant(user, tier=tier)
		requests = []
		for index in range(40):
			target = first if index % 2 else second
			requests.append(self.request(target, "catalog", f"request-{index}"))

		with (
			patch(
				"frappe_lms_commerce.commerce.integrations.lms.frappe.get_all",
				wraps=frappe.get_all,
			) as get_all,
			patch.object(frappe.db, "get_value", wraps=frappe.db.get_value) as get_value,
			patch.object(
				frappe.db,
				"get_single_value",
				wraps=frappe.db.get_single_value,
			) as get_single_value,
		):
			decisions = decide_many(user=user.name, requests=requests)
		self.assertEqual(len(decisions), len(requests))
		# One call each for settings enabled + portal path + user, and bounded
		# calls for offerings, entitlements, and tier ranks. The total is constant
		# regardless of request count.
		self.assertLessEqual(get_all.call_count + get_value.call_count + get_single_value.call_count, 6)

	def test_contract_exact_bounds_and_context(self):
		accepted = {
			"key": "k" * MAX_KEY_LENGTH,
			"resource_type": "course",
			"resource_name": "n" * MAX_RESOURCE_NAME_LENGTH,
			"action": "catalog",
			"context": {
				"lesson": "l" * MAX_CONTEXT_VALUE_LENGTH,
				"quiz": None,
				"is_preview": False,
			},
		}
		self.assertIn(accepted["key"], decide_many(user="Guest", requests=[accepted]))

		for field, value in (
			("key", "k" * (MAX_KEY_LENGTH + 1)),
			("resource_name", "n" * (MAX_RESOURCE_NAME_LENGTH + 1)),
		):
			invalid = {**accepted, field: value}
			with self.assertRaises(frappe.ValidationError):
				decide_many(user="Guest", requests=[invalid])
		invalid_context = {**accepted, "context": {"lesson": "x" * (MAX_CONTEXT_VALUE_LENGTH + 1)}}
		with self.assertRaises(frappe.ValidationError):
			decide_many(user="Guest", requests=[invalid_context])
		with self.assertRaises(frappe.ValidationError):
			decide_many(user="Guest", requests=[{**accepted, "context": {"unsafe": "x"}}])
		for falsey_non_object in (False, 0, "", []):
			with self.assertRaises(frappe.ValidationError):
				decide_many(
					user="Guest",
					requests=[{**accepted, "context": falsey_non_object}],
				)
		self.assertIn(
			accepted["key"],
			decide_many(user="Guest", requests=[{**accepted, "context": None}]),
		)
		without_context = dict(accepted)
		without_context.pop("context")
		self.assertIn(without_context["key"], decide_many(user="Guest", requests=[without_context]))
		with self.assertRaises(frappe.ValidationError):
			decide_many(
				user="Guest",
				requests=[{**accepted, "key": f"key-{index}"} for index in range(MAX_REQUESTS + 1)],
			)

	def test_contract_rejects_duplicate_keys_and_wrong_version(self):
		course = self.create_course()
		request = self.request(course, key="same")
		with self.assertRaises(frappe.ValidationError):
			decide_many(user="Guest", requests=[request, request])
		with self.assertRaises(frappe.ValidationError):
			decide_many(user="Guest", requests=[request], contract_version=2)
