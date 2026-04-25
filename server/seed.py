"""Procedural seed generator.

Produces ~150 realistic civilian messages per incident, spread over the last
several hours, with varied phone numbers, locations, needs, distress flags
and free-text bodies. Used for demos so the dashboard, timeline, and map
all show meaningful activity.
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from .schemas import IngestEvent
from .store import store


# ---------- helpers ----------

def _phone(rng: random.Random, country: str = "iraq") -> str:
    prefixes = {
        "iraq": "+9647",
        "syria": "+9639",
        "yemen": "+9677",
        "lebanon": "+9617",
    }
    base = prefixes.get(country, "+9647")
    return base + "".join(str(rng.randint(0, 9)) for _ in range(8))


def _country_for(region: str) -> str:
    if region.startswith("IRQ"): return "iraq"
    if region.startswith("SYR"): return "syria"
    if region.startswith("YEM"): return "yemen"
    if region.startswith("LBN"): return "lebanon"
    return "iraq"


def _jitter(base: tuple[float, float], rng: random.Random, scale_km: float = 4.0):
    """Jitter coordinates within ~scale_km kilometres."""
    # ~111km per degree latitude; longitude varies but close enough for demo
    dlat = rng.gauss(0, 1) * (scale_km / 111.0)
    dlon = rng.gauss(0, 1) * (scale_km / 90.0)
    return base[0] + dlat, base[1] + dlon


def _ts_iso(minutes_ago: float) -> str:
    return (datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)).isoformat()


# ---------- per-incident generators ----------

@dataclass
class IncidentSpec:
    id: str
    category: str
    title: str
    severity: str
    region: str
    base_coord: tuple[float, float]
    details: dict
    landmarks: list[str]


def _diala_messages(rng: random.Random) -> list[tuple[str, dict, list[str], list[str], float]]:
    """Returns list of (body, extracted_overrides, possible_landmarks, needs, distress_prob)."""
    return [
        ("My daughter Diala is missing! 7 years old, red dress, blue backpack. Please help.",
         {"personRef": "diala"}, [], [], 0.95),
        ("Saw a small girl in a red dress walking south near {loc} about an hour ago. Maybe 6 or 7?",
         {"personRef": "diala"}, ["the post office", "the bakery", "Block 14", "the school"], [], 0.05),
        ("She was crying. I gave her water but she ran when the shelling started.",
         {"personRef": "diala"}, ["near the mosque"], ["adult escort"], 0.85),
        ("Possible sighting near {loc}. Small girl alone, red clothes.",
         {"personRef": "diala"}, ["the school playground in Block 14", "the river crossing", "the empty market"], [], 0.1),
        ("Asking everyone in our building. Will share photos with the children's group.",
         {}, [], [], 0.0),
        ("Has anyone heard from her family? They live near Al-Mutanabbi street.",
         {"personRef": "diala"}, [], [], 0.2),
        ("I work at the bakery — she came by yesterday afternoon with her mother.",
         {"personRef": "diala", "location": "the bakery"}, [], [], 0.0),
        ("Telling my grandchildren to keep watch. So sad.",
         {}, [], [], 0.0),
        ("Last seen wearing red shoes too. About this tall (showing waist height).",
         {"personRef": "diala"}, [], [], 0.3),
        ("Contact the local council? They have volunteers searching block by block.",
         {}, [], [], 0.0),
        ("My son says he saw her near {loc} this morning. He is 9 and reliable.",
         {"personRef": "diala"}, ["the abandoned petrol station", "the bus stop", "the mosque"], [], 0.4),
        ("Please share a photo. Many of us cannot read but we can recognize her.",
         {}, [], [], 0.1),
        ("There was a woman crying at the police checkpoint about a missing girl. May be the same family.",
         {"personRef": "diala"}, ["the checkpoint"], [], 0.7),
        ("If anyone is heading toward Block 12 please ask the shopkeepers.",
         {}, [], [], 0.0),
        ("I'm a teacher — sending her photo to all my students' families.",
         {}, [], [], 0.0),
    ]


def _water_messages(rng: random.Random) -> list:
    return [
        ("There is no water here at all. Three days now. Children are getting sick.",
         {}, ["Block 4", "Block 4 north", "the north sector"], ["water"], 0.95),
        ("Pipe is dry on our street too. About 40 families affected.",
         {}, ["Block 4 north", "Sharia 9"], ["water"], 0.5),
        ("We are boiling rainwater. Need clean water urgently — especially for the babies.",
         {}, ["Block 4"], ["water", "baby formula"], 0.9),
        ("The standpipe at {loc} stopped working last night. Long queues forming.",
         {}, ["the school", "the mosque", "the clinic", "the market square"], ["water"], 0.3),
        ("Confirming: no water in our building since Saturday. Storage tank empty.",
         {}, ["Block 4"], ["water"], 0.4),
        ("Elderly neighbour fainted from dehydration. Got her to the clinic.",
         {}, [], ["water", "medical"], 0.95),
        ("Anyone has spare drinking water? Trade for bread.",
         {}, [], ["water"], 0.6),
        ("Truck deliveries stopped after the road was damaged. Fix this please.",
         {}, ["the main road"], ["water"], 0.5),
        ("My toddler has diarrhea — I think it's the stored water. We need clean.",
         {}, [], ["water", "medical"], 0.9),
        ("Heard the municipality is trucking water tomorrow. Can someone confirm?",
         {}, [], [], 0.2),
        ("Our well is contaminated. Three children sick this week.",
         {}, ["the well"], ["water", "medical"], 0.9),
        ("If anyone in Block 4 has a working pump please share location.",
         {}, ["Block 4"], ["water"], 0.4),
        ("Cooking oil for water trade — same building.",
         {}, [], ["water"], 0.2),
        ("The pumping station was hit. That's why pressure is gone.",
         {}, ["the pumping station"], ["water"], 0.3),
    ]


def _insulin_messages(rng: random.Random) -> list:
    return [
        ("My father has diabetes. Ran out of insulin two days ago. He is getting confused.",
         {"personRef": "karim"}, [], ["insulin"], 0.95),
        ("Pharmacy on 9th street might still have stock. They were open yesterday.",
         {}, ["9th street pharmacy"], [], 0.0),
        ("My mother has type 1 diabetes too. We are sharing the last vial. Need help.",
         {}, [], ["insulin"], 0.95),
        ("The clinic near {loc} closed last week. Where can we go?",
         {}, ["Sector 7", "the closed clinic", "the market"], ["insulin", "medical"], 0.7),
        ("Posting on this network — anyone with rapid-acting insulin?",
         {}, [], ["insulin"], 0.6),
        ("I am a nurse, can help administer if someone has supply. Reach me here.",
         {}, [], ["medical"], 0.0),
        ("The pharmacy in {loc} just got a delivery. Limited stock.",
         {}, ["Sector 6", "Sector 7", "Sector 8"], [], 0.0),
        ("Diabetic neighbour is unconscious. Please send help, fast.",
         {}, [], ["insulin", "medical"], 0.99),
        ("We tried the hospital but they say no insulin until Thursday.",
         {}, [], ["insulin"], 0.6),
        ("Trying to keep his blood sugar low with food only. Not working.",
         {}, [], ["insulin"], 0.7),
        ("Two more diabetics on this street out of meds.",
         {}, [], ["insulin"], 0.6),
        ("Doctor friend says shared insulin pens are dangerous. Please send proper supply.",
         {}, [], ["insulin"], 0.4),
    ]


def _building_messages(rng: random.Random) -> list:
    return [
        ("The building at 12 Najaf St took damage last night. We hear someone calling from the second floor.",
         {}, ["12 Najaf St", "Block 2"], [], 0.95),
        ("Heard the explosion around 11pm. Whole block shook.",
         {}, ["Block 2"], [], 0.7),
        ("Family on the third floor unaccounted for. Mother and two children.",
         {}, ["12 Najaf St"], [], 0.9),
        ("Civil defence team needs heavier equipment. Concrete slabs blocking access.",
         {}, ["12 Najaf St"], [], 0.6),
        ("Voices have stopped. We are still digging.",
         {}, ["12 Najaf St"], [], 0.95),
        ("My uncle lives next door — he is shaken but okay.",
         {}, ["Block 2"], [], 0.3),
        ("Power lines down on the street. Be careful.",
         {}, ["Block 2"], [], 0.2),
        ("Neighbours organising shifts to monitor. Need water and food for diggers.",
         {}, ["Block 2"], ["water", "food"], 0.4),
        ("Two casualties brought out around 4am. Both stable.",
         {}, [], ["medical"], 0.5),
        ("The structure might collapse further. Please advise residents to leave.",
         {}, ["12 Najaf St"], [], 0.7),
        ("Anyone with construction experience please come to {loc}.",
         {}, ["12 Najaf St", "the rubble"], [], 0.2),
        ("Heard the family on second floor was rescued. Thank god.",
         {}, ["12 Najaf St"], [], 0.0),
    ]


# ---------- incident specs ----------

INCIDENT_SPECS: list[tuple[IncidentSpec, callable]] = [
    (IncidentSpec(
        id="inc-diala",
        category="missing_person",
        title="Lost: Diala (girl, ~7)",
        severity="critical",
        region="IRQ_MOSUL",
        base_coord=(36.3489, 43.1577),
        details={
            "name": "Diala Haddad",
            "ageRange": "6-8",
            "photoUrl": "https://api.dicebear.com/9.x/avataaars/svg?seed=diala",
            "lastSeenAt": _ts_iso(180),
            "lastSeenLocation": "Bakery on Al-Mutanabbi St, Block 12",
            "description": "Brown hair, red dress, small blue backpack. Doesn't speak English.",
            "status": "open",
        },
        landmarks=["bakery", "Block 12", "the post office", "the school", "Al-Mutanabbi St"],
    ), _diala_messages),

    (IncidentSpec(
        id="inc-water-b4",
        category="resource_shortage",
        title="No water — Block 4",
        severity="high",
        region="SYR_ALEPPO",
        base_coord=(36.2021, 37.1343),
        details={
            "resource": "water",
            "location": "Block 4, north sector",
            "reporterCount": 6,
            "severity": "high",
        },
        landmarks=["Block 4", "the north sector", "Sharia 9"],
    ), _water_messages),

    (IncidentSpec(
        id="inc-insulin-s7",
        category="medical",
        title="Insulin needed — Sector 7",
        severity="high",
        region="YEM_SANAA",
        base_coord=(15.3694, 44.1910),
        details={
            "condition": "Type 1 diabetes",
            "medicationNeeded": "Insulin (rapid-acting)",
            "location": "Sector 7, near the closed clinic",
            "patientName": "Mr. Karim, 58",
            "urgency": "within 24h",
        },
        landmarks=["Sector 7", "9th street", "the closed clinic"],
    ), _insulin_messages),

    (IncidentSpec(
        id="inc-safety-b2",
        category="safety",
        title="Building damage — Block 2",
        severity="medium",
        region="IRQ_BAGHDAD",
        base_coord=(33.3152, 44.3661),
        details={
            "threat": "Partially collapsed apartment building, residents unaccounted for",
            "location": "12 Najaf St, Block 2",
            "ongoing": False,
        },
        landmarks=["12 Najaf St", "Block 2"],
    ), _building_messages),
]


# ---------- generation ----------

# Total messages per incident. Spread is realistic: a burst when the incident
# starts, sporadic afterwards, and a tail of fresh sightings/reports.
MESSAGES_PER_INCIDENT = 150
WINDOW_HOURS = 8.0  # incidents are 8h old


def _build_one_event(spec: IncidentSpec, template_pool: list, rng: random.Random) -> dict:
    body_template, ex_overrides, landmark_options, needs, distress_prob = rng.choice(template_pool)

    # pick a landmark when {loc} placeholder present
    if "{loc}" in body_template:
        landmark = rng.choice(landmark_options or spec.landmarks)
        body = body_template.replace("{loc}", landmark)
    else:
        body = body_template
        landmark = None

    # bias timestamp distribution: half of messages in last hour, rest spread
    if rng.random() < 0.5:
        minutes_ago = rng.uniform(0, 60)
    else:
        minutes_ago = rng.uniform(60, WINDOW_HOURS * 60)

    lat, lon = _jitter(spec.base_coord, rng)
    sender = _phone(rng, _country_for(spec.region))

    extracted = {
        "needs": needs,
        "distress": rng.random() < distress_prob,
    }
    if landmark:
        extracted["location"] = landmark
    extracted.update(ex_overrides)

    return {
        "messageId": str(uuid4()),
        "incident": {
            "id": spec.id,
            "category": spec.category,
            "title": spec.title,
            "severity": spec.severity,
            "region": spec.region,
            "lat": spec.base_coord[0],
            "lon": spec.base_coord[1],
            "details": spec.details,
        },
        "message": {
            "from": sender,
            "body": body,
            "ts": _ts_iso(minutes_ago),
            "lat": lat,
            "lon": lon,
            "extracted": extracted,
        },
    }


def generate_seed_events(seed: int = 42) -> list[dict]:
    rng = random.Random(seed)
    events: list[dict] = []
    for spec, gen in INCIDENT_SPECS:
        templates = gen(rng)
        for _ in range(MESSAGES_PER_INCIDENT):
            events.append(_build_one_event(spec, templates, rng))
    # sort by timestamp so the store sees them in chronological order
    events.sort(key=lambda e: e["message"]["ts"])
    return events


def load_seed() -> int:
    store.reset()
    events = generate_seed_events()
    for raw in events:
        store.upsert(IngestEvent.model_validate(raw))
    return len(events)
