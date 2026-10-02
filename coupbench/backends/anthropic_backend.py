from __future__ import annotations

import time

import anthropic

from .base import Backend, Reply


class AnthropicBackend(Backend):
    def __init__(self, model: str = "claude-opus-5-5", effort: str = "medium", max_tokens: int = 16000):
        self.model = model
        self.effort = effort
        self.max_tokens = max_tokens
        self.name = f"anthropic:{model}"
        self.client = anthropic.Anthropic(max_retries=5)

    def complete(self, system: str, prompt: str) -> Reply:
        t0 = time.perf_counter()
        # No refusal `fallbacks` here on purpose: a decline by the model under test is the
        # measurement, and a fallback model would answer in its place.
        response = self.client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            output_config={"effort": self.effort},
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        refused = response.stop_reason == "refusal"
        meta = {"stop_reason": response.stop_reason, "request_id": response._request_id}
        if refused and response.stop_details:
            meta["refusal_category"] = response.stop_details.category
        return Reply(
            text="".join(block.text for block in response.content if block.type == "text"),
            refused=refused,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            latency_ms=(time.perf_counter() - t0) * 1000.0,
            meta=meta,
        )
