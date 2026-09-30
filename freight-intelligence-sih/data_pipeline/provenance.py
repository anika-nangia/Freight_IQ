"""
Provenance registry for FreightIQ.

Every dataset the system reads is declared here with:
  tier      : observed | derived | estimated | unavailable
  source    : who published it / which endpoint
  as_of     : last date the data covers
  coverage  : what period and which entities the rows cover

Nothing in this project may return a number that is not traceable to a row in
this registry. `assert_provenance()` is the guard the API tests use.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
RAW = DATA / "raw"
EXTERNAL = DATA / "external"
INTERIM = DATA / "interim"
MODELS = ROOT / "models"
ARTIFACTS = MODELS / "artifacts"

OBSERVED = "observed"        # published/observed market data
DERIVED = "derived"          # computed by our code from observed data
ESTIMATED = "estimated"      # modelled from proxy inputs because no observation exists
UNAVAILABLE = "unavailable"  # no source; the API must say so instead of guessing


@dataclass
class DatasetSpec:
    key: str
    path: str
    tier: str
    source: str
    source_url: str
    description: str
    as_of: Optional[str] = None
    period: Optional[str] = None
    entities: Optional[str] = None
    rows: Optional[int] = None
    notes: str = ""
    license: str = "unknown"

    def exists(self) -> bool:
        return (ROOT / self.path).exists()

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["present"] = self.exists()
        return d


# --------------------------------------------------------------------------
# Registry
# --------------------------------------------------------------------------
REGISTRY: Dict[str, DatasetSpec] = {}


def _reg(spec: DatasetSpec) -> DatasetSpec:
    REGISTRY[spec.key] = spec
    return spec


_reg(DatasetSpec(
    key="route_rates_weekly",
    path="data/training_matrix.csv",
    tier=OBSERVED,
    source="Project dataset (origin/vessel-level weekly USD/MT assessments). "
           "Compiled by the team; the originating report has not been confirmed.",
    source_url="",
    description="Weekly freight rate observations per (load_port, unload_port, vessel_type).",
    period="2025-10-03 .. 2026-03-27",
    entities="11 lanes x 4 vessel classes, East Coast India discharge",
    license="internal",
    notes="PROVENANCE GAP: no upstream publication confirmed. Treat as project data of "
          "unknown origin until the team supplies the source. Every model metric that "
          "depends on it inherits this caveat.",
))

_reg(DatasetSpec(
    key="port_lineups",
    path="data/vessel_snapshots.csv",
    tier=OBSERVED,
    source="Port authority daily line-up reports (12 snapshot dates).",
    source_url="",
    description="Per-port vessel line-up: status, berth, cargo, direction, arrival, ETCD.",
    period="2026-08-10 .. 2026-08-31",
    entities="14 East Coast Indian ports",
    license="internal",
    notes="Carries realized turnaround (arrival -> ETCD) and queue counts. "
          "Covers only August 2026, so it does NOT overlap the rate history window.",
))

_reg(DatasetSpec(
    key="berth_status",
    path="data/berth_operations.csv",
    tier=OBSERVED,
    source="Port authority berth status reports (12 snapshot dates).",
    source_url="",
    description="Berth-level occupancy: berth name and vacant/occupied status.",
    period="2026-08-10 .. 2026-08-31",
    entities="6 ports, 453 berth rows",
    license="internal",
    notes="All rows are 'Vacant' status; used as berth-capacity denominator.",
))

_reg(DatasetSpec(
    key="port_constraints",
    path="data/port_constraints.csv",
    tier=OBSERVED,
    source="Port authority / published berth capability data, per-row source in international_loading_ports.csv.",
    source_url="",
    description="Discharge port limits: max draft, max LOA, max beam, berths, handling rate.",
    entities="7 East Coast India discharge ports",
    license="internal",
))

_reg(DatasetSpec(
    key="loading_port_constraints",
    path="data/international_loading_ports.csv",
    tier=OBSERVED,
    source="Terminal operators (each row carries its own source_url).",
    source_url="",
    description="Origin-side terminal limits for Australia, Indonesia, Mozambique, USA, Russia.",
    entities="13 terminals, 5 origin countries",
    license="internal",
))

_reg(DatasetSpec(
    key="vessel_specs",
    path="data/vessel_specs.csv",
    tier=OBSERVED,
    source="Class reference data (DWT / LOA / beam / draft / handling rate / day rate).",
    source_url="",
    description="Dry bulk vessel class specification table.",
    entities="5 classes: Handysize .. Capesize",
    license="internal",
))

_reg(DatasetSpec(
    key="world_bank_pink_sheet",
    path="data/external/world_bank_pink_sheet.csv",
    tier=OBSERVED,
    source="World Bank Commodity Price Data (The Pink Sheet), monthly.",
    source_url="https://thedocs.worldbank.org/en/doc/18675f1d1639c7a34d463f59263ba0a2-0050012025/related/CMO-Historical-Data-Monthly.xlsx",
    description="Monthly coal (Australia, South Africa), iron ore cfr spot, crude oil benchmarks.",
    license="CC-BY 4.0 (World Bank)",
    notes="Published with roughly a 2-month lag, so features are lagged by one month "
          "before use. Run data_pipeline/fetchers/world_bank_prices.py to refresh.",
))

_reg(DatasetSpec(
    key="port_weather",
    path="data/external/port_weather_daily.csv",
    tier=OBSERVED,
    source="Open-Meteo Historical Weather API (free, no key).",
    source_url="https://archive-api.open-meteo.com/v1/archive",
    description="Daily wind max, precipitation and cyclone proxy for discharge ports.",
    license="CC-BY 4.0 (Open-Meteo)",
    notes="Only ports with coordinates in port_constraints.csv are covered. "
          "Run data_pipeline/fetchers/open_meteo_weather.py to refresh.",
))

_reg(DatasetSpec(
    key="fx_usd_inr",
    path="data/external/fx_usd_inr.csv",
    tier=OBSERVED,
    source="Frankfurter API (ECB reference rates, free, no key).",
    source_url="https://api.frankfurter.dev/v1/",
    description="Daily USD/INR reference rate.",
    license="CC-BY 4.0 (ECB via Frankfurter)",
    notes="Used only for INR presentation of USD amounts, never as a model feature.",
))

_reg(DatasetSpec(
    key="bdi_subindices",
    path="data/external/bdi_subindices.csv",
    tier=UNAVAILABLE,
    source="Baltic Exchange. Free redistribution endpoints were unreachable at build time "
           "(HTTP 403 / JS challenge). Supply a CSV of daily BDI, BCI, BPI, BSI, BHSI.",
    source_url="https://www.balticexchange.com/en/data-services/market-information0.html",
    description="Dry bulk freight index and vessel-class sub-indices.",
    license="Baltic Exchange - subscription",
    notes="data_pipeline/fetchers/bdi_subindices.py picks this file up automatically the "
          "moment it exists. Until then no index feature enters any model.",
))


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
def refresh_counts() -> None:
    """Fill in row counts for datasets that are present. Cheap, called at startup."""
    for spec in REGISTRY.values():
        p = ROOT / spec.path
        if not p.exists() or p.suffix.lower() not in (".csv", ".json"):
            continue
        try:
            with p.open("r", encoding="utf-8", errors="ignore") as fh:
                spec.rows = max(0, sum(1 for _ in fh) - 1)
        except OSError:
            spec.rows = None


def coverage_report() -> List[Dict[str, Any]]:
    """Machine-readable data-coverage panel. Feeds GET /api/data-coverage."""
    refresh_counts()
    out = []
    for spec in REGISTRY.values():
        d = spec.to_dict()
        d["status"] = "loaded" if spec.exists() else spec.tier
        out.append(d)
    return out


def coverage_by_tier() -> Dict[str, int]:
    rep = coverage_report()
    counts: Dict[str, int] = {}
    for r in rep:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    return counts


def get(key: str) -> DatasetSpec:
    if key not in REGISTRY:
        raise KeyError(f"unknown dataset '{key}'. Declare it in data_pipeline/provenance.py")
    return REGISTRY[key]


def provenance_block(keys: List[str]) -> Dict[str, Any]:
    """Compact provenance block attached to API responses."""
    out = []
    for k in keys:
        s = get(k)
        out.append({"key": k, "tier": s.tier if s.exists() else UNAVAILABLE,
                    "source": s.source, "as_of": s.as_of, "period": s.period,
                    "loaded": s.exists()})
    return {"datasets": out, "generated_at": datetime.now().isoformat(timespec="seconds")}


def envelope(data: Dict[str, Any], keys: List[str], confidence: Optional[str] = None) -> Dict[str, Any]:
    """Wrap any API payload with provenance + confidence. Used by every endpoint."""
    data = dict(data)
    data["provenance"] = provenance_block(keys)
    if confidence:
        data["confidence"] = confidence
    return data


def assert_provenance(payload: Any) -> None:
    """Raise if a response dict carries numeric leaves with no provenance anywhere.

    Used by tests: a route query that returns a number must also return provenance.
    """
    if not isinstance(payload, dict):
        return
    if "provenance" not in payload:
        raise AssertionError("response contains no provenance block")


def unavailable(key: str, reason: str) -> Dict[str, Any]:
    """The only sanctioned way to answer 'we do not have this'."""
    s = get(key)
    return {
        "available": False,
        "reason": reason,
        "provenance": {
            "dataset": key,
            "tier": UNAVAILABLE,
            "source": s.source,
            "source_url": s.source_url,
        },
    }
