# Private SEC capture through GitHub Actions

The owner authorized reusing the existing `SEC_EDGAR_USER_AGENT` repository secret
on September 26, 2026. The secret stays in GitHub Actions; it is never printed,
exported, archived or copied into this workspace.

`IPO Roll private SEC capture` runs only when
`apps/ipo-roll/config/sec-capture-request.json` changes on `ipo-roll/foundation`.
It has no schedule and makes no database or repository writes. This push trigger
works before a workflow is present on main; do not merge into main to activate it.
Production workflows, feeds and schedules remain untouched.

Requests accept either one to four public CIK/accession pairs (`sec-capture-request/1`)
or a date-only discovery interval (`sec-discovery-request/1`). The latter fetches
canonical dated SEC daily indexes for at most seven calendar days, discovers exact
CIK/accession/form/date candidates, and captures up to four without supplied issuer
names. It stores hash-bound indexes, the private discovery queue, source packets and
explicit retrieval/interpretation holds in the encrypted artifact. Current-day or
missing indexes remain incomplete; discovery never establishes IPO eligibility.
See `discovery-pipeline.md` for durable checkpoint/replay and reviewed handoff.
The job itself still requires the existing request-file push trigger. It is not an
independently scheduled or unattended source-approval/import service.

Update those selectors under the development lock and ownership-history commit
guard. The runner resolves SEC registration metadata, captures the root/current
filing and latest preceding amendment, and marks all evidence unreviewed. It
paces serial requests at one second, reuses files within the batch, and has
request, byte, per-document and runtime bounds. Capturing the latest amendment
does not establish that all preliminary price history has been reviewed.

Only AES-256-GCM CMS ciphertext is uploaded as a seven-day Actions artifact.
No plaintext source, normalized text, private report or secret is uploaded.
The committed X.509 recipient certificate is public. Its SHA-256 fingerprint is
`DDD3905E4F33F62A41A5B38CCE700B43D046206830CA6267E7EB16C00EC03C5D`.
The owner-private recovery bundle is `IPO-Roll-Capture-Recovery-Key.tar.gz`
(`libfile_0985a1a09e1481919b9d4b6911b52070`); local copy is under ignored
`import-output/capture-recovery/`. Never put that private key in Git or logs.

Download the ciphertext artifact, then decrypt locally using:

```sh
openssl cms -decrypt -binary -inform DER -in evidence.cms \
  -inkey private-key.pem -out evidence.tar.gz
```

Check the authenticated decryption exit status before reading any output. Inspect
archive paths before extracting. Verify every manifest file's SHA-256 and byte
count before using it. Keep plaintext under ignored `import-output/`. The
discovery capture IDs are not canonical intake IDs: bind exact CIK/accession/form/
date to a validated SEC-index intake before generating a reviewed release.
Captured data does not change staging until separate source review and import QA.

If a source is held, the public job logs expose only aggregate counts and error
types. Partial captures are encrypted for recovery. Missing contact configuration
fails closed before any SEC request. No paid provider or database credential is
needed for this job.
