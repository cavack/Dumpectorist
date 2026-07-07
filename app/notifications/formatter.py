from app.notifications.models import NotificationChannel, NotificationMessage
from app.planning.models import PlanDraft, PlanStatus


def _format_number(value: float) -> str:
    return f"{value:g}"


def format_plan_message(
    plan: PlanDraft,
    channel: NotificationChannel = NotificationChannel.TELEGRAM,
) -> NotificationMessage:
    title = f"{plan.symbol} plan update"

    if plan.status == PlanStatus.HOLD:
        note = plan.notes[0] if plan.notes else "waiting"
        return NotificationMessage(
            symbol=plan.symbol,
            channel=channel,
            title=title,
            body=f"Status: HOLD\nNote: {note}",
            metadata={"status": plan.status.value},
        )

    values = (plan.entry_value, plan.boundary_value, plan.objective_value)
    if any(value is None for value in values):
        raise ValueError("ready plan is missing required values")

    entry_value = float(plan.entry_value)
    boundary_value = float(plan.boundary_value)
    objective_value = float(plan.objective_value)

    body = "\n".join(
        (
            "Status: READY",
            f"Entry: {_format_number(entry_value)}",
            f"Boundary: {_format_number(boundary_value)}",
            f"Objective: {_format_number(objective_value)}",
            f"Multiplier: {plan.multiplier}",
            f"Ratio: {_format_number(plan.ratio)}",
        )
    )

    return NotificationMessage(
        symbol=plan.symbol,
        channel=channel,
        title=title,
        body=body,
        metadata={
            "status": plan.status.value,
            "multiplier": str(plan.multiplier),
            "ratio": _format_number(plan.ratio),
        },
    )
