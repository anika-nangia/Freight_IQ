"""Build api_data.json: a snapshot of every API response the website can request.

WHY THIS EXISTS
    The website fetches all of its numbers from a FastAPI backend. That backend
    needs scikit-learn, xgboost, scipy, numpy and pandas, which together are
    roughly 300 MB installed. Vercel's serverless functions cap a function at
    250 MB, so the real backend cannot be deployed there.

    It does not have to be recomputed per request. Every response the site can
    ask for is deterministic: the models are already trained, and the rate,
    line-up and weather data are historical and fixed. So this script RUNS the
    real backend once, for every corridor, and records the exact bytes it
    returns. The Vercel functions then serve those recorded responses.

    The numbers served publicly are therefore genuine model output. They are
    frozen at build time rather than recomputed on each visit, which for a
    historical dataset is the same thing.

    Re-run this after retraining or changing data:
        python tools/build_api_snapshot.py
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "freight-intelligence-sih"
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

# The exact payload api-status.js posts for the recommendation page.
CARGO_TYPE = "Coking Coal"
CARGO_TONNES = 55000

from backend.main import (  # noqa: E402
    corridor_series,
    list_corridors,
    model_report,
    query_route,
)
from backend.schemas import RouteQueryRequest  # noqa: E402


def key_of(origin: str, destination: str, vessel_class: str) -> str:
    return f"{origin}|{destination}|{vessel_class}"


def main() -> int:
    print("Building API snapshot from the live models...\n")

    report = model_report()
    corridors = list_corridors()
    print("  model report   : %d top-level keys" % len(report))
    print("  corridors      : %d" % corridors.get("count", 0))

    snapshot: dict = {
        "_meta": {
            "built_at": datetime.now(timezone.utc).isoformat(),
            "note": "Real model responses, recorded at build time. See "
                    "tools/build_api_snapshot.py for why.",
            "corridor_count": corridors.get("count", 0),
        },
        "model_report": report,
        "corridors": corridors,
        "route": {},
        "series": {},
    }

    for row in corridors.get("corridors", []):
        cid = row["corridor_id"]
        vc = row["vessel_class"]
        origin, destination = cid.split("->", 1)
        k = key_of(origin, destination, vc)

        req = RouteQueryRequest(
            origin=origin,
            destination=destination,
            vessel_class=vc,
            cargo_type=CARGO_TYPE,
            cargo_volume_mt=CARGO_TONNES,
        )
        route = query_route(req)
        snapshot["route"][k] = route

        series = corridor_series(origin, destination, vc, max_weeks=20)
        snapshot["series"][k] = series

        action = (route.get("risk_mitigation") or {}).get("action", "?")
        print("    %-34s %-9s  %s" % (cid, vc, action))

    out = ROOT.parent / "api_data.json"
    payload = json.dumps(snapshot, ensure_ascii=False, separators=(",", ":"))
    out.write_text(payload, encoding="utf-8")

    size_kb = len(payload.encode("utf-8")) / 1024
    print("\n  wrote %s  (%.1f KB)" % (out.name, size_kb))
    print("  route responses : %d" % len(snapshot["route"]))
    print("  series responses: %d" % len(snapshot["series"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
