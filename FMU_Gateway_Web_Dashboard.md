# FMU Gateway Web Dashboard

This document summarizes the new server-rendered engineer dashboard for the FMU Gateway private API. The implementation introduces secure authentication flows, billing workflows, usage visibility, and API key lifecycle management while preserving compatibility with existing JSON APIs and automated clients.

## Frontend Architecture

- **Templating:** FastAPI with Jinja2 templates under `private-api/app/templates/`, using a shared `layout.html` shell and individual views (`dashboard.html`, `billing.html`, `usage.html`, `api_keys.html`, `login.html`, `register.html`).
- **Styling:** Minimal dark-mode theme in `private-api/app/static/css/styles.css`, plus a lightweight SVG logo and an ES module (`static/js/api_keys.js`) for dynamic API-key CRUD.
- **Routing:** `private-api/app/routes/dashboard.py` serves authenticated HTML pages and gracefully handles form submissions (with CSRF checks, rate limiting, and JWT cookies). JSON requests continue to be processed by the existing `routes/auth.py` endpoints to ensure backwards compatibility.

## Backend Enhancements

- **Authentication:**
  - Added hashed-password support on the `User` model (`hashed_password` column) and password hashing/verification helpers in `services/auth_service.py`.
  - Login forms accept either email/password or API key and establish secure HttpOnly JWT cookies. JSON login remains unchanged for API clients.
- **API Keys:**
  - Introduced an `APIKey` SQLAlchemy model with relationships to `User` and `UsageLog`, plus CRUD endpoints in `routes/api_keys.py`.
  - UI lists keys, tracks usage counts, and supports CSRF-protected creation/revocation.
- **Usage Reporting:**
  - Extended `UsageLog` with optional `api_key_id` linkage and added REST endpoints in `routes/usage.py`, including CSV export support.
- **Billing:**
  - Dashboard billing view integrates existing Stripe services for upgrade flows, with redirect-based checkout initiation and customer portal linking.
- **Security:**
  - CSRF tokens issued per session, in-memory rate limiting, Secure/HttpOnly cookies, and logout flows that clear authentication/CSRF cookies.
  - Maintains HTTPS expectations and is ready for deployment behind a reverse proxy (e.g., Nginx or Cloudflare Tunnel).

## Updated Project Structure

```
private-api/
├── app/
│   ├── routes/
│   │   ├── dashboard.py        # HTML-facing views and form handling
│   │   ├── api_keys.py         # Authenticated API key JSON endpoints
│   │   └── usage.py            # Usage history + CSV export endpoints
│   ├── services/
│   │   └── frontend_service.py # Template rendering, CSRF, rate limiting, auth helpers
│   ├── templates/              # Jinja2 templates (layout, dashboard, billing, usage, api keys, auth forms)
│   └── static/                 # Shared CSS/JS/logo assets
└── ...                         # Existing FastAPI application modules
```

The new components are registered in `private-api/app/__init__.py`, which now mounts static assets and includes the dashboard, usage, and API-key routers alongside the existing authentication, billing, execution, and registry APIs.

## Feature Highlights

1. **Dashboard Overview** – Greets the engineer, shows remaining credits, primary API key, quick actions, documentation links, and a Chart.js visualization of recent FMU runs.
2. **Billing & Upgrades** – Displays plan tiers, launches Stripe Checkout with CSRF-protected forms, and links to the hosted billing portal.
3. **Usage Analytics** – Renders a sortable table of FMU executions (with CSV export) and exposes JSON endpoints for integrations.
4. **API Key Management** – Lists active/revoked keys, generates new credentials, revokes compromised keys, and surfaces per-key usage counts.
5. **Authentication UX** – Registration and login pages with CSRF protection, password hashing, JWT cookies, and logout handling while preserving the original JSON API semantics.

## Testing

- Full backend regression suite (`pytest`) passes after schema updates to conditionally surface crypto payment methods only when a Coinbase session is issued.
- UI scripts rely solely on existing FastAPI endpoints, so no additional build tooling is required.

## Next Steps

- Connect Stripe webhooks and database migrations in production to accommodate the new `hashed_password`, `APIKey`, and `api_key_id` fields.
- Add unit/integration tests covering the new HTML routes if browser automation is desired.
- Optionally extend rate limiting with Redis or another persistent backend for multi-instance deployments.
