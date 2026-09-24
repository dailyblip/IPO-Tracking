# IPO Roll development handoff

## 2026-09-24: private Liquidity Analysis foundation

Implemented the holder Liquidity Analysis button, authenticated GET/POST API, private static database snapshots, reopen without regeneration, explicit versioned refresh and retry idempotency. The UI uses four categories: currently liquid, potential future liquidity, illiquid, and insufficient evidence. Evidence includes ownership passages, separately reviewed footnotes/restrictions, filing accession and document hash in the stored snapshot. Shared reviewed facts and private account reports are separate. No service-role key or AI provider is used.

Applied staging migration `20260924164646_private_liquidity_reports.sql`. The database generates report contents itself, rejects client-authored reports, enforces ownership/entitlement/access controls and grants no customer updates/deletes. Expired assessments, uncertain current positions or personal economic interest cannot be reported as currently liquid. Lock-up expiry does not automatically make shares liquid. Source facts changing do not rewrite saved snapshots.

Validation: production build, 10 unit/API tests, targeted browser test for the holder popup/reopen/refresh/Escape/focus, and rollback SQL tests for classification, private access, request replay, refresh versions, tamper denial and revoked entitlement passed. Browser authentication is simulated using the private pilot fixture; database policies were exercised in staging with disposable accounts and rolled back. This is not a completed live user login test.

The 22-company/44-biography month import is already applied, with no duplicate rows from replay. No new real holdings or liquidity assessments have been imported in this iteration. Current live reports therefore accurately report insufficient holdings evidence. Quote valuation remains unavailable. Do not describe this foundation as a completed financial analysis or an AI-powered review.

Publication: prepared for the existing commercial branch and Render staging. Verify the deployed asset before claiming the button is live. Legacy production engine, feed, Pages and schedules are unchanged.

## Next executable work

1. Verify this staging release and test actual authenticated UI when an authorized browser session is available.
2. Review and backfill exact ownership-table rows and holder-specific footnotes for the existing cohort. Separate issuer securities, share classes, trust/fund attribution, projected vs current holdings and overlapping positions. Reuse the original engine where appropriate.
3. Populate reviewed liquidity assessments only with explicit source passages, conditions, dates and review validity. Add release-date calculation tests for exact contractual wording before automating lock-up calculations. No default 180-day assumptions.
4. Add report history selection and source-version details in the UI; old snapshots are retained already.
5. Integrate security-matched licensed quotes and reconciled positions before exposing market estimates. Do not infer future prices, cash proceeds or saleability.
6. Evaluate a source-grounded AI extraction/explanation adapter after the deterministic evidence path is established. No paid calls or new external provider transmission yet.

## Owner decisions / launch gates for the 6 PM digest

- Quote provider: choose a provider with commercial display/storage rights before live or last-known pricing integration; research options before asking the owner to spend.
- AI provider: only request setup/cost approval if evidence review warrants adding it. Current foundation needs no AI key.
- Auth: existing leaked-password-protection warning remains. Review plan/support and configure before commercial launch: https://supabase.com/docs/guides/auth/password-security#password-strength-and-leaked-password-protection . No new security advisor warning was introduced by the liquidity schema.
- Payments, commercial source rights, production Auth and iporoll.com launch remain future gates. Continue staging work without waiting for these.

Maintain this ledger on subsequent runs. Do not re-import the month batch or reapply migrations blindly. Check Refresh Prospect Ownership History before every commit and preserve unrelated changes. Continue the established three daily development sessions and 6 PM Pacific digest.
