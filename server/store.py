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

    def append_outbound(self, message: Message) -> None:
        with self._lock:
            inc = self._incidents.get(message.incidentId)
            if inc is None:
                return
            self._messages[message.incidentId].append(message)
            inc.messageCount += 1
            inc.lastActivity = message.ts

    def timeline(
        self, region: Region, minutes: int = 60, bucket_seconds: int = 60
    ) -> list[tuple[datetime, int]]:
        """Per-bucket message count for the last `minutes`. Returns list of (bucket_start, count)."""
        now = datetime.now(timezone.utc)
        # align to bucket boundary
        start = now - timedelta(minutes=minutes)
        n_buckets = max(1, (minutes * 60) // bucket_seconds)
        # compute bucket index function
        def bucket_index(t: datetime) -> int:
            delta = (t - start).total_seconds()
            return int(delta // bucket_seconds)

        counts = [0] * n_buckets
        with self._lock:
            ts_list = list(self._region_ts.get(region, ()))
        for t in ts_list:
            if t < start or t > now:
                continue
            i = bucket_index(t)
            if 0 <= i < n_buckets:
                counts[i] += 1

        return [
            (start + timedelta(seconds=i * bucket_seconds), counts[i])
            for i in range(n_buckets)
        ]

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
