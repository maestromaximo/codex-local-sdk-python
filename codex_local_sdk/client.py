from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import threading
import time
from dataclasses import replace
from typing import Iterator

from .exceptions import CodexError, CodexExecFailedError, CodexNotInstalledError
from .models import CodexEvent, CodexExecRequest, CodexExecResult


def _parse_event_line(line: str) -> CodexEvent | None:
    payload: dict
    try:
        payload = json.loads(line)
    except json.JSONDecodeError:
        return None
    event_type = payload.get("type", "unknown")
    return CodexEvent(type=str(event_type), raw=payload)


def _parse_jsonl_events(stdout: str) -> tuple[CodexEvent, ...]:
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


class CodexLiveRun:
    """Represents an active `codex exec --json` process started with Popen."""

    def __init__(
        self,
        process: subprocess.Popen[str],
        command: list[str],
        started_at: float,
        raise_on_error: bool,
    ) -> None:
        self._process = process
        self.command = tuple(command)
        self._started_at = started_at
        self._raise_on_error = raise_on_error

        self._stdout_lines: list[str] = []
        self._stderr_lines: list[str] = []
        self._events: list[CodexEvent] = []

        self._stdout_consumed = False
        self._result_cache: CodexExecResult | None = None

        self._stderr_thread = threading.Thread(target=self._drain_stderr, daemon=True)
        self._stderr_thread.start()

    @property
    def pid(self) -> int:
        return self._process.pid

    @property
    def events(self) -> tuple[CodexEvent, ...]:
        return tuple(self._events)

    @property
    def is_complete(self) -> bool:
        return self._process.poll() is not None

    @property
    def return_code(self) -> int | None:
        return self._process.poll()

    def iter_events(self) -> Iterator[CodexEvent]:
        """Yield JSONL events as they arrive while the process is running."""
        if self._stdout_consumed:
            return

        if self._process.stdout is None:
            self._stdout_consumed = True
            return

        while True:
            line = self._process.stdout.readline()
            if line == "" and self._process.poll() is not None:
                break
            if not line:
                continue
            self._record_stdout_line(line)
            if self._events:
                yield self._events[-1]

        self._stdout_consumed = True

    def wait(self, timeout: float | None = None) -> CodexExecResult:
        self._process.wait(timeout=timeout)
        return self.result()

    def terminate(self) -> None:
        self._process.terminate()

    def kill(self) -> None:
        self._process.kill()

    def result(self) -> CodexExecResult:
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

        if self._raise_on_error and not result.ok:
            raise CodexExecFailedError(
                f"Codex live command failed with exit code {result.return_code}.",
                result=result,
            )

        self._result_cache = result
        return result

    def _record_stdout_line(self, line: str) -> None:
        self._stdout_lines.append(line)
        event = _parse_event_line(line.strip())
        if event is not None:
            self._events.append(event)

    def _consume_remaining_stdout(self) -> None:
        if self._stdout_consumed:
            return

        if self._process.stdout is not None:
            for line in self._process.stdout:
                self._record_stdout_line(line)

        self._stdout_consumed = True

    def _drain_stderr(self) -> None:
        if self._process.stderr is None:
            return
        for line in self._process.stderr:
            self._stderr_lines.append(line)


class CodexThreadSession:
    """Represents a resumable non-interactive Codex exec session (thread)."""

    def __init__(
        self,
        client: CodexLocalClient,
        session_id: str,
        default_cwd: str | None = None,
        api_key: str | None = None,
    ) -> None:
        self.client = client
        self.session_id = session_id
        self.default_cwd = default_cwd
        self.api_key = api_key
        self.last_result: CodexExecResult | None = None

    def continue_prompt(
        self,
        prompt: str,
        json_output: bool = True,
        cwd: str | None = None,
        api_key: str | None = None,
        all_sessions: bool = False,
    ) -> CodexExecResult:
        result = self.client.resume(
            prompt=prompt,
            session_id=self.session_id,
            last=False,
            all_sessions=all_sessions,
            json_output=json_output,
            cwd=cwd or self.default_cwd,
            api_key=api_key or self.api_key,
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
        return self.client.resume_live(
            prompt=prompt,
            session_id=self.session_id,
            last=False,
            all_sessions=all_sessions,
            cwd=cwd or self.default_cwd,
            api_key=api_key or self.api_key,
        )

    @property
    def is_last_turn_complete(self) -> bool:
        return self.last_result is not None and self.last_result.is_turn_completed


class CodexLocalClient:
    """High-level wrapper around `codex exec` for local non-interactive usage."""

    def __init__(
        self,
        codex_bin: str = "codex",
        default_cwd: str | None = None,
        default_env: dict[str, str] | None = None,
        raise_on_error: bool = True,
    ) -> None:
        self.codex_bin = codex_bin
        self.default_cwd = default_cwd
        self.default_env = dict(default_env or {})
        self.raise_on_error = raise_on_error

    def is_available(self) -> bool:
        return shutil.which(self.codex_bin) is not None

    def run(self, request: CodexExecRequest, api_key: str | None = None) -> CodexExecResult:
        if not self.is_available():
            raise CodexNotInstalledError(
                f"Could not find `{self.codex_bin}` in PATH. Install Codex CLI first."
            )

        cmd = self._build_exec_command(request)
        env = self._build_env(api_key=api_key)
        cwd = request.cwd or self.default_cwd

        started = time.monotonic()
        completed = subprocess.run(
            cmd,
            cwd=cwd,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )
        duration = time.monotonic() - started

        result = _build_result(
            return_code=completed.returncode,
            command=cmd,
            stdout=completed.stdout,
            stderr=completed.stderr,
            duration_seconds=duration,
            json_output=request.json_output,
        )

        if self.raise_on_error and not result.ok:
            raise CodexExecFailedError(
                f"Codex command failed with exit code {result.return_code}.",
                result=result,
            )

        return result

    def run_live(self, request: CodexExecRequest, api_key: str | None = None) -> CodexLiveRun:
        """
        Start a live run with subprocess.Popen and stream events.

        Live mode always uses `--json` so events can be streamed and parsed.
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
        started = time.monotonic()

        process = subprocess.Popen(
            cmd,
            cwd=cwd,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=1,
        )

        return CodexLiveRun(
            process=process,
            command=cmd,
            started_at=started,
            raise_on_error=self.raise_on_error,
        )

    def run_prompt(self, prompt: str, **kwargs: object) -> CodexExecResult:
        request = CodexExecRequest(prompt=prompt)
        request = replace(request, **kwargs)
        return self.run(request)

    def run_with_schema(
        self,
        prompt: str,
        schema: dict,
        output_json_path: str | None = None,
        **kwargs: object,
    ) -> CodexExecResult:
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
            return self.run(request)
        finally:
            try:
                os.remove(schema_path)
            except OSError:
                pass

    def start_thread(
        self,
        prompt: str,
        api_key: str | None = None,
        **request_overrides: object,
    ) -> tuple[CodexThreadSession, CodexExecResult]:
        """
        Start a new session and return a `CodexThreadSession` you can continue.

        This enforces `json_output=True` so the session/thread ID can be captured.
        """
        request = CodexExecRequest(prompt=prompt, json_output=True)
        request = replace(request, **{**request_overrides, "json_output": True})

        result = self.run(request, api_key=api_key)
        if result.thread_id is None:
            raise CodexError("Could not extract thread/session ID from Codex events.")

        session = CodexThreadSession(
            client=self,
            session_id=result.thread_id,
            default_cwd=request.cwd or self.default_cwd,
            api_key=api_key,
        )
        session.last_result = result
        return session, result

    def resume(
        self,
        prompt: str,
        session_id: str | None = None,
        last: bool = True,
        all_sessions: bool = False,
        json_output: bool = False,
        cwd: str | None = None,
        api_key: str | None = None,
    ) -> CodexExecResult:
        cmd = self._build_resume_command(
            prompt=prompt,
            session_id=session_id,
            last=last,
            all_sessions=all_sessions,
            json_output=json_output,
        )

        return self._run_raw_command(
            cmd=cmd,
            cwd=cwd,
            api_key=api_key,
            json_output=json_output,
            error_prefix="Codex resume failed",
        )

    def resume_live(
        self,
        prompt: str,
        session_id: str | None = None,
        last: bool = True,
        all_sessions: bool = False,
        cwd: str | None = None,
        api_key: str | None = None,
    ) -> CodexLiveRun:
        cmd = self._build_resume_command(
            prompt=prompt,
            session_id=session_id,
            last=last,
            all_sessions=all_sessions,
            json_output=True,
        )

        if not self.is_available():
            raise CodexNotInstalledError(
                f"Could not find `{self.codex_bin}` in PATH. Install Codex CLI first."
            )

        env = self._build_env(api_key=api_key)
        started = time.monotonic()
        process = subprocess.Popen(
            cmd,
            cwd=cwd or self.default_cwd,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=1,
        )

        return CodexLiveRun(
            process=process,
            command=cmd,
            started_at=started,
            raise_on_error=self.raise_on_error,
        )

    def _run_raw_command(
        self,
        cmd: list[str],
        cwd: str | None,
        api_key: str | None,
        json_output: bool,
        error_prefix: str,
    ) -> CodexExecResult:
        if not self.is_available():
            raise CodexNotInstalledError(
                f"Could not find `{self.codex_bin}` in PATH. Install Codex CLI first."
            )

        env = self._build_env(api_key=api_key)
        started = time.monotonic()
        completed = subprocess.run(
            cmd,
            cwd=cwd or self.default_cwd,
            env=env,
            text=True,
            capture_output=True,
            check=False,
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

        if self.raise_on_error and not result.ok:
            raise CodexExecFailedError(
                f"{error_prefix} with exit code {result.return_code}.",
                result=result,
            )

        return result

    def _build_resume_command(
        self,
        prompt: str,
        session_id: str | None,
        last: bool,
        all_sessions: bool,
        json_output: bool,
    ) -> list[str]:
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
        env = os.environ.copy()
        env.update(self.default_env)
        if api_key:
            env["CODEX_API_KEY"] = api_key
        return env
