"""
Static registry: operators, audiences, and region metadata.

REGIONS is a dict keyed by the frontend's region enum value so endpoints
can do REGIONS["IRQ_BAGHDAD"]["geohash_prefix"] directly.
"""
from __future__ import annotations

from typing import Any

REGIONS: dict[str, dict[str, Any]] = {
    "IRQ_BAGHDAD":  {"region": "IRQ_BAGHDAD",  "label": "Baghdad, Iraq",   "lat": 33.3152, "lon": 44.3661, "geohash_prefix": "sv8d"},
    "IRQ_MOSUL":    {"region": "IRQ_MOSUL",    "label": "Mosul, Iraq",     "lat": 36.3350, "lon": 43.1189, "geohash_prefix": "sv3p"},
    "SYR_ALEPPO":   {"region": "SYR_ALEPPO",   "label": "Aleppo, Syria",   "lat": 36.2021, "lon": 37.1343, "geohash_prefix": "sy7q"},
    "SYR_DAMASCUS": {"region": "SYR_DAMASCUS", "label": "Damascus, Syria", "lat": 33.5138, "lon": 36.2765, "geohash_prefix": "sv5t"},
    "YEM_SANAA":    {"region": "YEM_SANAA",    "label": "Sanaa, Yemen",    "lat": 15.3694, "lon": 44.1910, "geohash_prefix": "s87w"},
    "LBN_BEIRUT":   {"region": "LBN_BEIRUT",   "label": "Beirut, Lebanon", "lat": 33.8938, "lon": 35.5018, "geohash_prefix": "sv9j"},
}

_REGION_KEYS = list(REGIONS.keys())

OPERATORS: list[dict[str, Any]] = [
    {
        "id": "op-senior",
        "name": "Amira Hassan",
        "role": "senior",
        "regions": _REGION_KEYS,
        "avatarSeed": "amira-hassan",
    },
    {
        "id": "op-junior",
        "name": "Tariq Saleh",
        "role": "junior",
        "regions": ["IRQ_BAGHDAD", "IRQ_MOSUL"],
        "avatarSeed": "tariq-saleh",
    },
]

AUDIENCES: list[dict[str, Any]] = [
    {
        "id": "all_recipients",
        "label": "All recipients",
        "description": "Every registered account across all active regions.",
        "count": 14200,
        "regions": _REGION_KEYS,
        "roles": ["senior", "junior"],
        "channelsAvailable": ["app", "sms", "fallback"],
    },
    {
        "id": "medical_responders",
        "label": "Medical responders",
        "description": "Verified healthcare workers and first responders.",
        "count": 380,
        "regions": _REGION_KEYS,
        "roles": ["senior"],
        "channelsAvailable": ["app", "sms"],
    },
    {
        "id": "verified_eyewitnesses",
        "label": "Verified eyewitnesses",
        "description": "Accounts with at least one verified report in the last 30 days.",
        "count": 1540,
        "regions": _REGION_KEYS,
        "roles": ["senior", "junior"],
        "channelsAvailable": ["app", "sms", "fallback"],
    },
    {
        "id": "baghdad_residents",
        "label": "Baghdad residents",
        "description": "All accounts with a home geohash inside Greater Baghdad.",
        "count": 5700,
        "regions": ["IRQ_BAGHDAD"],
        "roles": ["senior", "junior"],
        "channelsAvailable": ["app", "sms", "fallback"],
    },
    {
        "id": "rescue_team",
        "label": "Rescue team",
        "description": "Explicit on-call list configured via RESCUE_TEAM_RECIPIENTS. Bypasses demo recipient — every member receives the SMS.",
        # count is overridden at runtime in /api/audiences from the env
        # var, so the card always reflects the current list size.
        "count": 0,
        "regions": _REGION_KEYS,
        "roles": ["senior", "junior"],
        "channelsAvailable": ["sms"],
    },
]

_OPERATOR_INDEX: dict[str, dict[str, Any]] = {op["id"]: op for op in OPERATORS}


def get_operator_by_id(operator_id: str) -> dict[str, Any] | None:
    return _OPERATOR_INDEX.get(operator_id)
