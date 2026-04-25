import uuid
from typing import Optional

from server.transports.sms_base import SendResult, SentMessage


class SimSmsProvider:
    """In-process SMS provider for the hackathon demo.

    Outbound: appends to `self.sent` and returns a fake provider_msg_id.
    Inbound: not handled here — the simulator drives the API tier directly
    via the in-process app channel.
    """

    def __init__(self) -> None:
        self.sent: list[SentMessage] = []
        self._idem: dict[str, str] = {}

    async def send(
        self,
        to: str,
        body: str,
        media: Optional[list[str]] = None,
        idempotency_key: Optional[str] = None,
    ) -> SendResult:
        if idempotency_key and idempotency_key in self._idem:
            return SendResult(provider_msg_id=self._idem[idempotency_key])
        provider_msg_id = f"sim-{uuid.uuid4().hex}"
        if idempotency_key:
            self._idem[idempotency_key] = provider_msg_id
        self.sent.append(
            SentMessage(
                to=to,
                body=body,
                media=media or [],
                idempotency_key=idempotency_key,
                provider_msg_id=provider_msg_id,
            )
        )
        return SendResult(provider_msg_id=provider_msg_id)

    def inbound_handler(self) -> None:
        return None
