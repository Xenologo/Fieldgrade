from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
from termite.llm import LLMEndpoint  # type: ignore

@dataclass
class LLMClient:
    base_url: str
    api_key: Optional[str] = None

    def complete(self, prompt: str, *, model: str = "qwen2.5-coder-0.5b-instruct", temperature: float = 0.2) -> str:
        ep = LLMEndpoint(base_url=self.base_url, api_key=self.api_key)
        return ep.chat(prompt, model=model, temperature=temperature)
