# LMS entitlement provider contract v1

Commerce registers one provider in Frappe hooks:

```python
lms_entitlement_provider = "frappe_lms_commerce.commerce.integrations.lms.decide_many"
```

The provider is called as a trusted Python function, not as a public HTTP endpoint:

```python
decide_many(user=user, requests=requests, contract_version=1)
```

A call contains at most 120 request objects. Each request has a unique key of at most 300 characters, `resource_type` (`course` or `program`), a resource name of at most 180 characters, `action` (`catalog`, `view`, `enroll`, `consume`, or `progress`) and an optional context containing only `lesson`, `quiz`, and `is_preview`. Lesson/quiz values are null or strings of at most 180 characters; `is_preview` is boolean.

Example response:

```json
{
  "course:introduction:catalog": {
    "handled": true,
    "allowed": false,
    "reason": "tier_required",
    "badge": {
      "label": "Max",
      "theme": "gray",
      "icon": "lock"
    },
    "offers": [
      {
        "kind": "upgrade",
        "label": "Upgrade to Max",
        "url": "/commerce/plans?offering=COF-00001",
        "variant": "outline",
        "icon": "layers"
      }
    ]
  }
}
```

## Semantics

- `handled=false` means Commerce has no enabled Offering for the target. LMS must run its unmodified legacy access policy.
- `handled=true` means Commerce owns the commercial decision for this target/action.
- `allowed` on `catalog` or `view` means the user is currently entitled; it does **not** hide published metadata.
- `allowed` on `enroll` lets LMS create a normal learner-selected Enrollment after LMS publication, duplicate and self-learning checks.
- `allowed` on `consume` or `progress` is only the commercial half of access. LMS must also require its local Enrollment and native lesson/quiz/progress rules.
- Staff/instructor bypass remains LMS-owned.
- Commerce never creates LMS Enrollment records.

## Safety

The provider returns plain values only. URLs are relative or HTTPS; labels are localized server-side; no HTML or component references are accepted. Commerce performs a bounded set of bulk queries independent of request count. The LMS bridge validates and normalizes this response again before returning it to Vue or authorizing a protected action.

Provider errors must be handled by LMS as generic unavailable locks for presentation and fail-closed decisions for protected mutations/consumption. Exception text must not reach learners.
