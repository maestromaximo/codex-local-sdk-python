"""Client implementations for running non-interactive Codex CLI flows."""

from __future__ import annotations

import asyncio
import functools
import json
import os
import random
import shutil
import subprocess
import tempfile
import threading
import time
from dataclasses import replace
from typing import AsyncIterator, Callable, Iterator

from .exceptions import CodexError, CodexExecFailedError, CodexNotInstalledError
from .models import CodexEvent, CodexExecRequest, CodexExecResult, RetryPolicy
from .session_store import InMemorySessionStore, SessionRecord, SessionStore, SessionTurnRecord
from .telemetry import CodexClientEvent

_TIMEOUT_MARKER = "SDK_TIMEOUT_EXPIRED"
_PROMPT_PREVIEW_LIMIT = 180
_MESSAGE_PREVIEW_LIMIT = 220
_LIVE_STARTUP_PROBE_SECONDS = 0.2
_LIVE_STARTUP_PROBE_INTERVAL_SECONDS = 0.01


def _parse_event_line(line: str) -> CodexEvent | None:
    """Parse a single JSONL line into a `CodexEvent` when possible."""
    payload: dict
    try:
        payload = json.loads(line)
    except json.JSONDecodeError:
        return None
    event_type = payload.get("type", "unknown")
    return CodexEvent(type=str(event_type), raw=payload)


def _parse_jsonl_events(stdout: str) -> tuple[CodexEvent, ...]:
    """Parse all JSONL events found in command stdout."""
    events: list[CodexEvent] = []
    for line in stdout.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        event = _parse_event_line(stripped)
        if event is not None:
            events.append(event)
    return tuple(events)


def _extract_thread_id(events: tuple[CodexEvent, ...]) -> str | None:
    """Extract a thread id from parsed events using known payload shapes."""
    for event in events:
        if event.type != "thread.started":
            continue

        for key in ("thread_id", "threadId"):
            value = event.raw.get(key)
            if isinstance(value, str) and value.strip():
                return value

        thread_obj = event.raw.get("thread")
        if isinstance(thread_obj, dict):
            thread_id = thread_obj.get("id")
            if isinstance(thread_id, str) and thread_id.strip():
                return thread_id
    return None


def _extract_turn_status_and_usage(events: tuple[CodexEvent, ...]) -> tuple[str | None, dict | None]:
    """Derive final turn status and usage metadata from parsed events."""
    status: str | None = None
    usage: dict | None = None

    for event in events:
        if event.type == "turn.completed":
            status = "completed"
            event_usage = event.raw.get("usage")
            if isinstance(event_usage, dict):
                usage = event_usage
            continue

        if event.type == "turn.failed":
            status = "failed"
            continue

        if event.type == "turn.interrupted":
            status = "interrupted"
            continue

        turn_obj = event.raw.get("turn")
        if isinstance(turn_obj, dict):
            turn_status = turn_obj.get("status")
            if isinstance(turn_status, str) and turn_status in {"completed", "failed", "interrupted"}:
                status = turn_status

            turn_usage = turn_obj.get("usage")
            if isinstance(turn_usage, dict):
                usage = turn_usage

    return status, usage


def _extract_final_message(
    stdout: str,
    events: tuple[CodexEvent, ...],
    json_output: bool,
) -> str | None:
    """Extract the most relevant final assistant message from command output."""
    if not json_output:
        stripped = stdout.strip()
        return stripped or None

    for event in reversed(events):
        if event.type != "item.completed":
            continue
        item = event.raw.get("item") or {}
        item_type = item.get("type")
        if item_type in {"agent_message", "agentMessage"}:
            text = item.get("text")
            if isinstance(text, str) and text.strip():
                return text.strip()
    return None


def _build_result(
    return_code: int,
    command: list[str],
    stdout: str,
    stderr: str,
    duration_seconds: float,
    json_output: bool,
) -> CodexExecResult:
    """Build a normalized `CodexExecResult` from raw subprocess output."""
    events: tuple[CodexEvent, ...] = ()
    if json_output:
        events = _parse_jsonl_events(stdout)

    thread_id = _extract_thread_id(events)
    turn_status, usage = _extract_turn_status_and_usage(events)

    return CodexExecResult(
        return_code=return_code,
        command=tuple(command),
        stdout=stdout,
        stderr=stderr,
        final_message=_extract_final_message(stdout, events, json_output),
        thread_id=thread_id,
        turn_status=turn_status,
        usage=usage,
        events=events,
        duration_seconds=duration_seconds,
    )


def _coerce_subprocess_output(value: object) -> str:
    """Convert timeout exception stdout/stderr fields into text."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def _preview(text: str | None, limit: int) -> str | None:
    """Return a trimmed preview string bounded by `limit` characters."""
    if text is None:
        return None
    stripped = text.strip()
    if not stripped:
        return None
    if len(stripped) <= limit:
        return stripped
    return f"{stripped[: limit - 3]}..."


class CodexLiveRun:
    """Represents an active sync live run started with `subprocess.Popen`.

    Use this handle when you need streaming JSON events from Codex:
    1. Call `iter_events()` to process events as they arrive.
    2. Call `wait()` or `result()` to get the terminal `CodexExecResult`.

    Example:
        live = client.run_live(CodexExecRequest(prompt="Explain repo", json_output=True))
        for event in live.iter_events():
            print(event.type)
        result = live.wait()
    """

    def __init__(
        self,
        process: subprocess.Popen[str],
        command: list[str],
        started_at: float,
        raise_on_error: bool,
        event_callback: Callable[[CodexEvent], None] | None = None,
        result_callback: Callable[[CodexExecResult], None] | None = None,
    ) -> None:
        """Create a live-run handle around an already-started subprocess."""
        self._process = process
        self.command = tuple(command)
        self._started_at = started_at
        self._raise_on_error = raise_on_error
        self._event_callback = event_callback
        self._result_callback = result_callback

        self._stdout_lines: list[str] = []
        self._stderr_lines: list[str] = []
        self._events: list[CodexEvent] = []

        self._stdout_consumed = False
        self._result_cache: CodexExecResult | None = None
        self._result_callback_sent = False

        self._stderr_thread = threading.Thread(target=self._drain_stderr, daemon=True)
        self._stderr_thread.start()

    @property
    def pid(self) -> int:
        """Return the subprocess PID."""
        return self._process.pid

    @property
    def events(self) -> tuple[CodexEvent, ...]:
        """Return events consumed so far."""
        return tuple(self._events)

    @property
    def is_complete(self) -> bool:
        """Return `True` when the process has exited."""
        return self._process.poll() is not None

    @property
    def return_code(self) -> int | None:
        """Return the process return code, or `None` while running."""
        return self._process.poll()

    def iter_events(self) -> Iterator[CodexEvent]:
        """Yield parsed events from stdout as they arrive.

        This consumes live stdout. After it has been fully consumed once, repeated
        calls yield nothing.
        """
        if self._stdout_consumed:
            return

        if self._process.stdout is None:
            self._stdout_consumed = True
            return

        while True:
            line = self._process.stdout.readline()
            if line == "":
                break
            if not line:
                continue
            self._record_stdout_line(line)
            if self._events:
                yield self._events[-1]

        self._stdout_consumed = True

    def wait(self, timeout: float | None = None) -> CodexExecResult:
        """Wait for process completion and return the parsed terminal result.

        Raises:
            subprocess.TimeoutExpired: If `timeout` elapses before completion.
        """
        self._process.wait(timeout=timeout)
        return self.result()

    def terminate(self) -> None:
        """Send a graceful termination signal to the process."""
        self._process.terminate()

    def kill(self) -> None:
        """Force-kill the process."""
        self._process.kill()

    def result(self) -> CodexExecResult:
        """Return the terminal parsed result for this live run.

        `result()` may only be called after the process exits. If `raise_on_error`
        was enabled on the parent client and exit code is non-zero, this raises
        `CodexExecFailedError`.
        """
        if self._result_cache is not None:
            return self._result_cache

        if not self.is_complete:
            raise CodexError("Process is still running. Call wait() or poll is_complete before requesting result().")

        self._consume_remaining_stdout()
        self._stderr_thread.join(timeout=0.5)

        duration = time.monotonic() - self._started_at
        result = _build_result(
            return_code=self._process.returncode if self._process.returncode is not None else 1,
            command=list(self.command),
            stdout="".join(self._stdout_lines),
            stderr="".join(self._stderr_lines),
            duration_seconds=duration,
            json_output=True,
        )

        if not self._result_callback_sent and self._result_callback is not None:
            try:
                self._result_callback(result)
            except Exception:
                pass
            self._result_callback_sent = True

        if self._raise_on_error and not result.ok:
            raise CodexExecFailedError(
                f"Codex live command failed with exit code {result.return_code}.",
                result=result,
            )

        self._result_cache = result
        return result

    def _record_stdout_line(self, line: str) -> None:
        """Store one stdout line and emit parsed event callbacks."""
        self._stdout_lines.append(line)
        event = _parse_event_line(line.strip())
        if event is not None:
            self._events.append(event)
            if self._event_callback is not None:
                try:
                    self._event_callback(event)
                except Exception:
                    pass

    def _consume_remaining_stdout(self) -> None:
        """Drain stdout after completion if event streaming stopped early."""
        if self._stdout_consumed:
            return

        if self._process.stdout is not None:
            for line in self._process.stdout:
                self._record_stdout_line(line)

        self._stdout_consumed = True

    def _drain_stderr(self) -> None:
        """Continuously drain stderr on a background thread."""
        if self._process.stderr is None:
            return
        for line in self._process.stderr:
            self._stderr_lines.append(line)


class AsyncCodexLiveRun:
    """Represents an active async live run backed by asyncio subprocess APIs.

    Example:
        live = await client.run_live_async(CodexExecRequest(prompt="Inspect tests"))
        async for event in live.iter_events():
            print(event.type)
        result = await live.wait()
    """

    def __init__(
        self,
        process: asyncio.subprocess.Process,
        command: list[str],
        started_at: float,
        raise_on_error: bool,
        event_callback: Callable[[CodexEvent], None] | None = None,
        result_callback: Callable[[CodexExecResult], None] | None = None,
    ) -> None:
        """Create an async live-run handle around an already-started process."""
        self._process = process
        self.command = tuple(command)
        self._started_at = started_at
        self._raise_on_error = raise_on_error
        self._event_callback = event_callback
        self._result_callback = result_callback

        self._stdout_lines: list[str] = []
        self._stderr_lines: list[str] = []
        self._events: list[CodexEvent] = []

        self._stdout_consumed = False
        self._result_cache: CodexExecResult | None = None
        self._result_callback_sent = False

        self._stderr_task = asyncio.create_task(self._drain_stderr())

    @property
    def pid(self) -> int | None:
        """Return the subprocess PID when available."""
        return self._process.pid

    @property
    def events(self) -> tuple[CodexEvent, ...]:
        """Return events consumed so far."""
        return tuple(self._events)

    @property
    def is_complete(self) -> bool:
        """Return `True` when the process has exited."""
        return self._process.returncode is not None

    @property
    def return_code(self) -> int | None:
        """Return the process return code, or `None` while running."""
        return self._process.returncode

    async def iter_events(self) -> AsyncIterator[CodexEvent]:
        """Yield parsed events from stdout as they arrive.

        This consumes live stdout. After it has been fully consumed once, repeated
        calls yield nothing.
        """
        if self._stdout_consumed:
            return

        if self._process.stdout is None:
            self._stdout_consumed = True
            return

        while True:
            line = await self._process.stdout.readline()
            if line == b"":
                break
            self._record_stdout_line(line)
            if self._events:
                yield self._events[-1]

        self._stdout_consumed = True

    async def wait(self, timeout: float | None = None) -> CodexExecResult:
        """Wait for process completion and return the parsed terminal result.

        Raises:
            asyncio.TimeoutError: If `timeout` elapses before completion.
        """
        if timeout is None:
            await self._process.wait()
        else:
            await asyncio.wait_for(self._process.wait(), timeout=timeout)
        return await self.result()

    def terminate(self) -> None:
        """Send a graceful termination signal to the process."""
        self._process.terminate()

    def kill(self) -> None:
        """Force-kill the process."""
        self._process.kill()

    async def result(self) -> CodexExecResult:
        """Return the terminal parsed result for this live run.

        `result()` may only be called after the process exits. If `raise_on_error`
        was enabled on the parent client and exit code is non-zero, this raises
        `CodexExecFailedError`.
        """
        if self._result_cache is not None:
            return self._result_cache

        if not self.is_complete:
            raise CodexError("Process is still running. Await wait() or check is_complete before requesting result().")

        await self._consume_remaining_stdout()
        try:
            await asyncio.wait_for(self._stderr_task, timeout=0.5)
        except asyncio.TimeoutError:
            pass

        duration = time.monotonic() - self._started_at
        result = _build_result(
            return_code=self._process.returncode if self._process.returncode is not None else 1,
            command=list(self.command),
            stdout="".join(self._stdout_lines),
            stderr="".join(self._stderr_lines),
            duration_seconds=duration,
            json_output=True,
        )

        if not self._result_callback_sent and self._result_callback is not None:
            try:
                self._result_callback(result)
            except Exception:
                pass
            self._result_callback_sent = True

        if self._raise_on_error and not result.ok:
            raise CodexExecFailedError(
                f"Codex async live command failed with exit code {result.return_code}.",
                result=result,
            )

        self._result_cache = result
        return result

    def _record_stdout_line(self, line: bytes) -> None:
        """Store one stdout line and emit parsed event callbacks."""
        text = line.decode("utf-8", errors="replace")
        self._stdout_lines.append(text)
        event = _parse_event_line(text.strip())
        if event is not None:
            self._events.append(event)
            if self._event_callback is not None:
                try:
                    self._event_callback(event)
                except Exception:
                    pass

    async def _consume_remaining_stdout(self) -> None:
        """Drain stdout after completion if event streaming stopped early."""
        if self._stdout_consumed:
            return

        if self._process.stdout is not None:
            while True:
                line = await self._process.stdout.readline()
                if line == b"":
                    break
                self._record_stdout_line(line)

        self._stdout_consumed = True

    async def _drain_stderr(self) -> None:
        """Continuously drain stderr in an asyncio task."""
        if self._process.stderr is None:
            return

        while True:
            line = await self._process.stderr.readline()
            if line == b"":
                break
            self._stderr_lines.append(line.decode("utf-8", errors="replace"))


class CodexThreadSession:
    """Convenience handle for continuing a previously started Codex thread.

    You usually get this from `CodexLocalClient.start_thread()` or
    `CodexLocalClient.open_session()`.

    Example:
        session, first = client.start_thread("Create a plan", session_name="planning")
        follow_up = session.continue_prompt("Now write the implementation.")
    """

    def __init__(
        self,
        client: CodexLocalClient,
        session_id: str,
        default_cwd: str | None = None,
        api_key: str | None = None,
        session_name: str | None = None,
    ) -> None:
        """Create a lightweight handle for a resumable Codex thread."""
        self.client = client
        self.session_id = session_id
        self.default_cwd = default_cwd
        self.api_key = api_key
        self.session_name = session_name
        self.last_result: CodexExecResult | None = None

    def continue_prompt(
        self,
        prompt: str,
        json_output: bool = True,
        cwd: str | None = None,
        api_key: str | None = None,
        all_sessions: bool = False,
        timeout_seconds: float | None = None,
    ) -> CodexExecResult:
        """Run a non-live follow-up prompt on this session.

        By default, this uses JSON output for structured terminal metadata.
        """
        result = self.client.resume(
            prompt=prompt,
            session_id=self.session_id if self.session_name is None else None,
            session_name=self.session_name,
            last=False,
            all_sessions=all_sessions,
            json_output=json_output,
            cwd=cwd or self.default_cwd,
            api_key=api_key or self.api_key,
            timeout_seconds=timeout_seconds,
            _operation="continue_prompt",
        )
        self.last_result = result
        return result

    async def continue_prompt_async(
        self,
        prompt: str,
        json_output: bool = True,
        cwd: str | None = None,
        api_key: str | None = None,
        all_sessions: bool = False,
        timeout_seconds: float | None = None,
    ) -> CodexExecResult:
        """Async variant of `continue_prompt`."""
        result = await self.client.resume_async(
            prompt=prompt,
            session_id=self.session_id if self.session_name is None else None,
            session_name=self.session_name,
            last=False,
            all_sessions=all_sessions,
            json_output=json_output,
            cwd=cwd or self.default_cwd,
            api_key=api_key or self.api_key,
            timeout_seconds=timeout_seconds,
            _operation="continue_prompt_async",
        )
        self.last_result = result
        return result

    def continue_live(
        self,
        prompt: str,
        cwd: str | None = None,
        api_key: str | None = None,
        all_sessions: bool = False,
    ) -> CodexLiveRun:
        """Start a live follow-up prompt for this session.

        Live mode always uses JSON output so events can be streamed.
        """
        return self.client.resume_live(
            prompt=prompt,
            session_id=self.session_id if self.session_name is None else None,
            session_name=self.session_name,
            last=False,
            all_sessions=all_sessions,
            cwd=cwd or self.default_cwd,
            api_key=api_key or self.api_key,
            _operation="continue_live",
        )

    async def continue_live_async(
        self,
        prompt: str,
        cwd: str | None = None,
        api_key: str | None = None,
        all_sessions: bool = False,
    ) -> AsyncCodexLiveRun:
        """Async variant of `continue_live`."""
        return await self.client.resume_live_async(
            prompt=prompt,
            session_id=self.session_id if self.session_name is None else None,
            session_name=self.session_name,
            last=False,
            all_sessions=all_sessions,
            cwd=cwd or self.default_cwd,
            api_key=api_key or self.api_key,
            _operation="continue_live_async",
        )

    @property
    def is_last_turn_complete(self) -> bool:
        """Return whether the latest stored result completed successfully."""
        return self.last_result is not None and self.last_result.is_turn_completed


class CodexLocalClient:
    """High-level wrapper around `codex exec` for local non-interactive usage.

    Typical workflow:
    1. Build a request (`CodexExecRequest`) or use a convenience method.
    2. Run once (`run*`) or start/resume a thread (`start_thread*`, `resume*`).
    3. Optionally persist session names with `save_session` and `open_session`.

    Example:
        client = CodexLocalClient()
        result = client.run_prompt("Summarize README", json_output=True)
        print(result.final_message)
    """

    def __init__(
        self,
        codex_bin: str = "codex",
        default_cwd: str | None = None,
        default_env: dict[str, str] | None = None,
        raise_on_error: bool = True,
        retry_policy: RetryPolicy | None = None,
        session_store: SessionStore | None = None,
        event_hook: Callable[[CodexClientEvent], None] | None = None,
    ) -> None:
        """Configure a Codex client with defaults for execution and retries.

        Args:
            codex_bin: CLI executable name or path.
            default_cwd: Working directory fallback when a request does not set `cwd`.
            default_env: Extra environment variables merged into child process env.
            raise_on_error: Raise `CodexExecFailedError` on non-zero command exits.
            retry_policy: Retry/backoff settings for non-live command execution.
            session_store: Named-session persistence backend.
            event_hook: Optional callback for best-effort telemetry events.
        """
        self.codex_bin = codex_bin
        self.default_cwd = default_cwd
        self.default_env = dict(default_env or {})
        self.raise_on_error = raise_on_error
        self.retry_policy = self._normalize_retry_policy(retry_policy or RetryPolicy())
        self.session_store = session_store or InMemorySessionStore()
        self.event_hook = event_hook

    def is_available(self) -> bool:
        """Return `True` when the configured Codex binary is on PATH."""
        return shutil.which(self.codex_bin) is not None

    def run(
        self,
        request: CodexExecRequest,
        api_key: str | None = None,
        timeout_seconds: float | None = None,
    ) -> CodexExecResult:
        """Execute a fully specified request.

        Retries follow `retry_policy`. If `raise_on_error=True`, non-zero exits
        raise `CodexExecFailedError`; otherwise the failed `CodexExecResult`
        is returned.
        """
        cmd = self._build_exec_command(request)
        return self._run_raw_command(
            cmd=cmd,
            cwd=request.cwd or self.default_cwd,
            api_key=api_key,
            json_output=request.json_output,
            error_prefix="Codex command failed",
            timeout_seconds=timeout_seconds,
            operation="run",
        )

    async def run_async(
        self,
        request: CodexExecRequest,
        api_key: str | None = None,
        timeout_seconds: float | None = None,
    ) -> CodexExecResult:
        """Async wrapper for `run` that delegates to a worker thread."""
        return await asyncio.to_thread(self.run, request, api_key, timeout_seconds)

    def run_live(self, request: CodexExecRequest, api_key: str | None = None) -> CodexLiveRun:
        """
        Start a live run with subprocess.Popen and stream events.

        Live mode always uses `--json` so events can be streamed and parsed.
        Retry behavior is limited to startup failures before a live handle exists.
        """
        if not self.is_available():
            raise CodexNotInstalledError(
                f"Could not find `{self.codex_bin}` in PATH. Install Codex CLI first."
            )

        if not request.json_output:
            request = replace(request, json_output=True)

        cmd = self._build_exec_command(request)
        env = self._build_env(api_key=api_key)
        cwd = request.cwd or self.default_cwd

        process = self._start_sync_live_process(
            cmd=cmd,
            cwd=cwd,
            env=env,
            operation="run_live",
            session_name=None,
            session_id=None,
        )

        started = time.monotonic()
        self._emit_event(
            event_type="live.started",
            operation="run_live",
            attempt=1,
            command=tuple(cmd),
            metadata={"pid": process.pid},
        )

        return CodexLiveRun(
            process=process,
            command=cmd,
            started_at=started,
            raise_on_error=self.raise_on_error,
            event_callback=self._make_live_event_callback(
                operation="run_live",
                command=tuple(cmd),
                session_name=None,
                session_id=None,
            ),
        )

    async def run_live_async(self, request: CodexExecRequest, api_key: str | None = None) -> AsyncCodexLiveRun:
        """Async variant of `run_live` with startup-only retry behavior."""
        if not self.is_available():
            raise CodexNotInstalledError(
                f"Could not find `{self.codex_bin}` in PATH. Install Codex CLI first."
            )

        if not request.json_output:
            request = replace(request, json_output=True)

        cmd = self._build_exec_command(request)
        env = self._build_env(api_key=api_key)
        cwd = request.cwd or self.default_cwd

        process = await self._start_async_live_process(
            cmd=cmd,
            cwd=cwd,
            env=env,
            operation="run_live_async",
            session_name=None,
            session_id=None,
        )

        started = time.monotonic()
        self._emit_event(
            event_type="live.started",
            operation="run_live_async",
            attempt=1,
            command=tuple(cmd),
            metadata={"pid": process.pid},
        )

        return AsyncCodexLiveRun(
            process=process,
            command=cmd,
            started_at=started,
            raise_on_error=self.raise_on_error,
            event_callback=self._make_live_event_callback(
                operation="run_live_async",
                command=tuple(cmd),
                session_name=None,
                session_id=None,
            ),
        )

    def run_prompt(
        self,
        prompt: str,
        api_key: str | None = None,
        timeout_seconds: float | None = None,
        **kwargs: object,
    ) -> CodexExecResult:
        """Execute a prompt without manually constructing `CodexExecRequest`.

        Keyword arguments map directly to `CodexExecRequest` fields.
        """
        request = CodexExecRequest(prompt=prompt)
        request = replace(request, **kwargs)
        return self.run(request, api_key=api_key, timeout_seconds=timeout_seconds)

    async def run_prompt_async(
        self,
        prompt: str,
        api_key: str | None = None,
        timeout_seconds: float | None = None,
        **kwargs: object,
    ) -> CodexExecResult:
        """Async variant of `run_prompt`."""
        return await asyncio.to_thread(
            self.run_prompt,
            prompt,
            api_key,
            timeout_seconds,
            **kwargs,
        )

    def run_with_schema(
        self,
        prompt: str,
        schema: dict,
        output_json_path: str | None = None,
        api_key: str | None = None,
        timeout_seconds: float | None = None,
        **kwargs: object,
    ) -> CodexExecResult:
        """Run a prompt with schema-constrained output.

        The schema is written to a temporary file and passed via
        `--output-schema`, then cleaned up automatically.
        """
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
            json.dump(schema, f)
            schema_path = f.name

        try:
            request = CodexExecRequest(prompt=prompt)
            request = replace(
                request,
                output_schema_path=schema_path,
                output_last_message_path=output_json_path,
                **kwargs,
            )
            return self.run(request, api_key=api_key, timeout_seconds=timeout_seconds)
        finally:
            try:
                os.remove(schema_path)
            except OSError:
                pass

    async def run_with_schema_async(
        self,
        prompt: str,
        schema: dict,
        output_json_path: str | None = None,
        api_key: str | None = None,
        timeout_seconds: float | None = None,
        **kwargs: object,
    ) -> CodexExecResult:
        """Async variant of `run_with_schema`."""
        return await asyncio.to_thread(
            self.run_with_schema,
            prompt,
            schema,
            output_json_path,
            api_key,
            timeout_seconds,
            **kwargs,
        )

    def start_thread(
        self,
        prompt: str,
        api_key: str | None = None,
        session_name: str | None = None,
        timeout_seconds: float | None = None,
        **request_overrides: object,
    ) -> tuple[CodexThreadSession, CodexExecResult]:
        """
        Start a new thread and return a `CodexThreadSession` you can continue.

        This enforces `json_output=True` so a thread ID can be extracted.
        Pass `session_name` to persist a logical alias in the configured
        `session_store`.
        """
        request = CodexExecRequest(prompt=prompt, json_output=True)
        request = replace(request, **{**request_overrides, "json_output": True})

        result = self.run(request, api_key=api_key, timeout_seconds=timeout_seconds)
        if result.thread_id is None:
            raise CodexError("Could not extract thread/session ID from Codex events.")

        session = CodexThreadSession(
            client=self,
            session_id=result.thread_id,
            default_cwd=request.cwd or self.default_cwd,
            api_key=api_key,
            session_name=session_name,
        )
        session.last_result = result

        if session_name:
            self._update_session_record(
                session_name=session_name,
                session_id=result.thread_id,
                prompt=prompt,
                result=result,
                operation="start_thread",
            )

        return session, result

    async def start_thread_async(
        self,
        prompt: str,
        api_key: str | None = None,
        session_name: str | None = None,
        timeout_seconds: float | None = None,
        **request_overrides: object,
    ) -> tuple[CodexThreadSession, CodexExecResult]:
        """Async variant of `start_thread`."""
        func = functools.partial(
            self.start_thread,
            prompt,
            api_key=api_key,
            session_name=session_name,
            timeout_seconds=timeout_seconds,
            **request_overrides,
        )
        return await asyncio.to_thread(func)

    def resume(
        self,
        prompt: str,
        session_id: str | None = None,
        session_name: str | None = None,
        last: bool = True,
        all_sessions: bool = False,
        json_output: bool = False,
        cwd: str | None = None,
        api_key: str | None = None,
        timeout_seconds: float | None = None,
        _operation: str = "resume",
    ) -> CodexExecResult:
        """Resume an existing thread by explicit id or stored session name.

        Pass exactly one of `session_id` or `session_name`.
        """
        resolved_session_id = self._resolve_session_id(session_id=session_id, session_name=session_name)

        cmd = self._build_resume_command(
            prompt=prompt,
            session_id=resolved_session_id,
            last=last,
            all_sessions=all_sessions,
            json_output=json_output,
        )

        result = self._run_raw_command(
            cmd=cmd,
            cwd=cwd,
            api_key=api_key,
            json_output=json_output,
            error_prefix="Codex resume failed",
            timeout_seconds=timeout_seconds,
            operation=_operation,
            session_name=session_name,
            session_id=resolved_session_id,
        )

        if session_name and resolved_session_id:
            self._update_session_record(
                session_name=session_name,
                session_id=resolved_session_id,
                prompt=prompt,
                result=result,
                operation=_operation,
            )

        return result

    async def resume_async(
        self,
        prompt: str,
        session_id: str | None = None,
        session_name: str | None = None,
        last: bool = True,
        all_sessions: bool = False,
        json_output: bool = False,
        cwd: str | None = None,
        api_key: str | None = None,
        timeout_seconds: float | None = None,
        _operation: str = "resume_async",
    ) -> CodexExecResult:
        """Async variant of `resume`."""
        func = functools.partial(
            self.resume,
            prompt,
            session_id=session_id,
            session_name=session_name,
            last=last,
            all_sessions=all_sessions,
            json_output=json_output,
            cwd=cwd,
            api_key=api_key,
            timeout_seconds=timeout_seconds,
            _operation=_operation,
        )
        return await asyncio.to_thread(func)

    def resume_live(
        self,
        prompt: str,
        session_id: str | None = None,
        session_name: str | None = None,
        last: bool = True,
        all_sessions: bool = False,
        cwd: str | None = None,
        api_key: str | None = None,
        _operation: str = "resume_live",
    ) -> CodexLiveRun:
        """Resume a thread in live event-streaming mode.

        JSON output is always enabled in live mode.
        """
        resolved_session_id = self._resolve_session_id(session_id=session_id, session_name=session_name)

        cmd = self._build_resume_command(
            prompt=prompt,
            session_id=resolved_session_id,
            last=last,
            all_sessions=all_sessions,
            json_output=True,
        )

        if not self.is_available():
            raise CodexNotInstalledError(
                f"Could not find `{self.codex_bin}` in PATH. Install Codex CLI first."
            )

        env = self._build_env(api_key=api_key)
        process = self._start_sync_live_process(
            cmd=cmd,
            cwd=cwd or self.default_cwd,
            env=env,
            operation=_operation,
            session_name=session_name,
            session_id=resolved_session_id,
        )

        started = time.monotonic()
        self._emit_event(
            event_type="live.started",
            operation=_operation,
            attempt=1,
            command=tuple(cmd),
            session_name=session_name,
            session_id=resolved_session_id,
            metadata={"pid": process.pid},
        )

        return CodexLiveRun(
            process=process,
            command=cmd,
            started_at=started,
            raise_on_error=self.raise_on_error,
            event_callback=self._make_live_event_callback(
                operation=_operation,
                command=tuple(cmd),
                session_name=session_name,
                session_id=resolved_session_id,
            ),
            result_callback=self._make_session_result_callback(
                operation=_operation,
                session_name=session_name,
                session_id=resolved_session_id,
                prompt=prompt,
            ),
        )

    async def resume_live_async(
        self,
        prompt: str,
        session_id: str | None = None,
        session_name: str | None = None,
        last: bool = True,
        all_sessions: bool = False,
        cwd: str | None = None,
        api_key: str | None = None,
        _operation: str = "resume_live_async",
    ) -> AsyncCodexLiveRun:
        """Async variant of `resume_live`."""
        resolved_session_id = self._resolve_session_id(session_id=session_id, session_name=session_name)

        cmd = self._build_resume_command(
            prompt=prompt,
            session_id=resolved_session_id,
            last=last,
            all_sessions=all_sessions,
            json_output=True,
        )

        if not self.is_available():
            raise CodexNotInstalledError(
                f"Could not find `{self.codex_bin}` in PATH. Install Codex CLI first."
            )

        env = self._build_env(api_key=api_key)
        process = await self._start_async_live_process(
            cmd=cmd,
            cwd=cwd or self.default_cwd,
            env=env,
            operation=_operation,
            session_name=session_name,
            session_id=resolved_session_id,
        )

        started = time.monotonic()
        self._emit_event(
            event_type="live.started",
            operation=_operation,
            attempt=1,
            command=tuple(cmd),
            session_name=session_name,
            session_id=resolved_session_id,
            metadata={"pid": process.pid},
        )

        return AsyncCodexLiveRun(
            process=process,
            command=cmd,
            started_at=started,
            raise_on_error=self.raise_on_error,
            event_callback=self._make_live_event_callback(
                operation=_operation,
                command=tuple(cmd),
                session_name=session_name,
                session_id=resolved_session_id,
            ),
            result_callback=self._make_session_result_callback(
                operation=_operation,
                session_name=session_name,
                session_id=resolved_session_id,
                prompt=prompt,
            ),
        )

    def save_session(self, name: str, session_id: str) -> None:
        """Persist a logical session name for later resume calls.

        Use this when you want friendly aliases like `"release-planning"` instead
        of passing raw thread IDs everywhere.
        """
        self.session_store.set(name, session_id)

    def get_session_id(self, name: str) -> str | None:
        """Return the stored session id for a logical name, if present."""
        return self.session_store.get(name)

    def delete_session(self, name: str) -> None:
        """Delete a stored logical session mapping."""
        self.session_store.delete(name)

    def list_sessions(self) -> dict[str, str]:
        """List all stored logical session mappings."""
        return self.session_store.all()

    def get_session_record(self, name: str) -> SessionRecord | None:
        """Return full persisted metadata for a named session."""
        return self.session_store.get_record(name)

    def list_session_records(self) -> dict[str, SessionRecord]:
        """Return all stored session records with metadata."""
        return self.session_store.list_records()

    def open_session(
        self,
        name: str,
        default_cwd: str | None = None,
        api_key: str | None = None,
    ) -> CodexThreadSession:
        """Open a `CodexThreadSession` from a previously saved session name.

        This is a convenience around `get_session_id` plus `CodexThreadSession`.
        """
        session_id = self.get_session_id(name)
        if not session_id:
            raise CodexError(f"No stored session found for name '{name}'.")

        return CodexThreadSession(
            client=self,
            session_id=session_id,
            default_cwd=default_cwd or self.default_cwd,
            api_key=api_key,
            session_name=name,
        )

    def _run_raw_command(
        self,
        cmd: list[str],
        cwd: str | None,
        api_key: str | None,
        json_output: bool,
        error_prefix: str,
        timeout_seconds: float | None,
        operation: str,
        session_name: str | None = None,
        session_id: str | None = None,
    ) -> CodexExecResult:
        """Execute a command with retry logic, timeout handling, and telemetry."""
        if not self.is_available():
            raise CodexNotInstalledError(
                f"Could not find `{self.codex_bin}` in PATH. Install Codex CLI first."
            )

        env = self._build_env(api_key=api_key)
        attempt = 1
        retry_started_at = time.monotonic()

        while True:
            self._emit_event(
                event_type="attempt.started",
                operation=operation,
                attempt=attempt,
                command=tuple(cmd),
                session_name=session_name,
                session_id=session_id,
            )

            started = time.monotonic()
            try:
                completed = subprocess.run(
                    cmd,
                    cwd=cwd or self.default_cwd,
                    env=env,
                    text=True,
                    capture_output=True,
                    check=False,
                    timeout=timeout_seconds,
                )
                duration = time.monotonic() - started

                result = _build_result(
                    return_code=completed.returncode,
                    command=cmd,
                    stdout=completed.stdout,
                    stderr=completed.stderr,
                    duration_seconds=duration,
                    json_output=json_output,
                )
            except subprocess.TimeoutExpired as exc:
                duration = time.monotonic() - started
                result = self._build_timeout_result(
                    cmd=cmd,
                    duration_seconds=duration,
                    json_output=json_output,
                    timeout_seconds=timeout_seconds,
                    exc=exc,
                )
            except (OSError, subprocess.SubprocessError) as exc:
                self._emit_event(
                    event_type="attempt.failed",
                    operation=operation,
                    attempt=attempt,
                    command=tuple(cmd),
                    session_name=session_name,
                    session_id=session_id,
                    message=str(exc),
                )

                if self._should_retry(attempt=attempt, exception=exc, retry_started_at=retry_started_at):
                    retry_delay = self._compute_retry_delay(attempt=attempt, retry_started_at=retry_started_at)
                    self._emit_event(
                        event_type="retry.scheduled",
                        operation=operation,
                        attempt=attempt,
                        command=tuple(cmd),
                        session_name=session_name,
                        session_id=session_id,
                        retry_delay_seconds=retry_delay,
                        message=str(exc),
                    )
                    if retry_delay > 0:
                        self._sleep_backoff(retry_delay)
                    attempt += 1
                    continue

                raise CodexError(f"{error_prefix}: {exc}") from exc

            if result.ok:
                self._emit_event(
                    event_type="attempt.succeeded",
                    operation=operation,
                    attempt=attempt,
                    command=tuple(cmd),
                    session_name=session_name,
                    session_id=session_id,
                    return_code=result.return_code,
                    turn_status=result.turn_status,
                    duration_seconds=result.duration_seconds,
                )
                return result

            self._emit_event(
                event_type="attempt.failed",
                operation=operation,
                attempt=attempt,
                command=tuple(cmd),
                session_name=session_name,
                session_id=session_id,
                return_code=result.return_code,
                turn_status=result.turn_status,
                duration_seconds=result.duration_seconds,
                message=result.stderr.strip() or None,
            )

            if self._should_retry(attempt=attempt, result=result, retry_started_at=retry_started_at):
                retry_delay = self._compute_retry_delay(attempt=attempt, retry_started_at=retry_started_at)
                self._emit_event(
                    event_type="retry.scheduled",
                    operation=operation,
                    attempt=attempt,
                    command=tuple(cmd),
                    session_name=session_name,
                    session_id=session_id,
                    retry_delay_seconds=retry_delay,
                    return_code=result.return_code,
                    turn_status=result.turn_status,
                )
                if retry_delay > 0:
                    self._sleep_backoff(retry_delay)
                attempt += 1
                continue

            if self.raise_on_error and not result.ok:
                raise CodexExecFailedError(
                    f"{error_prefix} with exit code {result.return_code}.",
                    result=result,
                )

            return result

    def _build_timeout_result(
        self,
        cmd: list[str],
        duration_seconds: float,
        json_output: bool,
        timeout_seconds: float | None,
        exc: subprocess.TimeoutExpired,
    ) -> CodexExecResult:
        """Build a synthetic timeout result that follows normal result shape."""
        stdout = _coerce_subprocess_output(getattr(exc, "stdout", ""))
        stderr = _coerce_subprocess_output(getattr(exc, "stderr", ""))
        timeout_label = timeout_seconds if timeout_seconds is not None else "unknown"
        timeout_message = f"{_TIMEOUT_MARKER}: command timed out after {timeout_label} seconds."
        combined_stderr = timeout_message if not stderr else f"{timeout_message}\n{stderr}"

        return _build_result(
            return_code=124,
            command=cmd,
            stdout=stdout,
            stderr=combined_stderr,
            duration_seconds=duration_seconds,
            json_output=json_output,
        )

    def _is_timeout_result(self, result: CodexExecResult) -> bool:
        """Return `True` when the result was generated from a timeout path."""
        return _TIMEOUT_MARKER in result.stderr

    def _should_retry(
        self,
        attempt: int,
        result: CodexExecResult | None = None,
        exception: BaseException | None = None,
        retry_started_at: float | None = None,
    ) -> bool:
        """Decide whether another attempt is allowed under policy constraints."""
        if attempt >= self.retry_policy.max_attempts:
            return False

        max_total = self.retry_policy.max_total_retry_seconds
        if max_total is not None and retry_started_at is not None:
            elapsed = time.monotonic() - retry_started_at
            if elapsed >= max_total:
                return False

        if exception is not None:
            return self._is_retryable_exception(exception)

        if result is None or result.ok:
            return False

        if self._is_timeout_result(result) and not self.retry_policy.retry_on_timeouts:
            return False

        exit_codes = self.retry_policy.retry_on_exit_codes
        if exit_codes is None:
            return True

        return result.return_code in exit_codes

    def _is_retryable_exception(self, exception: BaseException) -> bool:
        """Return whether an exception type is retryable."""
        return isinstance(exception, (OSError, subprocess.SubprocessError))

    def _compute_retry_delay(self, attempt: int, retry_started_at: float | None = None) -> float:
        """Compute exponential backoff delay with jitter and max-total cap."""
        exponent = max(0, attempt - 1)
        base_delay = self.retry_policy.initial_backoff_seconds * (self.retry_policy.backoff_multiplier**exponent)
        delay = min(base_delay, self.retry_policy.max_backoff_seconds)

        if delay > 0 and self.retry_policy.jitter_ratio > 0:
            jitter_span = delay * self.retry_policy.jitter_ratio
            delay += random.uniform(-jitter_span, jitter_span)
            if delay < 0:
                delay = 0.0

        max_total = self.retry_policy.max_total_retry_seconds
        if max_total is not None and retry_started_at is not None:
            remaining = max_total - (time.monotonic() - retry_started_at)
            if remaining <= 0:
                return 0.0
            delay = min(delay, remaining)

        return delay

    def _sleep_backoff(self, seconds: float) -> None:
        """Sleep for retry backoff if delay is positive."""
        if seconds <= 0:
            return
        time.sleep(seconds)

    def _normalize_retry_policy(self, retry_policy: RetryPolicy) -> RetryPolicy:
        """Clamp retry policy values into safe, non-negative ranges."""
        max_attempts = max(1, retry_policy.max_attempts)
        initial_backoff_seconds = max(0.0, retry_policy.initial_backoff_seconds)
        backoff_multiplier = retry_policy.backoff_multiplier
        if backoff_multiplier < 1.0:
            backoff_multiplier = 1.0
        max_backoff_seconds = max(initial_backoff_seconds, retry_policy.max_backoff_seconds)

        jitter_ratio = max(0.0, retry_policy.jitter_ratio)
        max_total_retry_seconds = retry_policy.max_total_retry_seconds
        if max_total_retry_seconds is not None and max_total_retry_seconds <= 0:
            max_total_retry_seconds = None

        return RetryPolicy(
            max_attempts=max_attempts,
            initial_backoff_seconds=initial_backoff_seconds,
            backoff_multiplier=backoff_multiplier,
            max_backoff_seconds=max_backoff_seconds,
            retry_on_exit_codes=retry_policy.retry_on_exit_codes,
            jitter_ratio=jitter_ratio,
            max_total_retry_seconds=max_total_retry_seconds,
            retry_on_timeouts=bool(retry_policy.retry_on_timeouts),
        )

    def _start_sync_live_process(
        self,
        cmd: list[str],
        cwd: str | None,
        env: dict[str, str],
        operation: str,
        session_name: str | None,
        session_id: str | None,
    ) -> subprocess.Popen[str]:
        """Start sync live mode with retries limited to startup failures."""
        attempt = 1
        retry_started_at = time.monotonic()

        while True:
            try:
                process = subprocess.Popen(
                    cmd,
                    cwd=cwd,
                    env=env,
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    bufsize=1,
                )
            except (OSError, subprocess.SubprocessError) as exc:
                self._emit_event(
                    event_type="live.startup_failed",
                    operation=operation,
                    attempt=attempt,
                    command=tuple(cmd),
                    session_name=session_name,
                    session_id=session_id,
                    message=str(exc),
                )

                if self._should_retry(attempt=attempt, exception=exc, retry_started_at=retry_started_at):
                    retry_delay = self._compute_retry_delay(attempt=attempt, retry_started_at=retry_started_at)
                    self._emit_event(
                        event_type="live.startup_retried",
                        operation=operation,
                        attempt=attempt,
                        command=tuple(cmd),
                        session_name=session_name,
                        session_id=session_id,
                        retry_delay_seconds=retry_delay,
                        message=str(exc),
                    )
                    self._sleep_backoff(retry_delay)
                    attempt += 1
                    continue

                raise CodexError(f"{operation} startup failed: {exc}") from exc

            startup_rc = self._probe_sync_process_exit(process, _LIVE_STARTUP_PROBE_SECONDS)
            if startup_rc is not None:
                probe_result = CodexExecResult(
                    return_code=startup_rc,
                    command=tuple(cmd),
                    stdout="",
                    stderr="",
                    final_message=None,
                )
                self._emit_event(
                    event_type="live.startup_failed",
                    operation=operation,
                    attempt=attempt,
                    command=tuple(cmd),
                    session_name=session_name,
                    session_id=session_id,
                    return_code=startup_rc,
                    message="process exited during startup probe",
                )

                if self._should_retry(attempt=attempt, result=probe_result, retry_started_at=retry_started_at):
                    self._best_effort_collect_sync_process(process)
                    retry_delay = self._compute_retry_delay(attempt=attempt, retry_started_at=retry_started_at)
                    self._emit_event(
                        event_type="live.startup_retried",
                        operation=operation,
                        attempt=attempt,
                        command=tuple(cmd),
                        session_name=session_name,
                        session_id=session_id,
                        return_code=startup_rc,
                        retry_delay_seconds=retry_delay,
                    )
                    self._sleep_backoff(retry_delay)
                    attempt += 1
                    continue

            return process

    async def _start_async_live_process(
        self,
        cmd: list[str],
        cwd: str | None,
        env: dict[str, str],
        operation: str,
        session_name: str | None,
        session_id: str | None,
    ) -> asyncio.subprocess.Process:
        """Async variant of `_start_sync_live_process`."""
        attempt = 1
        retry_started_at = time.monotonic()

        while True:
            try:
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    cwd=cwd,
                    env=env,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
            except (OSError, subprocess.SubprocessError) as exc:
                self._emit_event(
                    event_type="live.startup_failed",
                    operation=operation,
                    attempt=attempt,
                    command=tuple(cmd),
                    session_name=session_name,
                    session_id=session_id,
                    message=str(exc),
                )

                if self._should_retry(attempt=attempt, exception=exc, retry_started_at=retry_started_at):
                    retry_delay = self._compute_retry_delay(attempt=attempt, retry_started_at=retry_started_at)
                    self._emit_event(
                        event_type="live.startup_retried",
                        operation=operation,
                        attempt=attempt,
                        command=tuple(cmd),
                        session_name=session_name,
                        session_id=session_id,
                        retry_delay_seconds=retry_delay,
                        message=str(exc),
                    )
                    if retry_delay > 0:
                        await asyncio.sleep(retry_delay)
                    attempt += 1
                    continue

                raise CodexError(f"{operation} startup failed: {exc}") from exc

            startup_rc = await self._probe_async_process_exit(process, _LIVE_STARTUP_PROBE_SECONDS)
            if startup_rc is not None:
                probe_result = CodexExecResult(
                    return_code=startup_rc,
                    command=tuple(cmd),
                    stdout="",
                    stderr="",
                    final_message=None,
                )
                self._emit_event(
                    event_type="live.startup_failed",
                    operation=operation,
                    attempt=attempt,
                    command=tuple(cmd),
                    session_name=session_name,
                    session_id=session_id,
                    return_code=startup_rc,
                    message="process exited during startup probe",
                )

                if self._should_retry(attempt=attempt, result=probe_result, retry_started_at=retry_started_at):
                    await self._best_effort_collect_async_process(process)
                    retry_delay = self._compute_retry_delay(attempt=attempt, retry_started_at=retry_started_at)
                    self._emit_event(
                        event_type="live.startup_retried",
                        operation=operation,
                        attempt=attempt,
                        command=tuple(cmd),
                        session_name=session_name,
                        session_id=session_id,
                        return_code=startup_rc,
                        retry_delay_seconds=retry_delay,
                    )
                    if retry_delay > 0:
                        await asyncio.sleep(retry_delay)
                    attempt += 1
                    continue

            return process

    def _probe_sync_process_exit(self, process: subprocess.Popen[str], window_seconds: float) -> int | None:
        """Probe briefly for an immediate startup exit code."""
        deadline = time.monotonic() + window_seconds
        while time.monotonic() < deadline:
            return_code = process.poll()
            if return_code is not None:
                return return_code
            time.sleep(_LIVE_STARTUP_PROBE_INTERVAL_SECONDS)
        return process.poll()

    async def _probe_async_process_exit(self, process: asyncio.subprocess.Process, window_seconds: float) -> int | None:
        """Async variant of `_probe_sync_process_exit`."""
        deadline = time.monotonic() + window_seconds
        while time.monotonic() < deadline:
            return_code = process.returncode
            if return_code is not None:
                return return_code
            await asyncio.sleep(_LIVE_STARTUP_PROBE_INTERVAL_SECONDS)
        return process.returncode

    def _best_effort_collect_sync_process(self, process: subprocess.Popen[str]) -> None:
        """Drain process pipes after startup failure without raising."""
        try:
            process.communicate(timeout=0.2)
        except Exception:
            pass

    async def _best_effort_collect_async_process(self, process: asyncio.subprocess.Process) -> None:
        """Async variant of `_best_effort_collect_sync_process`."""
        try:
            await asyncio.wait_for(process.communicate(), timeout=0.2)
        except Exception:
            pass

    def _make_live_event_callback(
        self,
        operation: str,
        command: tuple[str, ...],
        session_name: str | None,
        session_id: str | None,
    ) -> Callable[[CodexEvent], None]:
        """Create a callback that forwards live-event telemetry to `event_hook`."""
        def callback(event: CodexEvent) -> None:
            self._emit_event(
                event_type="live.event",
                operation=operation,
                command=command,
                session_name=session_name,
                session_id=session_id,
                metadata={"event_type": event.type},
            )

        return callback

    def _make_session_result_callback(
        self,
        operation: str,
        session_name: str | None,
        session_id: str | None,
        prompt: str,
    ) -> Callable[[CodexExecResult], None] | None:
        """Create a callback that updates persistent session metadata."""
        if session_name is None or session_id is None:
            return None

        def callback(result: CodexExecResult) -> None:
            self._update_session_record(
                session_name=session_name,
                session_id=session_id,
                prompt=prompt,
                result=result,
                operation=operation,
            )

        return callback

    def _update_session_record(
        self,
        session_name: str,
        session_id: str,
        prompt: str,
        result: CodexExecResult,
        operation: str,
    ) -> None:
        """Append a turn summary and refresh counters for a named session."""
        existing = self.session_store.get_record(session_name)
        now = time.time()

        if existing is None:
            created_at = now
            turn_count = 0
            success_count = 0
            failure_count = 0
            turns: list[SessionTurnRecord] = []
        else:
            created_at = existing.created_at
            turn_count = existing.turn_count
            success_count = existing.success_count
            failure_count = existing.failure_count
            turns = list(existing.turns)

        turn_count += 1
        if result.ok and not result.is_turn_failed:
            success_count += 1
        else:
            failure_count += 1

        turns.append(
            SessionTurnRecord(
                timestamp=now,
                operation=operation,
                prompt_preview=_preview(prompt, _PROMPT_PREVIEW_LIMIT),
                return_code=result.return_code,
                turn_status=result.turn_status,
                duration_seconds=result.duration_seconds,
                message_preview=_preview(result.final_message, _MESSAGE_PREVIEW_LIMIT),
            )
        )

        record = SessionRecord(
            session_id=session_id,
            session_name=session_name,
            created_at=created_at,
            updated_at=now,
            last_turn_status=result.turn_status,
            turn_count=turn_count,
            success_count=success_count,
            failure_count=failure_count,
            turns=tuple(turns),
        )
        self.session_store.set_record(session_name, record)

        self._emit_event(
            event_type="session.updated",
            operation=operation,
            session_name=session_name,
            session_id=session_id,
            return_code=result.return_code,
            turn_status=result.turn_status,
            duration_seconds=result.duration_seconds,
            metadata={
                "turn_count": turn_count,
                "success_count": success_count,
                "failure_count": failure_count,
            },
        )

    def _emit_event(
        self,
        event_type: str,
        operation: str,
        attempt: int | None = None,
        command: tuple[str, ...] | None = None,
        session_name: str | None = None,
        session_id: str | None = None,
        retry_delay_seconds: float | None = None,
        return_code: int | None = None,
        turn_status: str | None = None,
        duration_seconds: float | None = None,
        message: str | None = None,
        metadata: dict | None = None,
    ) -> None:
        """Emit a best-effort telemetry callback event."""
        if self.event_hook is None:
            return

        event = CodexClientEvent(
            type=event_type,
            operation=operation,
            attempt=attempt,
            command=command,
            session_name=session_name,
            session_id=session_id,
            retry_delay_seconds=retry_delay_seconds,
            return_code=return_code,
            turn_status=turn_status,
            duration_seconds=duration_seconds,
            message=message,
            metadata=dict(metadata or {}),
        )
        try:
            self.event_hook(event)
        except Exception:
            pass

    def _resolve_session_id(
        self,
        session_id: str | None,
        session_name: str | None,
    ) -> str | None:
        """Resolve explicit or stored session identifier with validation."""
        if session_id and session_name:
            raise CodexError("Pass either session_id or session_name, not both.")

        if session_id:
            return session_id

        if session_name:
            stored = self.get_session_id(session_name)
            if not stored:
                raise CodexError(f"No stored session found for name '{session_name}'.")
            return stored

        return None

    def _build_resume_command(
        self,
        prompt: str,
        session_id: str | None,
        last: bool,
        all_sessions: bool,
        json_output: bool,
    ) -> list[str]:
        """Build a `codex exec resume` CLI command."""
        cmd = [self.codex_bin, "exec", "resume"]

        if session_id:
            cmd.append(session_id)
        elif last:
            cmd.append("--last")

        if all_sessions:
            cmd.append("--all")

        if json_output:
            cmd.append("--json")

        cmd.append(prompt)
        return cmd

    def _build_exec_command(self, request: CodexExecRequest) -> list[str]:
        """Build a `codex exec` command from request options."""
        cmd = [self.codex_bin, "exec"]

        if request.json_output:
            cmd.append("--json")
        if request.model:
            cmd.extend(["--model", request.model])
        if request.profile:
            cmd.extend(["--profile", request.profile])
        if request.sandbox:
            cmd.extend(["--sandbox", request.sandbox.value])
        if request.full_auto:
            cmd.append("--full-auto")
        if request.ephemeral:
            cmd.append("--ephemeral")
        if request.skip_git_repo_check:
            cmd.append("--skip-git-repo-check")
        if request.output_schema_path:
            cmd.extend(["--output-schema", request.output_schema_path])
        if request.output_last_message_path:
            cmd.extend(["--output-last-message", request.output_last_message_path])

        for image_path in request.images:
            cmd.extend(["--image", image_path])

        cmd.extend(request.extra_args)
        cmd.append(request.prompt)
        return cmd

    def _build_env(self, api_key: str | None = None) -> dict[str, str]:
        """Build subprocess environment merged with defaults and API key."""
        env = os.environ.copy()
        env.update(self.default_env)
        if api_key:
            env["CODEX_API_KEY"] = api_key
        return env
