# Monthly subscription access contract

IPO Roll's domain is iporoll.com. Authentication is provided by Supabase Auth. The payment provider, monthly price, tax handling, refund policy and dunning/grace policy are not configured or selected by this implementation.

## Implemented boundary

- A verified non-anonymous login can call GET /api/account, even without research access.
- The account response contains only the current user's identity, research-access boolean, monthly billing interval and `not_configured` billing status. It does not claim a payment or active subscription.
- Research routes still require server-managed entitlement checks on every request. Database RLS independently enforces access. User-editable metadata is never an authorization source.
- A signed-in account without access sees an account-ready screen with an access recheck and sign out. The frontend sends no research requests from that screen.
- Existing profiles/watchlists remain user-owned. There is no billing or checkout implementation, no configured prices, no customer creation and no charges.

## Payment integration contract for the next phase

1. Store provider customer IDs against verified application user IDs. Never accept a browser-submitted user ID or customer ID as authorization.
2. Create monthly checkout sessions server-side from an allowlisted price and trusted return origin. Require login first.
3. Verify webhook signatures against raw request bytes before processing. Store unique event IDs, make retries idempotent, and reconcile current subscription state when events arrive out of order.
4. Update subscription records and access expiry transactionally. A checkout redirect or success URL must never grant access.
5. Allow authenticated accounts to reach their own billing portal even when research access has expired.
6. Cancellation at period end should preserve paid-through access. Failed-payment behavior needs an explicit grace policy before launch; it must not create indefinite access. Handle cancellation reversal, renewal, refunds, disputes and administrative revocation distinctly.
7. Separate staging/test-mode payment configuration from production. Test renewals, duplicate/out-of-order notifications and expiry before enabling real checkout.
8. Add terms/privacy links, pricing disclosures and cancellation instructions once those business decisions are settled. Do not invent a price or advertise signup before the service is ready.

The existing entitlement table is an access projection, not an accounting ledger. Future provider-neutral customer/subscription/event tables should preserve billing history and reconcile entitlements. Current manual staging grants are not evidence of payment.
