from __future__ import annotations

from typing import Protocol

from app.memory_systems.common.exceptions.errors import MemorySystemRequiresLLM


class ChatGenerationProvider(Protocol):
    supports_structured_output: bool

    def generate(self, messages: list[dict], context: list[dict], configuration: dict) -> str:
        ...


class SummaryProvider(Protocol):
    def summarize(self, previous_summary: str, new_sources: list, recent_window: list) -> str:
        ...


class StructuredExtractionProvider(Protocol):
    def extract_entities_relations(self, text: str) -> dict:
        ...

    def extract_open_information(self, text: str) -> dict:
        ...

    def extract_observations(self, text: str) -> dict:
        ...


class CommunityReportProvider(Protocol):
    def generate_community_report(self, community_context: dict) -> str:
        ...


class UnavailableLLMProvider:
    supports_structured_output = False

    def generate(self, messages: list[dict], context: list[dict], configuration: dict) -> str:
        raise MemorySystemRequiresLLM("LLM provider is not configured.")

    def summarize(self, previous_summary: str, new_sources: list, recent_window: list) -> str:
        raise MemorySystemRequiresLLM("Summary provider is not configured.")

    def extract_entities_relations(self, text: str) -> dict:
        raise MemorySystemRequiresLLM("Structured extraction provider is not configured.")

    def extract_open_information(self, text: str) -> dict:
        raise MemorySystemRequiresLLM("OpenIE provider is not configured.")

    def extract_observations(self, text: str) -> dict:
        raise MemorySystemRequiresLLM("Observation extraction provider is not configured.")

    def generate_community_report(self, community_context: dict) -> str:
        raise MemorySystemRequiresLLM("Community report provider is not configured.")


class DeterministicFakeLLMProvider:
    supports_structured_output = True

    def generate(self, messages: list[dict], context: list[dict], configuration: dict) -> str:
        return "deterministic-test-generation"

    def summarize(self, previous_summary: str, new_sources: list, recent_window: list) -> str:
        return "deterministic-test-summary"

    def extract_entities_relations(self, text: str) -> dict:
        return {"entities": [], "relationships": []}

    def extract_open_information(self, text: str) -> dict:
        return {"facts": []}

    def extract_observations(self, text: str) -> dict:
        return {"observations": []}

    def generate_community_report(self, community_context: dict) -> str:
        return "deterministic-test-community-report"
