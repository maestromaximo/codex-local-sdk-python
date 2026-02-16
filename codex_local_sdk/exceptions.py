"""SDK exception types for common Codex execution failure modes."""

from __future__ import annotations

from .models import CodexExecResult


class CodexError(Exception):
    """Base SDK exception."""


class CodexNotInstalledError(CodexError):
    """Raised when the `codex` binary cannot be found."""


class CodexExecFailedError(CodexError):
    """Raised when a Codex command exits non-zero.

    The `result` attribute contains the full `CodexExecResult` for inspection.
    """

    def __init__(self, message: str, result: CodexExecResult):
        """Attach the failed execution result for caller inspection."""
        super().__init__(message)
        self.result = result
