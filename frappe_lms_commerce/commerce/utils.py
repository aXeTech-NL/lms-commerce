from urllib.parse import urlsplit

import frappe
from frappe import _
from frappe.utils import get_datetime, now_datetime

ALLOWED_TARGET_DOCTYPES = ("LMS Course", "LMS Program")
COMMERCE_MANAGER_ROLES = {"Commerce Manager", "System Manager"}


def target_key(target_doctype: str, target_name: str) -> str:
	if target_doctype not in ALLOWED_TARGET_DOCTYPES or not target_name:
		frappe.throw(_("A supported Commerce target is required."))
	return f"{target_doctype}:{target_name}"


def validate_safe_url(url: str | None, *, required: bool = False) -> str | None:
	if not url:
		if required:
			frappe.throw(_("A portal URL is required."))
		return None

	url = url.strip()
	if (
		len(url) > 500
		or "\\" in url
		or any(ord(character) < 32 or ord(character) == 127 for character in url)
	):
		frappe.throw(_("The portal URL is invalid."))
	parsed = urlsplit(url)
	is_relative = url.startswith("/") and not url.startswith("//") and not parsed.netloc
	is_https = (
		parsed.scheme == "https" and bool(parsed.netloc) and not parsed.username and not parsed.password
	)
	if not (is_relative or is_https):
		frappe.throw(_("Portal URLs must be relative paths or HTTPS URLs."))
	return url


def is_active_window(starts_on=None, ends_on=None, *, at=None) -> bool:
	at = get_datetime(at or now_datetime())
	if starts_on and get_datetime(starts_on) > at:
		return False
	return not ends_on or get_datetime(ends_on) >= at


def require_commerce_manager():
	user = frappe.session.user
	if user == "Administrator" or COMMERCE_MANAGER_ROLES & set(frappe.get_roles(user)):
		return
	frappe.throw(_("Commerce Manager permission is required."), frappe.PermissionError)
