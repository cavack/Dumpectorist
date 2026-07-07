from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from app.adapters.benchmark_models import BenchmarkSource


@dataclass(frozen=True)
class CrossExchangeSymbolMap:
    canonical_symbol: str
    lbank_symbol: str
    benchmark_symbols: Mapping[BenchmarkSource, str]
    reliable: bool = True

    def __post_init__(self) -> None:
        canonical = self.canonical_symbol.strip()
        lbank = self.lbank_symbol.strip()
        if not canonical:
            raise ValueError("canonical_symbol is required")
        if not lbank:
            raise ValueError("lbank_symbol is required")

        normalized: dict[BenchmarkSource, str] = {}
        for source, symbol in self.benchmark_symbols.items():
            if not isinstance(source, BenchmarkSource):
                raise ValueError("benchmark symbol keys must be BenchmarkSource values")
            clean_symbol = symbol.strip()
            if not clean_symbol:
                raise ValueError(f"symbol is required for {source.value}")
            normalized[source] = clean_symbol
        if not normalized:
            raise ValueError("at least one benchmark symbol is required")

        object.__setattr__(self, "canonical_symbol", canonical)
        object.__setattr__(self, "lbank_symbol", lbank)
        object.__setattr__(self, "benchmark_symbols", MappingProxyType(normalized))

    def expected_symbol(self, source: BenchmarkSource) -> str | None:
        return self.benchmark_symbols.get(source)
