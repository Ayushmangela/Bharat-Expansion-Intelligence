"""Full national MCA sweep: fetch + silver-transform every verified state,
one at a time, per docs/11-ROADMAP.md Phase 2. Goa and Bihar are already
loaded (Phase 1 checkpoint) and skipped here. Chhattisgarh is deliberately
excluded — see pipeline/connectors/mca_state_codes.py for why.

Each state's failure is caught and logged, not fatal to the sweep — a
problem with one state's data must not silently abort the other 30+.
"""

import json
import sys
import traceback
from datetime import date

from pipeline.connectors.mca import MCAConnector
from pipeline.connectors.mca_state_codes import STATE_FILTER_VALUES
from pipeline.transforms.mca_silver import transform_state

ALREADY_LOADED = {
    "goa", "bihar",  # Phase 1
    "andaman and nicobar islands", "andhra pradesh", "arunachal pradesh", "assam", "chandigarh",
    "delhi", "gujarat",  # completed this sweep; delhi/gujarat re-verified against the pagination-truncation fix
    "sikkim",  # fetched as a pre-sweep validation test
    "haryana", "himachal pradesh", "jammu & kashmir", "jharkhand",
    "ladakh", "kerala",  # fetched validating the concurrency change
}

SUMMARY_PATH = "/tmp/mca_national_sweep_summary.json"


def run() -> None:
    today = date.today()
    results = []

    all_filter_values = [
        (state_name, fv)
        for state_name, fvs in STATE_FILTER_VALUES.items()
        for fv in fvs
    ]

    for i, (state_name, filter_value) in enumerate(all_filter_values, 1):
        if filter_value in ALREADY_LOADED:
            print(f"[{i}/{len(all_filter_values)}] SKIP {state_name} ('{filter_value}') — already loaded in Phase 1", flush=True)
            continue

        print(f"[{i}/{len(all_filter_values)}] {state_name} ('{filter_value}') — fetching...", flush=True)
        try:
            connector = MCAConnector()
            payload = connector.fetch_state(filter_value)
            bronze_path = connector.write_bronze(payload, today, partition=f"state={filter_value}")
            connector.client.close()
            print(f"  fetched {len(payload.records)} rows -> {bronze_path}", flush=True)

            transform_result = transform_state(filter_value, ingest_date=today)
            print(f"  transformed: {json.dumps(transform_result)}", flush=True)

            results.append({"state": state_name, "filter": filter_value, "status": "success", **transform_result})
        except Exception as e:  # noqa: BLE001 — one state's failure must not abort the sweep
            print(f"  FAILED: {e}", flush=True)
            traceback.print_exc()
            results.append({"state": state_name, "filter": filter_value, "status": "failed", "error": str(e)})

        with open(SUMMARY_PATH, "w") as f:
            json.dump(results, f, indent=2, default=str)

    print("\n=== SWEEP COMPLETE ===", flush=True)
    n_success = sum(1 for r in results if r["status"] == "success")
    n_failed = sum(1 for r in results if r["status"] == "failed")
    total_loaded = sum(r.get("rows_loaded", 0) for r in results if r["status"] == "success")
    total_quarantined = sum(r.get("rows_quarantined", 0) for r in results if r["status"] == "success")
    print(f"states succeeded: {n_success}, failed: {n_failed}", flush=True)
    print(f"total rows loaded: {total_loaded}, total quarantined: {total_quarantined}", flush=True)
    print(f"summary written to {SUMMARY_PATH}", flush=True)


if __name__ == "__main__":
    run()
    sys.exit(0)
