from dataclasses import dataclass
from typing import Optional, Protocol


@dataclass
class SendResult:
    provider_msg_id: str
    accepted: bool = True
    error: Optional[str] = None


@dataclass
class SentMessage:
    to: str
    body: str
    media: list[str]
    idempotency_key: Optional[str]
    provider_msg_id: str


class SmsProvider(Protocol):
    async def send(
        self,
        to: str,
        body: str,
        media: Optional[list[str]] = None,
        idempotency_key: Optional[str] = None,
    ) -> SendResult: ...

    def inbound_handler(self) -> object | None:
        """Returns an ASGI app to mount, or None for sim providers
        that drive inbound through their own UI."""
        ...
