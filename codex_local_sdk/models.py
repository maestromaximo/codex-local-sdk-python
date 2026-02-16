"""Core data models shared across the local Codex SDK."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class SandboxMode(str, Enum):
    """Allowed values for the Codex CLI `--sandbox` option.

    Use these enum values with `CodexExecRequest.sandbox` instead of raw strings.
    """

    READ_ONLY = "read-only"
    WORKSPACE_WRITE = "workspace-write"
    DANGER_FULL_ACCESS = "danger-full-access"


@dataclass(frozen=True)
class CodexExecRequest:
    """Parameters for one `codex exec` invocation.

    Most users can start with `prompt` plus one or two optional flags:
    - `json_output=True` when you want parsed events and thread metadata.
    - `cwd` to run Codex in a specific project directory.
    - `model`, `reasoning_effort`, `profile`, `sandbox` for CLI runtime
      configuration.

    Example:
        request = CodexExecRequest(
            prompt="Summarize this repository.",
            json_output=True,
            sandbox=SandboxMode.WORKSPACE_WRITE,
        )
    """

    prompt: str
    cwd: str | None = None
    json_output: bool = False
    model: str | None = None
    reasoning_effort: str | None = None
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
class RetryPolicy:
    """Retry and backoff configuration for sync command execution.

    Notes:
    - This policy applies to non-live sync execution paths.
    - Live APIs (`run_live*`, `resume_live*`) only retry startup failures.
    - `max_total_retry_seconds` bounds cumulative retry time.

    Example:
        policy = RetryPolicy(
            max_attempts=3,
            retry_on_exit_codes=(1, 124),
            initial_backoff_seconds=0.3,
        )
    """

    max_attempts: int = 1
    initial_backoff_seconds: float = 0.5
    backoff_multiplier: float = 2.0
    max_backoff_seconds: float = 8.0
    retry_on_exit_codes: tuple[int, ...] | None = None
    jitter_ratio: float = 0.2
    max_total_retry_seconds: float | None = None
    retry_on_timeouts: bool = True


@dataclass(frozen=True)
class CodexEvent:
    """Normalized JSON event emitted by `codex exec --json`.

    Attributes:
        type: Top-level event type, for example `thread.started` or `turn.completed`.
        raw: Original parsed JSON payload for full-fidelity access.
    """

    type: str
    raw: dict


@dataclass(frozen=True)
class CodexExecResult:
    """Structured result returned by sync and async SDK execution methods.

    `final_message`, `thread_id`, `turn_status`, and `events` are populated when
    JSON output is enabled for the run.

    Example:
        result = client.run_prompt("Say hello", json_output=True)
        if result.ok:
            print(result.final_message)
            print(result.thread_id)
    """

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
        """Return `True` when the command exited with code `0`."""
        return self.return_code == 0

    @property
    def is_turn_completed(self) -> bool:
        """Return `True` when Codex reported terminal turn status `completed`."""
        return self.turn_status == "completed"

    @property
    def is_turn_failed(self) -> bool:
        """Return `True` when Codex reported terminal turn status `failed`."""
        return self.turn_status == "failed"

    @property
    def is_turn_terminal(self) -> bool:
        """Return `True` when turn status is any terminal value."""
        return self.turn_status in {"completed", "failed", "interrupted"}
