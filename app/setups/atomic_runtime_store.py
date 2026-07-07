from app.adapters.models import AdapterState
from app.candles.models import CandleInterval
from app.candles.serialization import batch_from_payload_data
from app.runtime.models import SourceJobKind
from app.runtime.store import DomainRecordRuntimeStore
from app.setups.runtime_m15 import persist_m15_confirmation
from app.setups.runtime_records import add_runtime_records


class AtomicReclaimRuntimeStore(DomainRecordRuntimeStore):
    async def persist_payload(self, job, payload, outcome):
        is_structure = job.kind == SourceJobKind.STRUCTURE
        is_ok = payload.health.state == AdapterState.OK
        if not (is_structure and is_ok):
            return await super().persist_payload(job, payload, outcome)

        batch = batch_from_payload_data(payload.data)
        if batch.interval != CandleInterval.M15:
            return await super().persist_payload(job, payload, outcome)

        async with self.session_factory() as session:
            source_payload = await persist_m15_confirmation(session, payload)
            source_payload["job_name"] = job.name
            source_payload["adapter_name"] = payload.name
            source_payload["kind"] = job.kind.value
            await add_runtime_records(session, job, payload, outcome, source_payload)
            await session.commit()
