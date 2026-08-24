import frappe

COMMERCE_ROLES = {
	"Commerce Manager": {"desk_access": 1},
	"Commerce Viewer": {"desk_access": 1},
}


def after_install():
	create_roles()


def after_sync():
	create_roles()


def create_roles():
	for role_name, values in COMMERCE_ROLES.items():
		if frappe.db.exists("Role", role_name):
			frappe.db.set_value("Role", role_name, values, update_modified=False)
			continue

		role = frappe.new_doc("Role")
		role.role_name = role_name
		role.update(values)
		role.insert(ignore_permissions=True)
