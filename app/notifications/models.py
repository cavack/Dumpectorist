from dataclasses import dataclass, field
from enum import StrEnum


class NotificationChannel(StrEnum):
    TELEGRAM = "TELEGRAM"
    DASHBOARD = "DASHBOARD"


class DeliveryStatus(StrEnum):
    ACCEPTED = "ACCEPTED"
    SKIPPED = "SKIPPED"


@dataclass(frozen=True)
class NotificationMessage:
    symbol: str
    channel: NotificationChannel
    title: str
    body: str
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class DeliveryReceipt:
    symbol: str
    channel: NotificationChannel
    status: DeliveryStatus
    detail: str = ""
