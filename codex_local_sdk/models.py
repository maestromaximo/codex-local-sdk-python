from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class SandboxMode(str, Enum):
    READ_ONLY = "read-only"
    WORKSPACE_WRITE = "workspace-write"
    DANGER_FULL_ACCESS = "danger-full-access"


@dataclass(frozen=True)
class CodexExecRequest:
    prompt: str
    cwd: str | None = None
    json_output: bool = False
    model: str | None = None
    profile: str | None = None
    sandbox: SandboxMode | None = None
    full_auto: bool = False
    ephemeral: bool = False
    skip_git_repo_check: bool = False
    output_last_message_path: str | None = None
    output_schema_path: str | None = None
    images: tuple[str, ...] = ()
    extra_args: tuple[str, ...] = ()


@dataclass(frozen=True)
class CodexEvent:
    type: str
    raw: dict


@dataclass(frozen=True)
class CodexExecResult:
    return_code: int
    command: tuple[str, ...]
    stdout: str
    stderr: str
    final_message: str | None
    thread_id: str | None = None
    turn_status: str | None = None
    usage: dict | None = None
    events: tuple[CodexEvent, ...] = field(default_factory=tuple)
    duration_seconds: float = 0.0

    @property
    def ok(self) -> bool:
        return self.return_code == 0

    @property
    def is_turn_completed(self) -> bool:
        return self.turn_status == "completed"

    @property
    def is_turn_failed(self) -> bool:
        return self.turn_status == "failed"

    @property
    def is_turn_terminal(self) -> bool:
        return self.turn_status in {"completed", "failed", "interrupted"}
