# Monetization Strategy

## Credit Model
- Users purchase plans defined in `shared-specs/pricing_tiers.json`.
- Each FMU execution consumes at least one credit and charges Stripe for pay-per-run usage when applicable.
- Credits are decremented in the backend within `app/routes/billing.py` to maintain a single source of truth.

## Stripe Integration
- Use `StripeService.charge_per_execution` to record usage for metered billing.
- Configure webhook endpoint `/billing/webhook` to receive Stripe events and reconcile usage data.
- Webhook handlers update logs and can extend to top-up credits or downgrade plans based on payment status.

## Reporting
- The `/usage` endpoint returns current credit balances for authenticated users.
- Stripe dashboard provides revenue analytics while internal logs should capture execution metrics for audits.

## Future Enhancements
- Add rate limiting per plan to prevent abuse.
- Introduce prepaid credit bundles managed through Stripe Checkout Sessions.
- Provide self-service plan changes via the SDK and admin dashboard.
