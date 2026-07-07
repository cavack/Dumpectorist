from typing import Protocol

from app.notifications.models import (
    DeliveryReceipt,
    DeliveryStatus,
    NotificationMessage,
)


class DeliveryPort(Protocol):
    async def deliver(self, message: NotificationMessage) -> DeliveryReceipt:
        """Deliver one formatted notification message."""


class DisabledDelivery:
    async def deliver(self, message: NotificationMessage) -> DeliveryReceipt:
        return DeliveryReceipt(
            symbol=message.symbol,
            channel=message.channel,
            status=DeliveryStatus.SKIPPED,
            detail="delivery disabled",
        )
