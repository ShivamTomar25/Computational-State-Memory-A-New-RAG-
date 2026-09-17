from __future__ import annotations

from app.memory_systems.common.enums.status import SYSTEM_TYPES
from app.memory_systems.common.exceptions.errors import MemorySystemNotFound
from app.memory_systems.common.registry.adapter import MemorySystemAdapter


class MemorySystemRegistry:
    def __init__(self) -> None:
        self._adapters: dict[str, MemorySystemAdapter] = {}

    def register(self, adapter: MemorySystemAdapter) -> None:
        if adapter.system_type in self._adapters:
            raise ValueError(f"Memory system already registered: {adapter.system_type}")

        self._adapters[adapter.system_type] = adapter

    def get(self, system_type: str) -> MemorySystemAdapter:
        adapter = self._adapters.get(system_type)

        if adapter is None:
            raise MemorySystemNotFound("Memory system not found.")

        return adapter

    def all(self) -> list[MemorySystemAdapter]:
        return [self._adapters[system_type] for system_type in SYSTEM_TYPES]

    def keys(self) -> tuple[str, ...]:
        return tuple(self._adapters.keys())


def build_default_registry() -> MemorySystemRegistry:
    from app.memory_systems.csm.adapter import CsmAdapter
    from app.memory_systems.csm.v3_adapter import CsmV3Adapter
    from app.memory_systems.csm.v4_adapter import CsmV4Adapter
    from app.memory_systems.dense_rag.adapter import DenseRagAdapter
    from app.memory_systems.graph_rag.adapter import GraphRagAdapter
    from app.memory_systems.hippo_rag.adapter import HippoRagAdapter
    from app.memory_systems.hybrid_rag.adapter import HybridRagAdapter
    from app.memory_systems.long_context.adapter import LongContextAdapter
    from app.memory_systems.rolling_summary.adapter import RollingSummaryAdapter

    registry = MemorySystemRegistry()

    for adapter in (
        LongContextAdapter(),
        RollingSummaryAdapter(),
        DenseRagAdapter(),
        HybridRagAdapter(),
        GraphRagAdapter(),
        HippoRagAdapter(),
        CsmAdapter(),
        CsmV3Adapter(),
        CsmV4Adapter(),
    ):
        registry.register(adapter)

    return registry


registry = build_default_registry()
