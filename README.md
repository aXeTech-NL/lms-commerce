# Frappe LMS Commerce

`frappe_lms_commerce` is a public, sidecar Frappe app for commercial access to Frappe LMS. It keeps commercial policy outside LMS while LMS remains responsible for its catalog, learner enrollment and progress.

This foundation release contains only the versioned entitlement-provider contract and the smallest Desk model needed to configure and test it. Checkout, personal subscriptions, business seats and Mollie are intentionally deferred until their contracts are proven independently.

## Architecture

```text
Frappe LMS                         frappe_lms_commerce
-----------                        -------------------
Published catalog       <--------  Commerce Offering
Learner enrollment      -------->  decide_many(action="enroll")
Lesson/progress access  -------->  decide_many(action="consume|progress")
Enrollment + progress              Tier + Entitlement policy
```

An entitlement means that a learner *may* enroll or consume managed content. It never creates an `LMS Enrollment`; enrollment remains the learner's explicit intent to start a Course.

The app exposes one LMS hook:

```python
lms_entitlement_provider = (
    "frappe_lms_commerce.commerce.integrations.lms.decide_many"
)
```

The provider implements LMS entitlement contract version 1 as one bounded bulk call. An unmapped Course or Program returns `handled=False`, preserving exact legacy LMS behavior. Managed resources return safe badges and offer URLs but no HTML or executable frontend components.

## Foundation model

- **Commerce Settings** — feature switch, future portal base path, default currency and provider diagnostics.
- **Commerce Tier** — hierarchical access rank. A higher active tier includes lower tiers.
- **Commerce Offering** — one enabled mapping per LMS Course or Program, with Free, Tier, Purchase or Tier-or-Purchase policy.
- **Commerce Entitlement** — audited, time-bounded manual Target or Tier grant for one registered User.

All DocTypes live in one Frappe module named **Commerce**. `Commerce Manager` manages records and manual grants; `Commerce Viewer` receives read/report access. Portal users have no generic DocType permissions.

## Compatibility

The initial package targets:

- Frappe `>=16,<17`
- Frappe LMS `>=2.61,<3`
- Frappe Payments `<1` (declared now; checkout is not part of this milestone)

The LMS site must include the generic external entitlement bridge that provides `lms_entitlement_provider`. Until that bridge is installed, this app is a safe Desk-only configuration app and does not change LMS access.

## Installation

From a Frappe v16 Bench:

```bash
bench get-app https://github.com/aXeTech-NL/frappe-lms-commerce.git
bench --site <site> install-app frappe_lms_commerce
bench --site <site> migrate
```

Install LMS and Payments on the site before Commerce.

## Configure the foundation

1. Open the **Commerce** Workspace.
2. Set a default Currency and enable **Commerce Settings**.
3. Create ascending **Commerce Tiers**.
4. Map an LMS Course or Program with **Commerce Offering**.
5. Use the manual grant service or Desk to create a **Commerce Entitlement**.

Manual service example:

```python
from frappe_lms_commerce.commerce.services.entitlements import (
    grant_manual_entitlement,
    revoke_manual_entitlement,
)

name = grant_manual_entitlement(
    "learner@example.com",
    "Tier",
    tier="Max",
    idempotency_key="support-case-123",
)
revoke_manual_entitlement(name)
```

These methods require `Commerce Manager` or `System Manager` and serialize changes on the User row.

## Contract behavior

For a managed Offering:

- **catalog/view** — published metadata remains visible; `allowed` says whether the current user is entitled and generic lock/offer data explains the next action.
- **enroll** — Commerce permits enrollment for Free, matching Tier or direct Target entitlement.
- **consume/progress** — Commerce returns the same commercial decision; LMS separately requires local enrollment and applies its lesson, quiz and progress rules.
- **provider absent, disabled or unmapped** — LMS keeps its legacy behavior.

Commercial offer URLs must be relative paths or HTTPS URLs. Purchase/upgrade routes currently point at the future `/commerce` portal and are presentation-only until checkout is implemented.

## Tests and development

Static checks:

```bash
ruff check .
python -m compileall -q frappe_lms_commerce
```

In Bench:

```bash
bench --site <site> run-tests --app frappe_lms_commerce
```

The integration tests cover model validation, safe URLs, time windows, manual grant/revoke authorization, idempotency, hierarchy, bulk query behavior and unmapped fallback.

## Roadmap

Milestones are deliberately serial:

1. **Foundation** — this release: Settings, Tiers, Offerings, manual Entitlements and LMS provider.
2. **Personal commerce** — Purchases, Subscriptions, verified payment events and Frappe UI customer portal.
3. **Business commerce** — Business Accounts, invitations and concurrency-safe seat assignment in the same Commerce module.
4. **Payments/Mollie** — generic recurring Payments contract, first-period checkout, mandates, normalized webhook events, cancellation and reconciliation.

No placeholder lifecycle DocTypes are shipped before their payment and policy contracts are approved.

## License

GNU Affero General Public License v3 or later. See [`license.txt`](license.txt).
