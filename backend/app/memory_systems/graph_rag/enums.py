from __future__ import annotations

from enum import Enum


class GraphRAGProviderName(str, Enum):
    UNAVAILABLE = "unavailable"
    MICROSOFT_LOCAL = "microsoft_graphrag_local"
