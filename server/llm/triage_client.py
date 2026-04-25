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
        "You are a triage classifier for civilian sighting reports for a missing-person "
        "alert system. Classify the message, extract a 6-character geohash if possible, "
        "detect language, and produce a stable dedup_hash from the normalized body. "
        "Return ONLY the structured tool call."
    )
    context = f"\n\nAlert context: {alert_summary}" if alert_summary else ""

    tool = {
        "name": "classify",
        "description": "Classify an inbound civilian sighting message.",
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
