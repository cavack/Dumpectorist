from dataclasses import dataclass


@dataclass
class RuntimeRecordPayloads:
    symbol: str
    record_type: str
    source: dict
    health: dict
    run: dict
