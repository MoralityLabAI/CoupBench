from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass
class Reply:
    text: str
    refused: bool = False
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: float = 0.0
    meta: Dict[str, Any] = field(default_factory=dict)


class Backend:
    """Common interface for models under evaluation. Each turn is a fresh, stateless call."""

    name: str = "base"

    def complete(self, system: str, prompt: str) -> Reply:
        raise NotImplementedError
