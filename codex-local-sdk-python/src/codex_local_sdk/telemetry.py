from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class CodexClientEvent:
    """Structured event emitted by CodexLocalClient during execution."""

    type: str
    operation: str
    attempt: int | None = None
    command: tuple[str, ...] | None = None
    session_name: str | None = None
    session_id: str | None = None
    retry_delay_seconds: float | None = None
    return_code: int | None = None
    turn_status: str | None = None
    duration_seconds: float | None = None
    message: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
