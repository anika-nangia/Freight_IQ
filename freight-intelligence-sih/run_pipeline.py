"""
Rebuild the whole pipeline in order, then report what each stage produced.

    python run_pipeline.py            # fetch (skipped if cached), build, train
    python run_pipeline.py --no-fetch # rebuild from the cached external CSVs only
    python run_pipeline.py --fetch    # force a refresh of the external sources

Every step is a separate module and can be run on its own. This script exists so the
order is written down once instead of being remembered.
"""
from __future__ import annotations

import argparse
import runpy
import sys
import time
from pathlib import Path
from typing import Callable, List, Tuple

ROOT = Path(__file__).resolve().parents[0]
sys.path.insert(0, str(ROOT))

EXTERNAL = ROOT / "data" / "external"
RAW = ROOT / "data" / "raw"

FETCHERS: List[Tuple[str, str, Path]] = [
    ("World Bank Pink Sheet -> coal / iron ore / oil",
     "data_pipeline.fetchers.world_bank_prices", RAW / "CMO-Historical-Data-Monthly.xlsx"),
    ("Open-Meteo -> port wind and rainfall",
     "data_pipeline.fetchers.open_meteo_weather", EXTERNAL / "port_weather_daily.csv"),
    ("Frankfurter (ECB) -> USD/INR",
     "data_pipeline.fetchers.frankfurter_fx", EXTERNAL / "fx_usd_inr.csv"),
]

# Not run automatically: there is no free source. Supply the CSV and this picks it up.
MANUAL = ("Baltic sub-indices (BDI/BCI/BPI/BSI/BHSI) - no free source; "
          "data_pipeline/fetchers/bdi_subindices.py --input <file>")

BUILDERS: List[Tuple[str, str]] = [
    ("Monthly corridor table (contract-horizon view)",
     "data_pipeline.build_corridor_table"),
    ("Weekly modelling panel (leak-free features)",
     "data_pipeline.build_weekly_panel"),
    ("Congestion dataset (observed turnarounds)",
     "data_pipeline.build_congestion_dataset"),
]

TRAINERS: List[Tuple[str, str]] = [
    ("Model 2 - freight rate forecaster (walk-forward)",
     "models.model_2_freight.train_freight"),
    ("Model 1 - port congestion and turnaround",
     "models.model_1_congestion.train_congestion"),
]


def run(label: str, module: str) -> bool:
    print(f"\n{'=' * 78}\n{label}\n  python -m {module}\n{'=' * 78}")
    t0 = time.time()
    try:
        # runpy, not __import__: importing a module only defines it, so every stage
        # would report success in 0.0s while doing nothing.
        runpy.run_module(module, run_name="__main__", alter_sys=True)
        return True
    except SystemExit as e:
        if e.code:
            print(f"  FAILED: exited with code {e.code}")
            return False
        return True
    except Exception as e:  # noqa: BLE001 - reported, pipeline continues
        print(f"  FAILED: {type(e).__name__}: {e}")
        return False
    finally:
        print(f"  [{time.time() - t0:.1f}s]")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--no-fetch", action="store_true", help="use cached external data only")
    ap.add_argument("--fetch", action="store_true", help="force a refresh of external data")
    ap.add_argument("--skip-train", action="store_true")
    args = ap.parse_args()

    ok = True
    if not args.no_fetch:
        for label, module, cache in FETCHERS:
            if args.fetch or not cache.exists():
                ok &= run(f"FETCH: {label}", module)
            else:
                print(f"\n[skip] {label}: cached at {cache.relative_to(ROOT)} "
                      f"(use --fetch to refresh)")
    print(f"\n[note] {MANUAL}")

    for label, module in BUILDERS:
        ok &= run(f"BUILD: {label}", module)

    if not args.skip_train:
        for label, module in TRAINERS:
            ok &= run(f"TRAIN: {label}", module)

    print(f"\n{'=' * 78}")
    if ok:
        print("Pipeline complete. Start the API with:  uvicorn backend.main:app --reload")
        print("Then read what the system actually knows:  GET /api/data-coverage")
        print("And how the models were validated:        GET /api/model-report")
    else:
        print("Pipeline finished with errors. See above for the failing stage.")
    print("=" * 78)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
