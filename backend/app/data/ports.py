"""Single source of truth for port coordinates (server-side only).

Coordinates are approximate port locations (good to a few km), which is well
within the ~11 km grid resolution of the weather provider.

IMPORTANT: reconcile this list with the destination ports in your project's
datasets. Either delete rows you don't use, or set SUPPORTED_PORTS in .env.
"""
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Port:
    name: str
    state: str
    latitude: float
    longitude: float


PORTS: dict[str, Port] = {
    p.name: p
    for p in (
        Port("Paradip", "Odisha", 20.2647, 86.6947),
        Port("Dhamra", "Odisha", 20.7800, 86.9700),
        Port("Gopalpur", "Odisha", 19.2570, 84.9060),
        Port("Visakhapatnam", "Andhra Pradesh", 17.6800, 83.2800),
        Port("Gangavaram", "Andhra Pradesh", 17.6200, 83.2300),
        Port("Kakinada", "Andhra Pradesh", 16.9333, 82.2833),
        Port("Krishnapatnam", "Andhra Pradesh", 14.2500, 80.1167),
        Port("Chennai", "Tamil Nadu", 13.0900, 80.2900),
        Port("Ennore", "Tamil Nadu", 13.2500, 80.3333),
        Port("Tuticorin", "Tamil Nadu", 8.7500, 78.1833),
        Port("Haldia", "West Bengal", 22.0333, 88.0667),
        Port("Kolkata", "West Bengal", 22.5400, 88.3200),
        # Added from vessel_snapshots.csv; approximate anchorage/port locations.
        Port("Karaikal", "Puducherry", 10.9200, 79.8500),
        Port("Kattupalli", "Tamil Nadu", 13.3000, 80.3500),
        Port("Sagar", "West Bengal", 21.6500, 88.0800),
        Port("Sandheads", "West Bengal", 21.0000, 88.3000),
    )
}

_ALIASES: dict[str, str] = {
    "vizag": "Visakhapatnam",
    "vishakhapatnam": "Visakhapatnam",
    "visakhapatnam": "Visakhapatnam",
    "madras": "Chennai",
    "kamarajar": "Ennore",
    "thoothukudi": "Tuticorin",
    "v.o. chidambaranar": "Tuticorin",
}


def _normalise(name: str) -> str:
    text = re.sub(r"\s+", " ", name.strip().lower())
    text = re.sub(r"^port of ", "", text)
    return re.sub(r" port$", "", text)


def find_port(name: str, allowed: list[str] | None = None) -> Port | None:
    """Resolve a user-supplied name to a known port, or None."""
    key = _normalise(name)
    canonical = _ALIASES.get(key)
    if canonical is None:
        canonical = next((p for p in PORTS if p.lower() == key), None)
    if canonical is None:
        return None
    if allowed:
        allowed_keys = {_ALIASES.get(_normalise(a), a).lower() for a in allowed}
        if canonical.lower() not in allowed_keys:
            return None
    return PORTS[canonical]


def list_ports(allowed: list[str] | None = None) -> list[Port]:
    return [p for p in PORTS.values() if find_port(p.name, allowed) is not None]
