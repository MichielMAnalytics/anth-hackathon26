"""Tolerant TLV decoders for the four inner amber payload types.

Each payload uses a 1-byte type + 1-byte length + value layout (max 255
bytes per field). The decoder skips unknown TLV types so either side can
add fields without breaking older clients — see the iOS `AmberPackets`
docstring for the same convention on the encode side.

Mirrors:
  - mobileapp/src/bitchat/Models/AmberPackets.swift  (Sighting / LocationReport / GeneralMessage)
  - ProfileUpdate is forward-declared here; the iOS side doesn't yet
    emit it over DTN (profile changes only flow via HTTP today). Field
    layout is provisional; revise when iOS adds the encoder.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from enum import IntEnum
from typing import Iterator, Optional


def _iter_tlv(data: bytes) -> Iterator[tuple[int, bytes]]:
    """Yield (type, value) pairs from a TLV byte stream. Unknown types
    are still yielded — caller decides what to do.

    Truncated trailing fields are silently ignored (tolerant decode).
    """
    off = 0
    while off + 2 <= len(data):
        t = data[off]
        ln = data[off + 1]
        off += 2
        if off + ln > len(data):
            return
        yield t, data[off : off + ln]
        off += ln


def _utf8(data: bytes) -> Optional[str]:
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return None


# ---------------------------------------------------------------------------
# SightingPayload (0x21)
# ---------------------------------------------------------------------------


@dataclass
class SightingPayload:
    case_id: str
    client_msg_id: str  # idempotency / dedup at hub
    free_text: str
    observed_at: int  # unix seconds (uint32)
    location_lat: Optional[float] = None
    location_lng: Optional[float] = None

    class _T(IntEnum):
        CASE_ID = 0x01
        CLIENT_MSG_ID = 0x02
        FREE_TEXT = 0x03
        OBSERVED_AT = 0x04
        LOCATION_LAT = 0x05
        LOCATION_LNG = 0x06

    def encode(self) -> bytes:
        out = bytearray()
        for tlv_type, value in (
            (self._T.CASE_ID, self.case_id.encode("utf-8")),
            (self._T.CLIENT_MSG_ID, self.client_msg_id.encode("utf-8")),
            (self._T.FREE_TEXT, self.free_text.encode("utf-8")),
        ):
            if len(value) > 255:
                raise ValueError(f"{tlv_type.name} too long ({len(value)} > 255)")
            out += bytes([tlv_type, len(value)]) + value
        out += bytes([self._T.OBSERVED_AT, 4]) + struct.pack("!I", self.observed_at)
        if self.location_lat is not None:
            out += bytes([self._T.LOCATION_LAT, 8]) + struct.pack("!d", self.location_lat)
        if self.location_lng is not None:
            out += bytes([self._T.LOCATION_LNG, 8]) + struct.pack("!d", self.location_lng)
        return bytes(out)

    @classmethod
    def decode(cls, data: bytes) -> Optional["SightingPayload"]:
        case_id: Optional[str] = None
        client_msg_id: Optional[str] = None
        free_text: Optional[str] = None
        observed_at: Optional[int] = None
        lat: Optional[float] = None
        lng: Optional[float] = None
        for t, v in _iter_tlv(data):
            if t == cls._T.CASE_ID:
                case_id = _utf8(v)
            elif t == cls._T.CLIENT_MSG_ID:
                client_msg_id = _utf8(v)
            elif t == cls._T.FREE_TEXT:
                free_text = _utf8(v)
            elif t == cls._T.OBSERVED_AT and len(v) == 4:
                (observed_at,) = struct.unpack("!I", v)
            elif t == cls._T.LOCATION_LAT and len(v) == 8:
                (lat,) = struct.unpack("!d", v)
            elif t == cls._T.LOCATION_LNG and len(v) == 8:
                (lng,) = struct.unpack("!d", v)
            # else: unknown TLV, skip
        if case_id is None or client_msg_id is None or free_text is None or observed_at is None:
            return None
        return cls(
            case_id=case_id,
            client_msg_id=client_msg_id,
            free_text=free_text,
            observed_at=observed_at,
            location_lat=lat,
            location_lng=lng,
        )


# ---------------------------------------------------------------------------
# LocationReportPayload (0x22)
# ---------------------------------------------------------------------------


class Safety(IntEnum):
    SAFE = 0x01
    UNSAFE = 0x02


@dataclass
class LocationReportPayload:
    client_msg_id: str
    lat: float
    lng: float
    safety: int  # Safety enum value
    note: str  # may be empty
    observed_at: int  # unix seconds (uint32)

    class _T(IntEnum):
        CLIENT_MSG_ID = 0x01
        LAT = 0x02
        LNG = 0x03
        SAFETY = 0x04
        NOTE = 0x05
        OBSERVED_AT = 0x06

    def encode(self) -> bytes:
        out = bytearray()
        cmid = self.client_msg_id.encode("utf-8")
        if len(cmid) > 255:
            raise ValueError("client_msg_id too long")
        out += bytes([self._T.CLIENT_MSG_ID, len(cmid)]) + cmid
        out += bytes([self._T.LAT, 8]) + struct.pack("!d", self.lat)
        out += bytes([self._T.LNG, 8]) + struct.pack("!d", self.lng)
        out += bytes([self._T.SAFETY, 1, self.safety])
        note = self.note.encode("utf-8")
        if len(note) > 255:
            raise ValueError("note too long")
        out += bytes([self._T.NOTE, len(note)]) + note
        out += bytes([self._T.OBSERVED_AT, 4]) + struct.pack("!I", self.observed_at)
        return bytes(out)

    @classmethod
    def decode(cls, data: bytes) -> Optional["LocationReportPayload"]:
        client_msg_id: Optional[str] = None
        lat: Optional[float] = None
        lng: Optional[float] = None
        safety: Optional[int] = None
        note: Optional[str] = ""
        observed_at: Optional[int] = None
        for t, v in _iter_tlv(data):
            if t == cls._T.CLIENT_MSG_ID:
                client_msg_id = _utf8(v)
            elif t == cls._T.LAT and len(v) == 8:
                (lat,) = struct.unpack("!d", v)
            elif t == cls._T.LNG and len(v) == 8:
                (lng,) = struct.unpack("!d", v)
            elif t == cls._T.SAFETY and len(v) == 1:
                safety = v[0]
            elif t == cls._T.NOTE:
                note = _utf8(v) or ""
            elif t == cls._T.OBSERVED_AT and len(v) == 4:
                (observed_at,) = struct.unpack("!I", v)
        if (
            client_msg_id is None
            or lat is None
            or lng is None
            or safety is None
            or observed_at is None
        ):
            return None
        return cls(
            client_msg_id=client_msg_id,
            lat=lat,
            lng=lng,
            safety=safety,
            note=note or "",
            observed_at=observed_at,
        )


# ---------------------------------------------------------------------------
# GeneralMessagePayload (0x23)
# ---------------------------------------------------------------------------


@dataclass
class GeneralMessagePayload:
    client_msg_id: str
    body: str
    sent_at: int  # unix seconds (uint32)

    class _T(IntEnum):
        CLIENT_MSG_ID = 0x01
        BODY = 0x02
        SENT_AT = 0x03

    def encode(self) -> bytes:
        out = bytearray()
        for tlv_type, value in (
            (self._T.CLIENT_MSG_ID, self.client_msg_id.encode("utf-8")),
            (self._T.BODY, self.body.encode("utf-8")),
        ):
            if len(value) > 255:
                raise ValueError(f"{tlv_type.name} too long")
            out += bytes([tlv_type, len(value)]) + value
        out += bytes([self._T.SENT_AT, 4]) + struct.pack("!I", self.sent_at)
        return bytes(out)

    @classmethod
    def decode(cls, data: bytes) -> Optional["GeneralMessagePayload"]:
        cmid: Optional[str] = None
        body: Optional[str] = None
        sent_at: Optional[int] = None
        for t, v in _iter_tlv(data):
            if t == cls._T.CLIENT_MSG_ID:
                cmid = _utf8(v)
            elif t == cls._T.BODY:
                body = _utf8(v)
            elif t == cls._T.SENT_AT and len(v) == 4:
                (sent_at,) = struct.unpack("!I", v)
        if cmid is None or body is None or sent_at is None:
            return None
        return cls(client_msg_id=cmid, body=body, sent_at=sent_at)


# ---------------------------------------------------------------------------
# ProfileUpdatePayload (0x24)
# ---------------------------------------------------------------------------
#
# Forward-declared. The iOS app currently delivers profile updates over
# HTTP only — it has no DTN fallback wired in for `updateProfile`. The
# wire format below is provisional and matches the registration form
# fields. Revise once iOS adds the encoder.


@dataclass
class ProfileUpdatePayload:
    name: str
    phone_number: str
    language: str
    profession: Optional[str] = None

    class _T(IntEnum):
        NAME = 0x01
        PHONE_NUMBER = 0x02
        PROFESSION = 0x03  # optional
        LANGUAGE = 0x04

    def encode(self) -> bytes:
        out = bytearray()
        for tlv_type, value in (
            (self._T.NAME, self.name.encode("utf-8")),
            (self._T.PHONE_NUMBER, self.phone_number.encode("utf-8")),
            (self._T.LANGUAGE, self.language.encode("utf-8")),
        ):
            if len(value) > 255:
                raise ValueError(f"{tlv_type.name} too long")
            out += bytes([tlv_type, len(value)]) + value
        if self.profession is not None:
            prof = self.profession.encode("utf-8")
            if len(prof) > 255:
                raise ValueError("profession too long")
            out += bytes([self._T.PROFESSION, len(prof)]) + prof
        return bytes(out)

    @classmethod
    def decode(cls, data: bytes) -> Optional["ProfileUpdatePayload"]:
        name: Optional[str] = None
        phone: Optional[str] = None
        language: Optional[str] = None
        profession: Optional[str] = None
        for t, v in _iter_tlv(data):
            if t == cls._T.NAME:
                name = _utf8(v)
            elif t == cls._T.PHONE_NUMBER:
                phone = _utf8(v)
            elif t == cls._T.PROFESSION:
                profession = _utf8(v)
            elif t == cls._T.LANGUAGE:
                language = _utf8(v)
        if name is None or phone is None or language is None:
            return None
        return cls(
            name=name,
            phone_number=phone,
            language=language,
            profession=profession,
        )
