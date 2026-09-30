"""Shared helpers for the Vercel serverless functions.

These functions do no machine learning. They read api_data.json, which was
written by tools/build_api_snapshot.py from the real trained models, and return
the exact response the FastAPI backend produced. Keeping them dependency-free is
deliberate: it is what lets the site deploy to Vercel's 250 MB function limit.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict

_DATA: Dict[str, Any] | None = None

CORS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
}


def load() -> Dict[str, Any]:
    """Read api_data.json, cached for the life of the warm function."""
    global _DATA
    if _DATA is not None:
        return _DATA
    here = Path(__file__).resolve()
    candidates = [
        Path(os.environ.get("FREIGHTIQ_DATA", "")) if os.environ.get("FREIGHTIQ_DATA") else None,
        here.parent,
        here.parent.parent,
        here.parent.parent.parent,
        Path.cwd(),
        Path.cwd() / "api",
    ]
    for base in candidates:
        if base is None:
            continue
        for name in (base / "api_data.json", base.parent / "api_data.json"):
            if name.is_file():
                _DATA = json.loads(name.read_text(encoding="utf-8"))
                return _DATA
    raise FileNotFoundError(
        "api_data.json not found. Run: python tools/build_api_snapshot.py"
    )


def key(origin: str, destination: str, vessel_class: str) -> str:
    return f"{origin}|{destination}|{vessel_class}"


def unavailable(reason: str) -> Dict[str, Any]:
    """The same shape the backend returns when a corridor has no history.

    The website already knows how to render this honestly, so a miss produces
    the correct message on screen instead of an error.
    """
    return {
        "available": False,
        "reason": reason,
        "freight_forecast": {"available": False, "reason": reason},
        "congestion_model": {"available": False, "reason": reason},
        "market_timing": {"available": False, "reason": reason},
        "contract_comparison": {"available": False, "reason": reason},
        "vessel_optimizer": {"available": False, "reason": reason},
        "idle_analysis": {"available": False, "reason": reason},
        "risk_mitigation": {"available": False, "reason": reason},
        "explanation": {"available": False, "reason": reason},
    }
