from . import __version__

app_name = "frappe_lms_commerce"
app_title = "LMS Commerce"
app_publisher = "aXeTech"
app_description = "External commerce and entitlement management for Frappe LMS"
app_email = "info@axetech.nl"
app_license = "AGPL-3.0-or-later"
app_version = __version__

required_apps = ["frappe/lms", "frappe/payments"]

after_install = "frappe_lms_commerce.install.after_install"
after_sync = "frappe_lms_commerce.install.after_sync"

# Frappe LMS v1 external entitlement contract. The provider owns commercial
# policy; LMS retains publication, staff, enrollment and progress semantics.
lms_entitlement_provider = "frappe_lms_commerce.commerce.integrations.lms.decide_many"

# v16 rejects untyped whitelisted methods when this is enabled. Keeping it on
# makes the portal/service boundary explicit from the first release.
require_type_annotated_api_methods = True
