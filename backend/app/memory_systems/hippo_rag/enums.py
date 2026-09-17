from __future__ import annotations

from enum import Enum


class HippoRAGProviderName(str, Enum):
    UNAVAILABLE = "unavailable"
    OFFICIAL_LOCAL = "official_hipporag_local"
