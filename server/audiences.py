from .schemas import Audience

REGION_META: dict[str, dict] = {
    "IRQ_BAGHDAD": {"label": "Baghdad, Iraq", "lat": 33.3152, "lon": 44.3661},
    "IRQ_MOSUL": {"label": "Mosul, Iraq", "lat": 36.3489, "lon": 43.1577},
    "SYR_ALEPPO": {"label": "Aleppo, Syria", "lat": 36.2021, "lon": 37.1343},
    "SYR_DAMASCUS": {"label": "Damascus, Syria", "lat": 33.5138, "lon": 36.2765},
    "YEM_SANAA": {"label": "Sana'a, Yemen", "lat": 15.3694, "lon": 44.1910},
    "LBN_BEIRUT": {"label": "Beirut, Lebanon", "lat": 33.8938, "lon": 35.5018},
}

AUDIENCES: list[Audience] = [
    Audience(
        id="civilians_iraq",
        label="Civilians — Iraq",
        description="All registered civilian phones in Iraq.",
        count=18420,
        regions=["IRQ_BAGHDAD", "IRQ_MOSUL"],
        roles=["civilian"],
        channelsAvailable=["app", "sms", "fallback"],
    ),
    Audience(
        id="civilians_syria",
        label="Civilians — Syria",
        description="All registered civilian phones in Syria.",
        count=11200,
        regions=["SYR_ALEPPO", "SYR_DAMASCUS"],
        roles=["civilian"],
        channelsAvailable=["app", "sms", "fallback"],
    ),
    Audience(
        id="civilians_yemen",
        label="Civilians — Yemen",
        description="All registered civilian phones in Yemen.",
        count=7840,
        regions=["YEM_SANAA"],
        roles=["civilian"],
        channelsAvailable=["app", "sms", "fallback"],
    ),
    Audience(
        id="doctors_near_sanaa",
        label="Doctors near Sana'a",
        description="On-call medical staff within 50km of Sana'a.",
        count=12,
        regions=["YEM_SANAA"],
        roles=["doctor"],
        channelsAvailable=["sms", "fallback"],
    ),
    Audience(
        id="doctors_global",
        label="Doctors — all regions",
        description="Every registered medical professional in our network.",
        count=187,
        regions=["IRQ_BAGHDAD", "IRQ_MOSUL", "SYR_ALEPPO", "SYR_DAMASCUS", "YEM_SANAA", "LBN_BEIRUT"],
        roles=["doctor"],
        channelsAvailable=["app", "sms", "fallback"],
    ),
    Audience(
        id="ngo_field_staff",
        label="NGO field staff",
        description="Our own field workers and volunteer coordinators.",
        count=64,
        regions=["IRQ_BAGHDAD", "IRQ_MOSUL", "SYR_ALEPPO", "SYR_DAMASCUS", "YEM_SANAA", "LBN_BEIRUT"],
        roles=["ngo"],
        channelsAvailable=["app", "sms", "fallback"],
    ),
    Audience(
        id="pharmacies_open",
        label="Pharmacies (open today)",
        description="Pharmacies confirmed open in the last 24h.",
        count=23,
        regions=["IRQ_BAGHDAD", "SYR_ALEPPO", "SYR_DAMASCUS", "YEM_SANAA"],
        roles=["pharmacy"],
        channelsAvailable=["sms", "fallback"],
    ),
]


def get(audience_id: str) -> Audience | None:
    return next((a for a in AUDIENCES if a.id == audience_id), None)
