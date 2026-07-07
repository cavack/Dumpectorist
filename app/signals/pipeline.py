from datetime import datetime

from app.signals.models import (
    SignalAssemblyReport,
    SignalAssemblyRequest,
    SignalAssemblyRules,
)
from app.signals.service import assemble_signal
from app.signals.store import SignalAssemblyStore


async def assemble_and_persist(
    request: SignalAssemblyRequest,
    *,
    now: datetime,
    store: SignalAssemblyStore,
    rules: SignalAssemblyRules | None = None,
) -> SignalAssemblyReport:
    report = assemble_signal(request, now=now, rules=rules)
    await store.persist(report)
    return report
