# FMU Gateway Certified Registry Walkthrough

The Certified FMU Registry layers a commercial marketplace and certification workflow on top of the existing FMU Gateway private API. It introduces new database models, storage helpers, service modules, HTTP routes, templates, and scripts that enable creators to sell FMUs while enforcing licensing and provenance requirements.

## Data Model

All marketplace entities are modelled in `private-api/app/models/marketplace.py` using SQLAlchemy. Key tables:

- **creators** – associates a user with Stripe Connect metadata and a display name.
- **fmu_packages** – high level catalog entries including listing state, certification badge, rating aggregates, and taxonomy fields.
- **fmu_versions** – uploaded binaries with file metadata, cryptographic hashes, signatures, validation status, and changelog.
- **listings** – monetisation configuration per SKU (download, execute-only, seat, org) including pricing, currency, license template, and revenue sharing.
- **purchases / licenses / execution_entitlements** – track license issuance, hashed license keys, entitlements, and run quotas.
- **ratings, validation_jobs, webhooks, dmca_takedowns, audit_log** – support community feedback, certification, webhook replay, compliance, and auditability.

Relationships ensure cascading deletes and allow navigation from users through purchases to entitlements. License keys are stored as salted hashes to satisfy at-rest security requirements.

## Storage & Provenance

`private-api/app/services/object_storage.py` writes FMU binaries to a configurable object storage root and issues short-lived signed URLs using HMAC tokens. `private-api/app/services/provenance.py` computes SHA-256 hashes, builds metadata manifests, and optionally signs digests with an ECDSA private key. Validation reports are persisted under `data/validation_reports` for later retrieval.

## Certification Pipeline

`private-api/app/services/validation_pipeline.py` exposes `validate_fmu(session, version_id)` which reads the stored FMU, runs sandboxed checks (stubbed for local testing), records a `validation_job`, and marks the latest package version as certified when successful. A CLI helper lives in `scripts/validation_worker.py` for batch execution.

## Marketplace Services

`private-api/app/services/marketplace_service.py` orchestrates creator onboarding, package creation, version uploads, listing configuration, license issuance, payouts, and moderation. It encapsulates payout calculations, license template snapshots, rating aggregation, and DMCA or admin actions. Licensing logic (issue, rotate, enforce, revoke) is implemented in `private-api/app/services/licensing_service.py`.

## API Endpoints

New FastAPI routers power both REST APIs and dashboard pages:

- `private-api/app/routes/creator.py` – creator onboarding (`/creator/apply`), package creation, version uploads with hashing/signature, listing setup, validation status checks, and publishing.
- `private-api/app/routes/marketplace.py` – buyer search, package detail with badges and validation reports, checkout initiation, license management, key rotation, and ratings.
- `private-api/app/routes/admin_marketplace.py` – admin unlisting, license revocation, and DMCA review/resolve operations.
- `private-api/app/routes/billing.py` – extended Stripe webhook handler issuing marketplace licenses, revoking on refunds, and auditing payouts.
- `private-api/app/routes/execute_fmu.py` – now accepts optional `license_key`, `package_id`, and `version_id` form fields, enforcing execute-only entitlements and skipping credit deductions for download SKUs.
- `private-api/app/routes/dashboard.py` – new template-backed pages for the creator console, public marketplace, and buyer account.

Templates for these views live in `private-api/app/templates`, including license text snippets required during checkout.

## Licensing & Enforcement

License issuance snapshots the selected markdown template, stores hashed keys, and (for execute-only SKUs) provisions run entitlements. Download SKUs expose signed URLs via the license APIs, while execute-only runs are decremented inside the execution endpoint. License rotation regenerates keys with fresh salts.

## Stripe & Financials

Stripe Connect data is stubbed for local usage. Marketplace purchases can be triggered through REST calls or Stripe webhooks. Revenue splits respect `revenue_share_bps` and configurable platform fees. Refund webhooks revoke entitlements and mark purchases refunded. Payout events are recorded in the audit log.

## Moderation & Compliance

DMCA complaints are captured via the `dmca_takedowns` table and surfaced through admin routes. All administrative and payout actions write structured entries to the `audit_log` table. Content policies and proprietary notice are documented in `private-api/PRIVATE_NOTICE.md`.

## Scripts & Examples

- `scripts/creator_demo.py` – demonstrates applying as a creator and creating a package via HTTP.
- `scripts/buyer_demo.py` – demonstrates searching the marketplace and listing licenses.
- `scripts/validation_worker.py` – CLI entry point that validates a specific FMU version.

## Tests

`tests/test_marketplace.py` provides unit coverage for creator uploads, validation and certification, license issuance with signed URLs, execute-only entitlements, and takedown flows. Existing fixtures bootstrap an isolated SQLite database for deterministic testing.

## Configuration

New environment variables:

```
SIGNING_PRIVATE_KEY_PATH=/run/secrets/fmu_signing_key.pem
OBJECT_STORAGE_BUCKET=fmu-registry
OBJECT_STORAGE_ROOT=./data/object_storage
PLATFORM_FEE_BPS=1500
STRIPE_CONNECT_ENABLED=true
```

These complement earlier `.env` entries to enable provenance signing, object storage, and revenue share configuration.

