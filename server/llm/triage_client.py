import hashlib
import os
from typing import Optional


def hash_to_vec(body: str) -> list[float]:
    """Deterministic 512-float embedding from sha256 of the body."""
    seed = body.encode("utf-8")
    floats: list[float] = []
    i = 0
    while len(floats) < 512:
        digest = hashlib.sha256(seed + i.to_bytes(4, "big")).digest()
        for byte in digest:
            floats.append((byte / 127.5) - 1.0)
            if len(floats) == 512:
                break
        i += 1
    return floats


def _stub_classify(body: str, alert_summary: Optional[str]) -> dict:
    normalized = body.strip().lower()
    classification = "sighting" if len(normalized) >= 10 else "noise"
    return {
        "classification": classification,
        "geohash6": None,
        "geohash_source": "alert_region",
        "confidence": 0.75 if classification == "sighting" else 0.4,
        "language": "en",
        "dedup_hash": hashlib.sha256(normalized.encode()).hexdigest()[:16],
    }


async def classify(body: str, alert_summary: Optional[str]) -> dict:
    """Classify an inbound message. Stub if ANTHROPIC_API_KEY is unset."""
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return _stub_classify(body, alert_summary)

    import anthropic

    client = anthropic.AsyncAnthropic(api_key=api_key)
    system = (
        "You are a triage classifier for civilian messages reaching an NGO operating "
        "in a humanitarian crisis. The NGO works four kinds of cases:\n"
        "  1. missing_person  — people reported missing, last-seen reports, sightings of missing persons\n"
        "  2. medical         — injuries, illness, medical evacuation, requests for medics or supplies\n"
        "  3. resource_shortage — water, food, fuel, shelter, baby formula, blankets, etc.\n"
        "  4. safety          — fires, unsafe routes, ongoing incidents, security threats, evacuation needs\n\n"
        "PRIMARY RULE: if the message could plausibly be promoted into ANY of the four "
        "case categories above, classify it as `sighting`. This is by far the most common "
        "category. Examples that are ALL `sighting`:\n"
        "  • 'I NEED A MEDIC RIGHT NOW' (medical)\n"
        "  • 'we have no water in district 4 since yesterday' (resource_shortage)\n"
        "  • 'fire on the south road, avoid' (safety)\n"
        "  • 'my brother is missing, last seen at the bus station' (missing_person)\n"
        "  • 'I saw Maryam near the central market' (missing_person)\n"
        "  • 'ALERT, my neighbour is missing' (missing_person — the word ALERT is the writer "
        "    raising one, NOT acknowledging a prior NGO alert)\n\n"
        "Other categories — use sparingly:\n"
        "  • question — the user is ONLY asking the NGO for information / status and reports nothing new "
        "    (e.g. 'any updates on Maryam?'). If they're also reporting something, it's a `sighting`.\n"
        "  • ack — short acknowledgement of an NGO-issued alert the user previously received. "
        "    Words like 'ALERT' or 'help' written BY the user do NOT make a message an ack — those are "
        "    sightings. True acks look like: 'received', 'got it, thanks', 'understood', 'on my way'.\n"
        "  • noise — actually off-topic, automated, gibberish, or unrelated to humanitarian work. "
        "    A short message that names a person, a place, or a need is NEVER noise.\n"
        "  • bad_actor — spam, abuse, or appears intentionally false.\n\n"
        "When in doubt between `sighting` and any other label, choose `sighting`. The cost of "
        "missing a real distress signal far outweighs the cost of an operator glancing at one extra "
        "message.\n\n"
        "Extract a 6-character geohash if a location is mentionable, detect language, and produce a "
        "stable dedup_hash from the normalized body. Return ONLY the structured tool call."
    )
    context = f"\n\nAlert context: {alert_summary}" if alert_summary else ""

    tool = {
        "name": "classify",
        "description": "Classify an inbound civilian distress / report message across all NGO case categories.",
        "input_schema": {
            "type": "object",
            "properties": {
                "classification": {"type": "string", "enum": ["sighting", "question", "ack", "noise", "bad_actor"]},
                "geohash6": {"type": ["string", "null"]},
                "geohash_source": {"type": "string", "enum": ["app_gps", "registered_home", "alert_region", "body_extraction"]},
                "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                "language": {"type": "string"},
                "dedup_hash": {"type": "string"},
            },
            "required": ["classification", "geohash6", "geohash_source", "confidence", "language", "dedup_hash"],
        },
    }

    resp = await client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=256,
        system=system,
        messages=[{"role": "user", "content": f"Message: {body}{context}"}],
        tools=[tool],
        tool_choice={"type": "tool", "name": "classify"},
    )
    for block in resp.content:
        if block.type == "tool_use" and block.name == "classify":
            return block.input
    return _stub_classify(body, alert_summary)
