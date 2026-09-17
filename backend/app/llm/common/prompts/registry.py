from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from app.config import settings


@dataclass(frozen=True)
class PromptBundle:
    prompt_id: str
    task_type: str
    version: int
    system_prompt: str
    user_prompt_template: str
    checksum: str


class PromptRegistry:
    def __init__(self, root: Path) -> None:
        self.root = root

    def get_final_answer_prompt(self) -> PromptBundle:
        version = settings.llm_prompt_version
        base = self.root / "final_answer"
        system_prompt = (base / f"v{version}_system.txt").read_text(encoding="utf-8")
        user_prompt = (base / f"v{version}_user.txt").read_text(encoding="utf-8")
        checksum = hashlib.sha256(f"{system_prompt}\n{user_prompt}".encode("utf-8")).hexdigest()

        return PromptBundle(
            prompt_id=f"final_answer_v{version}",
            task_type="final_answer",
            version=version,
            system_prompt=system_prompt,
            user_prompt_template=user_prompt,
            checksum=checksum,
        )


prompt_registry = PromptRegistry(Path(__file__).parent)
