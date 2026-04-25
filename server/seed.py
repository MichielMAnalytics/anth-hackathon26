from datetime import datetime, timedelta, timezone
from uuid import uuid4

from .schemas import IngestEvent
from .store import store

NOW = datetime.now(timezone.utc)


def _ts(minutes_ago: int) -> str:
    return (NOW - timedelta(minutes=minutes_ago)).isoformat()


SEED_EVENTS: list[dict] = [
    # ---- Missing person: Diala ----
    {
        "messageId": str(uuid4()),
        "incident": {
            "id": "inc-diala",
            "category": "missing_person",
            "title": "Lost: Diala (girl, ~7)",
            "severity": "critical",
            "details": {
                "name": "Diala Haddad",
                "ageRange": "6-8",
                "photoUrl": "https://api.dicebear.com/9.x/avataaars/svg?seed=diala",
                "lastSeenAt": _ts(180),
                "lastSeenLocation": "Bakery on Al-Mutanabbi St, Block 12",
                "description": "Brown hair, wearing a red dress, carrying a small blue backpack. Doesn't speak English.",
                "status": "open",
            },
        },
        "message": {
            "from": "+9647712345678",
            "body": "My daughter Diala is missing. Last seen near the bakery on Al-Mutanabbi street. Please help.",
            "ts": _ts(180),
            "extracted": {"personRef": "diala", "distress": True, "needs": []},
        },
    },
    {
        "messageId": str(uuid4()),
        "incident": {
            "id": "inc-diala",
            "category": "missing_person",
            "title": "Lost: Diala (girl, ~7)",
            "severity": "critical",
            "details": {
                "name": "Diala Haddad",
                "ageRange": "6-8",
                "photoUrl": "https://api.dicebear.com/9.x/avataaars/svg?seed=diala",
                "lastSeenAt": _ts(180),
                "lastSeenLocation": "Bakery on Al-Mutanabbi St, Block 12",
                "description": "Brown hair, wearing a red dress, carrying a small blue backpack.",
                "status": "open",
            },
        },
        "message": {
            "from": "+9647798765432",
            "body": "I saw a girl in a red dress walking south past the post office about an hour ago. Maybe 6 or 7 years old?",
            "ts": _ts(95),
            "geohash": "sy3kzd",
            "extracted": {
                "personRef": "diala",
                "location": "post office, walking south",
                "distress": False,
            },
        },
    },
    {
        "messageId": str(uuid4()),
        "incident": {
            "id": "inc-diala",
            "category": "missing_person",
            "title": "Lost: Diala (girl, ~7)",
            "severity": "critical",
            "details": {
                "name": "Diala Haddad",
                "ageRange": "6-8",
                "photoUrl": "https://api.dicebear.com/9.x/avataaars/svg?seed=diala",
                "lastSeenAt": _ts(180),
                "lastSeenLocation": "Bakery on Al-Mutanabbi St, Block 12",
                "description": "Brown hair, wearing a red dress, carrying a small blue backpack.",
                "status": "open",
            },
        },
        "message": {
            "from": "+9647755123456",
            "body": "She was crying and asking for her mother. I gave her water but she ran off when the shelling started.",
            "ts": _ts(60),
            "geohash": "sy3kze",
            "extracted": {
                "personRef": "diala",
                "location": "near post office",
                "distress": True,
                "needs": ["adult escort"],
            },
        },
    },
    {
        "messageId": str(uuid4()),
        "incident": {
            "id": "inc-diala",
            "category": "missing_person",
            "title": "Lost: Diala (girl, ~7)",
            "severity": "critical",
            "details": {
                "name": "Diala Haddad",
                "ageRange": "6-8",
                "photoUrl": "https://api.dicebear.com/9.x/avataaars/svg?seed=diala",
                "lastSeenAt": _ts(180),
                "lastSeenLocation": "Bakery on Al-Mutanabbi St, Block 12",
                "description": "Brown hair, wearing a red dress, carrying a small blue backpack.",
                "status": "open",
            },
        },
        "message": {
            "from": "+9647700998877",
            "body": "Possible sighting near the school playground in Block 14. Small girl alone, red clothes.",
            "ts": _ts(20),
            "geohash": "sy3kzm",
            "extracted": {
                "personRef": "diala",
                "location": "school playground, Block 14",
            },
        },
    },
    # ---- Resource shortage: water ----
    {
        "messageId": str(uuid4()),
        "incident": {
            "id": "inc-water-b4",
            "category": "resource_shortage",
            "title": "No water — Block 4",
            "severity": "high",
            "details": {
                "resource": "water",
                "location": "Block 4, north sector",
                "reporterCount": 6,
                "severity": "high",
            },
        },
        "message": {
            "from": "+9647722334455",
            "body": "There is no water here at all. Three days now. Children are getting sick.",
            "ts": _ts(420),
            "extracted": {"location": "Block 4", "needs": ["water"], "distress": True},
        },
    },
    {
        "messageId": str(uuid4()),
        "incident": {
            "id": "inc-water-b4",
            "category": "resource_shortage",
            "title": "No water — Block 4",
            "severity": "high",
            "details": {
                "resource": "water",
                "location": "Block 4, north sector",
                "reporterCount": 6,
                "severity": "high",
            },
        },
        "message": {
            "from": "+9647766554433",
            "body": "Confirming, the pipe is dry on our street too. About 40 families.",
            "ts": _ts(310),
            "extracted": {"location": "Block 4 north", "needs": ["water"]},
        },
    },
    {
        "messageId": str(uuid4()),
        "incident": {
            "id": "inc-water-b4",
            "category": "resource_shortage",
            "title": "No water — Block 4",
            "severity": "high",
            "details": {
                "resource": "water",
                "location": "Block 4, north sector",
                "reporterCount": 6,
                "severity": "high",
            },
        },
        "message": {
            "from": "+9647711223344",
            "body": "We are boiling rainwater. Need clean water urgently, especially for the babies.",
            "ts": _ts(140),
            "extracted": {"needs": ["water", "baby formula"], "distress": True},
        },
    },
    # ---- Medical: insulin ----
    {
        "messageId": str(uuid4()),
        "incident": {
            "id": "inc-insulin-s7",
            "category": "medical",
            "title": "Insulin needed — Sector 7",
            "severity": "high",
            "details": {
                "condition": "Type 1 diabetes",
                "medicationNeeded": "Insulin (rapid-acting)",
                "location": "Sector 7, near the closed clinic",
                "patientName": "Mr. Karim, 58",
                "urgency": "within 24h",
            },
        },
        "message": {
            "from": "+9647788776655",
            "body": "My father has diabetes. We ran out of insulin two days ago. He is getting confused.",
            "ts": _ts(240),
            "extracted": {
                "personRef": "karim",
                "needs": ["insulin"],
                "distress": True,
            },
        },
    },
    {
        "messageId": str(uuid4()),
        "incident": {
            "id": "inc-insulin-s7",
            "category": "medical",
            "title": "Insulin needed — Sector 7",
            "severity": "high",
            "details": {
                "condition": "Type 1 diabetes",
                "medicationNeeded": "Insulin (rapid-acting)",
                "location": "Sector 7, near the closed clinic",
                "patientName": "Mr. Karim, 58",
                "urgency": "within 24h",
            },
        },
        "message": {
            "from": "+9647733445566",
            "body": "I think the pharmacy on 9th street might still have stock. They were open yesterday.",
            "ts": _ts(120),
            "extracted": {"location": "9th street pharmacy"},
        },
    },
    # ---- Safety ----
    {
        "messageId": str(uuid4()),
        "incident": {
            "id": "inc-safety-b2",
            "category": "safety",
            "title": "Building damage — Block 2",
            "severity": "medium",
            "details": {
                "threat": "Partially collapsed apartment building, residents unaccounted for",
                "location": "12 Najaf St, Block 2",
                "ongoing": False,
            },
        },
        "message": {
            "from": "+9647744556677",
            "body": "The building at 12 Najaf St took damage last night. We can hear someone calling from the second floor.",
            "ts": _ts(35),
            "extracted": {"location": "12 Najaf St", "distress": True},
        },
    },
]


def load_seed() -> int:
    store.reset()
    count = 0
    for raw in SEED_EVENTS:
        event = IngestEvent.model_validate(raw)
        store.upsert(event)
        count += 1
    return count
