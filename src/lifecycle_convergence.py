"""Run SEC lifecycle reconciliation until the public feed reaches a stable state.

A single issuer CIK can have multiple independent S-1/S-1/A registrations that
reach distinct 424B4 finals at nearly the same time. ``lifecycle_reconciler``
intentionally reconciles exact registration lineages conservatively, so one pass
can promote one registration and expose another independent promotion only after
the first final is present in the payload. This wrapper repeats the same verified
SEC reconciliation against one discovery snapshot until no further lifecycle
changes remain, preventing a finalized parallel registration from being published
as stale pre-pricing for an extra feed cycle.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import dashboard_export
import edgar_client
import lifecycle_reconciler
import registration_lineage


def _reconcile_existing_final_records(
    payload,
    final_filings,
    soup_loader,
    lineage_resolver,
):
    """Reconcile every published 424B4 independently by exact accession.

    ``lifecycle_reconciler`` groups lifecycle state by issuer CIK so it can safely
    hand a pre-pricing registration to its final prospectus. A CIK can also contain
    multiple already-published 424B4 registrations. Rechecking those final rows one
    at a time prevents the first final under the CIK from shielding a later final
    from authoritative ticker, price, or offering-size repair.
    """
    filings = payload.get("filings")
    if not isinstance(filings, list):
        raise ValueError("Public feed must contain a filings list")

    reconciled = []
    repaired_total = 0
    removed_total = 0
    changed = False

    for filing in filings:
        if not isinstance(filing, dict) or not lifecycle_reconciler._is_final_record(filing):
            reconciled.append(filing)
            continue

        focused_payload, repaired, removed = lifecycle_reconciler.reconcile_payload(
            {"filings": [filing]},
            final_filings,
            soup_loader,
            lineage_resolver=lineage_resolver,
        )
        focused_filings = focused_payload.get("filings")
        if not isinstance(focused_filings, list) or len(focused_filings) > 1:
            raise RuntimeError(
                "Single-final lifecycle reconciliation returned an invalid record set"
            )

        repaired_total += repaired
        removed_total += removed
        changed = changed or bool(repaired or removed)
        if focused_filings:
            reconciled.append(focused_filings[0])

    current = dict(payload)
    current["filings"] = reconciled
    if changed:
        current["generated_at"] = datetime.now(timezone.utc).isoformat()
    return current, repaired_total, removed_total


def reconcile_payload_to_convergence(
    payload,
    final_filings,
    soup_loader,
    lineage_resolver,
    max_passes=8,
):
    """Repeat exact-lineage reconciliation until a pass makes no changes.

    ``max_passes`` limits mutation-bearing reconciliation passes. One additional
    verification pass is allowed after that boundary so a feed that becomes stable
    on the final permitted repair pass is accepted instead of being falsely rejected
    as non-convergent.
    """
    current = payload
    total_repaired = 0
    total_removed = 0

    for pass_number in range(1, max_passes + 2):
        current, final_repaired, final_removed = _reconcile_existing_final_records(
            current,
            final_filings,
            soup_loader,
            lineage_resolver,
        )
        current, repaired, removed = lifecycle_reconciler.reconcile_payload(
            current,
            final_filings,
            soup_loader,
            lineage_resolver=lineage_resolver,
        )
        repaired += final_repaired
        removed += final_removed
        if repaired == 0 and removed == 0:
            return current, total_repaired, total_removed, pass_number
        if pass_number > max_passes:
            break
        total_repaired += repaired
        total_removed += removed

    raise RuntimeError(
        "Lifecycle reconciliation did not converge within "
        f"{max_passes} mutation pass(es); refusing to publish an unstable feed"
    )


def reconcile_feed(output_path, days_back=60, max_passes=8):
    """Reconcile a feed to a fixed point using one SEC final-filings snapshot."""
    output_path = Path(output_path)
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    filings = [f for f in payload.get("filings", []) if isinstance(f, dict)]
    needs_reconciliation = any(
        lifecycle_reconciler._is_prepricing(filing)
        or lifecycle_reconciler._is_final_record(filing)
        for filing in filings
    )
    if not needs_reconciliation:
        dashboard_export.write_dashboard_csv(payload.get("filings", []), output_path)
        return payload, 0, 0, 0

    final_filings = edgar_client.find_recent_424b4_filings(days_back=days_back)
    lineage_resolver = registration_lineage.build_registration_lineage_resolver()
    payload, repaired, removed, passes = reconcile_payload_to_convergence(
        payload,
        final_filings,
        lifecycle_reconciler._load_final_soup,
        lineage_resolver,
        max_passes=max_passes,
    )

    if repaired or removed:
        temporary = output_path.with_suffix(output_path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        temporary.replace(output_path)

    dashboard_export.write_dashboard_csv(payload.get("filings", []), output_path)
    return payload, repaired, removed, passes


if __name__ == "__main__":
    import sys

    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("../docs/data/filings.json")
    _, repaired_count, removed_count, pass_count = reconcile_feed(target)
    print(
        f"Convergent lifecycle reconciliation completed in {pass_count} pass(es): "
        f"repaired/promoted {repaired_count} final 424B4 record(s) and removed "
        f"{removed_count} stale/unresolved record(s)."
    )
