from collections import defaultdict
from threading import Lock

from .schemas import Incident, IngestEvent, Message


class Store:
    def __init__(self) -> None:
        self._lock = Lock()
        self._incidents: dict[str, Incident] = {}
        self._messages: dict[str, list[Message]] = defaultdict(list)

    def upsert(self, event: IngestEvent) -> tuple[Incident, Message]:
        with self._lock:
            inc_in = event.incident
            existing = self._incidents.get(inc_in.id)
            incident = Incident(
                id=inc_in.id,
                category=inc_in.category,
                title=inc_in.title,
                severity=inc_in.severity,
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
                extracted=event.message.extracted,
            )
            self._messages[incident.id].append(message)
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

    def reset(self) -> None:
        with self._lock:
            self._incidents.clear()
            self._messages.clear()


store = Store()
