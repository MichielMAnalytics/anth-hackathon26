from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

Category = Literal["missing_person", "resource_shortage", "medical", "safety", "other"]
Severity = Literal["low", "medium", "high", "critical"]


class Extracted(BaseModel):
    personRef: str | None = None
    location: str | None = None
    distress: bool | None = None
    needs: list[str] = Field(default_factory=list)


class Message(BaseModel):
    messageId: str
    incidentId: str
    sender: str = Field(alias="from")
    body: str
    ts: datetime
    geohash: str | None = None
    extracted: Extracted | None = None

    model_config = {"populate_by_name": True}


class Incident(BaseModel):
    id: str
    category: Category
    title: str
    severity: Severity
    details: dict[str, Any] = Field(default_factory=dict)
    messageCount: int = 0
    lastActivity: datetime | None = None


class IncomingMessage(BaseModel):
    sender: str = Field(alias="from")
    body: str
    ts: datetime
    geohash: str | None = None
    extracted: Extracted | None = None

    model_config = {"populate_by_name": True}


class IncomingIncident(BaseModel):
    id: str
    category: Category
    title: str
    severity: Severity
    details: dict[str, Any] = Field(default_factory=dict)


class IngestEvent(BaseModel):
    messageId: str
    incident: IncomingIncident
    message: IncomingMessage


class StreamEvent(BaseModel):
    type: Literal["message", "incident_upserted"]
    incident: Incident
    message: Message | None = None


class AlertPayload(BaseModel):
    incidentId: str
    name: str
    photoUrl: str | None = None
    lastSeenLocation: str | None = None
    description: str | None = None
