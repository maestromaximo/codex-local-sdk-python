import io
import json
import subprocess
import tempfile
import threading
import time
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from codex_local_sdk import (
    CodexExecRequest,
    CodexLocalClient,
    InMemorySessionStore,
    JsonFileSessionStore,
    RetryPolicy,
)


class _StartupProcess:
    def __init__(
        self,
        poll_sequence,
        stdout_text: str = "",
        stderr_text: str = "",
        wait_return_code: int = 0,
        pid: int = 5050,
    ):
        self._poll_sequence = list(poll_sequence)
        self.pid = pid
        self.returncode = None
        self._wait_return_code = wait_return_code
        self.stdout = io.StringIO(stdout_text)
        self.stderr = io.StringIO(stderr_text)

    def poll(self):
        if self._poll_sequence:
            value = self._poll_sequence.pop(0)
            if value is not None:
                self.returncode = value
            return value
        return self.returncode

    def communicate(self, timeout=None):
        return self.stdout.read(), self.stderr.read()

    def wait(self, timeout=None):
        self._poll_sequence = []
        self.returncode = self._wait_return_code
        return self.returncode

    def terminate(self):
        self.returncode = -15

    def kill(self):
        self.returncode = -9


class _FakeAsyncStream:
    def __init__(self, text: str):
        self._lines = [line.encode("utf-8") for line in text.splitlines(keepends=True)]
        self._idx = 0

    async def readline(self):
        if self._idx >= len(self._lines):
            return b""
        line = self._lines[self._idx]
        self._idx += 1
        return line


class _AsyncStartupProcess:
    def __init__(self, returncode=None, stdout_text="", stderr_text="", pid=9090):
        self.pid = pid
        self.returncode = returncode
        self.stdout = _FakeAsyncStream(stdout_text)
        self.stderr = _FakeAsyncStream(stderr_text)

    async def wait(self):
        if self.returncode is None:
            self.returncode = 0
        return self.returncode

    async def communicate(self):
        return b"", b""

    def terminate(self):
        self.returncode = -15

    def kill(self):
        self.returncode = -9


class TestRetryAndTimeoutV2(unittest.TestCase):
    @patch("codex_local_sdk.client.shutil.which", return_value="/usr/bin/codex")
    @patch("codex_local_sdk.client.time.sleep")
    @patch("codex_local_sdk.client.random.uniform", return_value=0.05)
    @patch("codex_local_sdk.client.subprocess.run")
    def test_retry_jitter_is_applied_deterministically(self, mock_run, _mock_rand, mock_sleep, _mock_which):
        mock_run.side_effect = [
            SimpleNamespace(returncode=7, stdout="", stderr="tmp"),
            SimpleNamespace(returncode=0, stdout="ok", stderr=""),
        ]

        client = CodexLocalClient(
            retry_policy=RetryPolicy(
                max_attempts=2,
                initial_backoff_seconds=0.5,
                backoff_multiplier=2.0,
                jitter_ratio=0.2,
            )
        )

        result = client.run(CodexExecRequest(prompt="hello"))
        self.assertTrue(result.ok)
        mock_sleep.assert_called_once_with(0.55)

    def test_max_total_retry_seconds_caps_delay(self):
        client = CodexLocalClient(
            retry_policy=RetryPolicy(
                max_attempts=3,
                initial_backoff_seconds=1.0,
                max_total_retry_seconds=0.3,
                jitter_ratio=0.0,
            )
        )

        with patch("codex_local_sdk.client.time.monotonic", return_value=10.2):
            delay = client._compute_retry_delay(attempt=1, retry_started_at=10.0)

        self.assertAlmostEqual(delay, 0.1, places=6)

    @patch("codex_local_sdk.client.shutil.which", return_value="/usr/bin/codex")
    @patch("codex_local_sdk.client.time.sleep")
    @patch("codex_local_sdk.client.subprocess.run")
    def test_timeout_result_is_retried_when_enabled(self, mock_run, mock_sleep, _mock_which):
        timeout_exc = subprocess.TimeoutExpired(cmd=["codex", "exec"], timeout=0.01, output="partial", stderr="slow")
        mock_run.side_effect = [
            timeout_exc,
            SimpleNamespace(returncode=0, stdout="done", stderr=""),
        ]

        client = CodexLocalClient(
            retry_policy=RetryPolicy(max_attempts=2, initial_backoff_seconds=0.1, jitter_ratio=0.0),
        )

        result = client.run(CodexExecRequest(prompt="x"), timeout_seconds=0.01)
        self.assertTrue(result.ok)
        mock_sleep.assert_called_once_with(0.1)

    @patch("codex_local_sdk.client.shutil.which", return_value="/usr/bin/codex")
    @patch("codex_local_sdk.client.time.sleep")
    @patch("codex_local_sdk.client.subprocess.run")
    def test_timeout_result_not_retried_when_disabled(self, mock_run, mock_sleep, _mock_which):
        timeout_exc = subprocess.TimeoutExpired(cmd=["codex", "exec"], timeout=0.01, output="partial", stderr="slow")
        mock_run.side_effect = [timeout_exc]

        client = CodexLocalClient(
            raise_on_error=False,
            retry_policy=RetryPolicy(max_attempts=3, retry_on_timeouts=False, jitter_ratio=0.0),
        )

        result = client.run(CodexExecRequest(prompt="x"), timeout_seconds=0.01)
        self.assertEqual(result.return_code, 124)
        self.assertIn("SDK_TIMEOUT_EXPIRED", result.stderr)
        self.assertEqual(mock_run.call_count, 1)
        mock_sleep.assert_not_called()


class TestLiveStartupRetries(unittest.TestCase):
    @patch("codex_local_sdk.client.shutil.which", return_value="/usr/bin/codex")
    @patch("codex_local_sdk.client.time.sleep")
    @patch("codex_local_sdk.client.subprocess.Popen")
    def test_run_live_retries_on_launch_exception(self, mock_popen, _mock_sleep, _mock_which):
        running = _StartupProcess(poll_sequence=[None] * 40, wait_return_code=0)
        mock_popen.side_effect = [OSError("spawn failed"), running]

        client = CodexLocalClient(
            retry_policy=RetryPolicy(max_attempts=2, initial_backoff_seconds=0.0, jitter_ratio=0.0),
        )

        live = client.run_live(CodexExecRequest(prompt="x", json_output=True))
        self.assertEqual(live.pid, running.pid)
        self.assertEqual(mock_popen.call_count, 2)

    @patch("codex_local_sdk.client.shutil.which", return_value="/usr/bin/codex")
    @patch("codex_local_sdk.client.time.sleep")
    @patch("codex_local_sdk.client.subprocess.Popen")
    def test_run_live_retries_on_immediate_retryable_exit(self, mock_popen, _mock_sleep, _mock_which):
        immediate_fail = _StartupProcess(poll_sequence=[7], wait_return_code=7)
        running = _StartupProcess(poll_sequence=[None] * 40, wait_return_code=0)
        mock_popen.side_effect = [immediate_fail, running]

        client = CodexLocalClient(
            retry_policy=RetryPolicy(max_attempts=2, initial_backoff_seconds=0.0, jitter_ratio=0.0),
        )

        live = client.run_live(CodexExecRequest(prompt="x", json_output=True))
        self.assertEqual(live.pid, running.pid)
        self.assertEqual(mock_popen.call_count, 2)

    @patch("codex_local_sdk.client.shutil.which", return_value="/usr/bin/codex")
    @patch("codex_local_sdk.client.subprocess.Popen")
    def test_run_live_no_retry_after_handle_returned(self, mock_popen, _mock_which):
        # Probe sees process as alive; later wait returns failure. This must not trigger startup retries.
        process = _StartupProcess(
            poll_sequence=[None] * 40,
            stdout_text='{"type":"turn.failed"}\n',
            wait_return_code=7,
        )
        mock_popen.return_value = process

        client = CodexLocalClient(
            raise_on_error=False,
            retry_policy=RetryPolicy(max_attempts=5, initial_backoff_seconds=0.0, jitter_ratio=0.0),
        )
        live = client.run_live(CodexExecRequest(prompt="x", json_output=True))
        result = live.wait()

        self.assertEqual(result.return_code, 7)
        self.assertEqual(mock_popen.call_count, 1)


class TestSessionMetadataAndMigration(unittest.TestCase):
    @patch("codex_local_sdk.client.shutil.which", return_value="/usr/bin/codex")
    @patch("codex_local_sdk.client.subprocess.run")
    def test_session_record_updates_and_bounded_history(self, mock_run, _mock_which):
        mock_run.side_effect = [
            SimpleNamespace(
                returncode=0,
                stdout='{"type":"thread.started","thread_id":"thread-a"}\n{"type":"turn.completed"}\n',
                stderr="",
            ),
            SimpleNamespace(returncode=0, stdout='{"type":"turn.completed"}\n', stderr=""),
            SimpleNamespace(returncode=0, stdout='{"type":"turn.completed"}\n', stderr=""),
        ]

        store = InMemorySessionStore(max_turn_history=2)
        client = CodexLocalClient(session_store=store)

        client.start_thread("start", session_name="plan")
        client.resume("step 1", session_name="plan", last=False, json_output=True)
        client.resume("step 2", session_name="plan", last=False, json_output=True)

        record = client.get_session_record("plan")
        self.assertIsNotNone(record)
        assert record is not None
        self.assertEqual(record.turn_count, 3)
        self.assertEqual(len(record.turns), 2)
        self.assertEqual(record.turns[-1].prompt_preview, "step 2")

    def test_json_store_auto_migrates_legacy_payload(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = f"{tmpdir}/sessions.json"
            with open(path, "w", encoding="utf-8") as f:
                json.dump({"legacy-plan": "thread-legacy"}, f)

            store = JsonFileSessionStore(path)
            self.assertEqual(store.get("legacy-plan"), "thread-legacy")

            with open(path, "r", encoding="utf-8") as f:
                payload = json.load(f)

            self.assertEqual(payload.get("schema_version"), 2)
            self.assertIn("records", payload)
            self.assertIn("legacy-plan", payload["records"])

    def test_json_store_concurrent_writers_keep_valid_json(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = f"{tmpdir}/sessions.json"
            store_a = JsonFileSessionStore(path)
            store_b = JsonFileSessionStore(path)

            def writer(store, prefix):
                for i in range(25):
                    store.set(f"{prefix}-{i}", f"thread-{prefix}-{i}")
                    time.sleep(0.001)

            t1 = threading.Thread(target=writer, args=(store_a, "a"))
            t2 = threading.Thread(target=writer, args=(store_b, "b"))
            t1.start()
            t2.start()
            t1.join()
            t2.join()

            with open(path, "r", encoding="utf-8") as f:
                payload = json.load(f)

            self.assertEqual(payload.get("schema_version"), 2)
            self.assertIsInstance(payload.get("records"), dict)


class TestObservabilityHooks(unittest.TestCase):
    @patch("codex_local_sdk.client.shutil.which", return_value="/usr/bin/codex")
    @patch("codex_local_sdk.client.subprocess.run")
    def test_emits_attempt_and_retry_events(self, mock_run, _mock_which):
        mock_run.side_effect = [
            SimpleNamespace(returncode=7, stdout="", stderr="tmp"),
            SimpleNamespace(returncode=0, stdout="ok", stderr=""),
        ]

        events = []
        client = CodexLocalClient(
            raise_on_error=False,
            retry_policy=RetryPolicy(max_attempts=2, initial_backoff_seconds=0.0, jitter_ratio=0.0),
            event_hook=events.append,
        )

        client.run(CodexExecRequest(prompt="x"))
        event_types = [event.type for event in events]

        self.assertIn("attempt.started", event_types)
        self.assertIn("attempt.failed", event_types)
        self.assertIn("retry.scheduled", event_types)
        self.assertIn("attempt.succeeded", event_types)

    @patch("codex_local_sdk.client.shutil.which", return_value="/usr/bin/codex")
    @patch("codex_local_sdk.client.subprocess.run")
    def test_hook_errors_are_swallowed(self, mock_run, _mock_which):
        mock_run.return_value = SimpleNamespace(returncode=0, stdout="ok", stderr="")

        def noisy_hook(_event):
            raise RuntimeError("hook fail")

        client = CodexLocalClient(event_hook=noisy_hook)
        result = client.run(CodexExecRequest(prompt="x"))

        self.assertTrue(result.ok)

    @patch("codex_local_sdk.client.shutil.which", return_value="/usr/bin/codex")
    @patch("codex_local_sdk.client.subprocess.Popen")
    def test_emits_live_event_notifications(self, mock_popen, _mock_which):
        process = _StartupProcess(
            poll_sequence=[None] * 40,
            stdout_text='{"type":"thread.started","thread_id":"t1"}\n',
            wait_return_code=0,
        )
        mock_popen.return_value = process

        events = []
        client = CodexLocalClient(raise_on_error=False, event_hook=events.append)
        live = client.run_live(CodexExecRequest(prompt="x", json_output=True))
        list(live.iter_events())
        live.wait()

        event_types = [event.type for event in events]
        self.assertIn("live.event", event_types)

    @patch("codex_local_sdk.client.shutil.which", return_value="/usr/bin/codex")
    @patch("codex_local_sdk.client.subprocess.run")
    def test_emits_session_updated_event(self, mock_run, _mock_which):
        mock_run.return_value = SimpleNamespace(
            returncode=0,
            stdout='{"type":"thread.started","thread_id":"thread-z"}\n{"type":"turn.completed"}\n',
            stderr="",
        )

        events = []
        client = CodexLocalClient(event_hook=events.append)
        client.start_thread("start", session_name="flow")

        event_types = [event.type for event in events]
        self.assertIn("session.updated", event_types)


class TestAsyncStartupRetries(unittest.IsolatedAsyncioTestCase):
    @patch("codex_local_sdk.client.shutil.which", return_value="/usr/bin/codex")
    async def test_run_live_async_retries_on_launch_exception(self, _mock_which):
        process = _AsyncStartupProcess(returncode=None)
        creator = AsyncMock(side_effect=[OSError("spawn failed"), process])

        with patch("codex_local_sdk.client.asyncio.create_subprocess_exec", new=creator):
            client = CodexLocalClient(retry_policy=RetryPolicy(max_attempts=2, initial_backoff_seconds=0.0))
            live = await client.run_live_async(CodexExecRequest(prompt="x", json_output=True))

        self.assertEqual(live.pid, process.pid)
        self.assertEqual(creator.call_count, 2)


if __name__ == "__main__":
    unittest.main()
