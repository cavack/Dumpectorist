# Notification Interfaces

Sprint 7 adds typed message formatting and delivery interfaces after plan creation.

## Components

```text
NotificationChannel
NotificationMessage
DeliveryStatus
DeliveryReceipt
DeliveryPort
DisabledDelivery
format_plan_message
```

## Flow

```text
PlanDraft
  -> format_plan_message
  -> NotificationMessage
  -> DeliveryPort
  -> DeliveryReceipt
```

## Rules

- Ready plans include entry, boundary, objective, multiplier, and ratio.
- Held plans produce a readable waiting message without numeric values.
- Ready plans missing required values are rejected.
- DisabledDelivery always returns SKIPPED and performs no external request.

## Current Channels

```text
TELEGRAM
DASHBOARD
```

These values are interface targets only. No real delivery integration is enabled in this sprint.
