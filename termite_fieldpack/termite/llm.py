from __future__ import annotations
import json
import os
from dataclasses import dataclass
from typing import Any, Dict, Optional
import requests

@dataclass
class LLMEndpoint:
    base_url: str
    api_key: Optional[str] = None

    def chat(self, prompt: str, *, model: str = "qwen2.5-coder-0.5b-instruct", temperature: float = 0.2) -> str:
        # OpenAI-compatible minimal call (works with local endpoints that mimic /v1/chat/completions)
        url = self.base_url.rstrip("/") + "/v1/chat/completions"
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        payload = {
            "model": model,
            "temperature": temperature,
            "messages": [{"role":"user","content": prompt}],
        }
        r = requests.post(url, headers=headers, data=json.dumps(payload))
        r.raise_for_status()
        obj = r.json()
        return obj["choices"][0]["message"]["content"]
