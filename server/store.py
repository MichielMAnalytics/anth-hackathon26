from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from threading import Lock

from .schemas import Incident, IngestEvent, Message, Region


class Store:
    def __init__(self) -> None:
        self._lock = Lock()
        self._incidents: dict[str, Incident] = {}
        self._messages: dict[str, list[Message]] = defaultdict(list)
        # for anomaly detection: ring buffer of message timestamps per region
        self._region_ts: dict[Region, deque[datetime]] = defaultdict(
            lambda: deque(maxlen=2000)
        )

    def upsert(self, event: IngestEvent) -> tuple[Incident, Message]:
        with self._lock:
            inc_in = event.incident
            existing = self._incidents.get(inc_in.id)
            incident = Incident(
                id=inc_in.id,
                category=inc_in.category,
                title=inc_in.title,
                severity=inc_in.severity,
                region=inc_in.region,
                lat=inc_in.lat,
                lon=inc_in.lon,
                details=inc_in.details,
                messageCount=(existing.messageCount if existing else 0) + 1,
                lastActivity=event.message.ts,
            )
            self._incidents[incident.id] = incident

            message = Message(
                messageId=event.messageId,
                incidentId=incident.id,
                **{"from": event.message.sender},
                body=event.message.body,
                ts=event.message.ts,
                geohash=event.message.geohash,
                lat=event.message.lat if event.message.lat is not None else inc_in.lat,
                lon=event.message.lon if event.message.lon is not None else inc_in.lon,
                extracted=event.message.extracted,
            )
            self._messages[incident.id].append(message)
            self._region_ts[inc_in.region].append(event.message.ts)
            return incident, message

    def list_incidents(self) -> list[Incident]:
        with self._lock:
            return list(self._incidents.values())

    def get_incident(self, incident_id: str) -> Incident | None:
        with self._lock:
            return self._incidents.get(incident_id)

    def list_messages(self, incident_id: str) -> list[Message]:
        with self._lock:
            return list(self._messages.get(incident_id, []))

    def msgs_per_minute(self, region: Region, window_seconds: int = 60) -> float:
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=window_seconds)
        with self._lock:
            ts = self._region_ts.get(region, ())
            recent = sum(1 for t in ts if t >= cutoff)
        return recent * (60.0 / window_seconds)

    def baseline_msgs_per_minute(self, region: Region) -> float:
        # crude baseline: msgs/min averaged over last 30 min, excluding the last 3 min
        now = datetime.now(timezone.utc)
        window_start = now - timedelta(minutes=30)
        recent_cutoff = now - timedelta(minutes=3)
        with self._lock:
            ts = self._region_ts.get(region, ())
            count = sum(1 for t in ts if window_start <= t <= recent_cutoff)
        return count / 27.0  # 30 - 3 minutes

    def reset(self) -> None:
        with self._lock:
            self._incidents.clear()
            self._messages.clear()
            self._region_ts.clear()


store = Store()
