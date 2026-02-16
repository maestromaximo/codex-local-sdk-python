from __future__ import annotations

from .models import CodexExecResult


class CodexError(Exception):
    """Base SDK exception."""


class CodexNotInstalledError(CodexError):
    """Raised when the `codex` binary cannot be found."""


class CodexExecFailedError(CodexError):
    """Raised when a codex command exits non-zero."""

    def __init__(self, message: str, result: CodexExecResult):
        super().__init__(message)
        self.result = result
