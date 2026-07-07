from app.db.repository import DomainRecordInput, DomainRecordRepository
from app.runtime.store import _payload_record_type, _record_symbol, json_safe


async def add_runtime_records(session, job, payload, outcome, source_payload):
    symbol = _record_symbol(job, payload)
    repository = DomainRecordRepository(session)
    records = (
        DomainRecordInput(
            record_type=_payload_record_type(job, payload),
            symbol=symbol,
            state=payload.health.state.value,
            payload=json_safe(source_payload),
        ),
        DomainRecordInput(
            record_type="source_health",
            symbol=symbol,
            state=payload.health.state.value,
            payload=json_safe(
                {
                    "job_name": job.name,
                    "adapter_name": payload.health.name,
                    "kind": job.kind.value,
                    "latency_ms": payload.health.latency_ms,
                    "message": payload.health.message,
                    "observed_at": outcome.finished_at,
                }
            ),
        ),
        DomainRecordInput(
            record_type="worker_run",
            symbol=symbol,
            state=outcome.status.value,
            payload=json_safe(
                {
                    "job_name": job.name,
                    "adapter_name": payload.name,
                    "kind": job.kind.value,
                    "started_at": outcome.started_at,
                    "finished_at": outcome.finished_at,
                    "duration_ms": outcome.duration_ms,
                    "adapter_state": payload.health.state.value,
                    "message": outcome.message,
                }
            ),
        ),
    )
    for record in records:
        await repository.add(record)
