from __future__ import annotations


PROMPT_VERSION = "rolling-summary-v1"

SYSTEM_PROMPT = """
You create a concise, source-grounded rolling clinical memory summary for one patient.
Use only the supplied sources. Preserve contradictions, corrections, uncertainty, and source IDs.
Do not invent facts. Do not turn assistant conversation messages into verified clinical facts.
Return structured output only.
""".strip()


def build_user_prompt(*, source_cutoff_time: str, sources: list[dict]) -> str:
    source_lines = []

    for source in sources:
        source_lines.append(
            "\n".join(
                [
                    f"Source ID: {source['source_id']}",
                    f"Type: {source['source_type']} / {source['source_subtype']}",
                    f"Event time: {source['event_time']}",
                    f"Content: {source['content']}",
                ]
            )
        )

    return "\n\n".join(
        [
            f"Source cutoff time: {source_cutoff_time}",
            "Create an updated rolling summary using these sources.",
            "Every included fact must cite at least one Source ID.",
            "\n\n---\n\n".join(source_lines) if source_lines else "No sources.",
        ]
    )
