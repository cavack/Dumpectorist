from app.adapters.models import AdapterPayload, AdapterState
from app.candles.serialization import batch_from_payload_data
from app.runtime.models import ScheduledSourceJob, SourceJobKind, WorkerRunOutcome
from app.runtime.store import DomainRecordRuntimeStore
from app.setups.runtime_analysis import persist_reclaim_from_structure
from app.structure.htf_engine import analyze_higher_timeframe


class ReclaimAwareRuntimeStore(DomainRecordRuntimeStore):
    async def persist_payload(
        self,
        job: ScheduledSourceJob,
        payload: AdapterPayload,
        outcome: WorkerRunOutcome,
    ) -> None:
        await super().persist_payload(job, payload, outcome)
        if job.kind != SourceJobKind.STRUCTURE:
            return
        if payload.health.state != AdapterState.OK:
            return

        batch = batch_from_payload_data(payload.data)
        analysis = analyze_higher_timeframe(batch)
        async with self.session_factory() as session:
            await persist_reclaim_from_structure(session, batch, analysis)
            await session.commit()
