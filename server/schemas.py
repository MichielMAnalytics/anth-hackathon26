from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

Category = Literal["missing_person", "resource_shortage", "medical", "safety", "other"]
Severity = Literal["low", "medium", "high", "critical"]
Region = Literal[
    "IRQ_BAGHDAD",
    "IRQ_MOSUL",
    "SYR_ALEPPO",
    "SYR_DAMASCUS",
    "YEM_SANAA",
    "LBN_BEIRUT",
]
Channel = Literal["app", "sms", "fallback"]


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
    lat: float | None = None
    lon: float | None = None
    extracted: Extracted | None = None
    outbound: bool = False
    via: str | None = None  # bitchat | sms | app

    model_config = {"populate_by_name": True}


class Incident(BaseModel):
    id: str
    category: Category
    title: str
    severity: Severity
    region: Region
    lat: float | None = None
    lon: float | None = None
    details: dict[str, Any] = Field(default_factory=dict)
    messageCount: int = 0
    lastActivity: datetime | None = None


class IncomingMessage(BaseModel):
    sender: str = Field(alias="from")
    body: str
    ts: datetime
    geohash: str | None = None
    lat: float | None = None
    lon: float | None = None
    extracted: Extracted | None = None

    model_config = {"populate_by_name": True}


class IncomingIncident(BaseModel):
    id: str
    category: Category
    title: str
    severity: Severity
    region: Region
    lat: float | None = None
    lon: float | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class IngestEvent(BaseModel):
    messageId: str
    incident: IncomingIncident
    message: IncomingMessage


class StreamEvent(BaseModel):
    type: Literal["message", "incident_upserted"]
    incident: Incident
    message: Message | None = None


class Audience(BaseModel):
    id: str
    label: str
    description: str
    count: int
    regions: list[Region]
    roles: list[str] = Field(default_factory=list)
    channelsAvailable: list[Channel]


class RegionStats(BaseModel):
    region: Region
    label: str
    lat: float
    lon: float
    reachable: int
    incidentCount: int
    messageCount: int
    msgsPerMin: float
    baselineMsgsPerMin: float
    anomaly: bool


class BroadcastPayload(BaseModel):
    audienceId: str
    channels: Channel = "fallback"
    region: Region | None = None
    body: str
    incidentId: str | None = None
    attachments: dict[str, Any] = Field(default_factory=dict)


# legacy alias retained for backward compat
AlertPayload = BroadcastPayload


class BroadcastAck(BaseModel):
    ok: bool = True
    queued: int
    batches: int
    etaSeconds: int
    channels: list[str]
    audienceLabel: str
    note: str


class OperatorMessage(BaseModel):
    body: str
    via: Channel = "fallback"
    audienceId: str | None = None  # if set, also schedules a broadcast
