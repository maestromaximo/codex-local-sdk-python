import asyncio
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from codex_local_sdk import (
    CodexError,
    CodexExecRequest,
    CodexExecResult,
    CodexLocalClient,
    InMemorySessionStore,
    JsonFileSessionStore,
    RetryPolicy,
)
from codex_local_sdk.exceptions import CodexExecFailedError


class _FakeAsyncStream:
    def __init__(self, text: str) -> None:
        self._lines = [line.encode("utf-8") for line in text.splitlines(keepends=True)]
        self._idx = 0

    async def readline(self) -> bytes:
        if self._idx >= len(self._lines):
            return b""
        line = self._lines[self._idx]
        self._idx += 1
        await asyncio.sleep(0)
        return line


class _FakeAsyncProcess:
    def __init__(self, stdout_text: str, stderr_text: str = "", returncode: int = 0) -> None:
        self.pid = 8888
        self.stdout = _FakeAsyncStream(stdout_text)
        self.stderr = _FakeAsyncStream(stderr_text)
        self.returncode: int | None = None
        self._final_returncode = returncode

    async def wait(self) -> int:
        await asyncio.sleep(0)
        self.returncode = self._final_returncode
        return self.returncode

    def terminate(self) -> None:
        self.returncode = -15

    def kill(self) -> None:
        self.returncode = -9


class TestRetryAndSessionStore(unittest.TestCase):
    @patch("codex_local_sdk.client.shutil.which", return_value="/usr/bin/codex")
    @patch("codex_local_sdk.client.time.sleep")
    @patch("codex_local_sdk.client.subprocess.run")
    def test_retry_policy_retries_until_success(self, mock_run, mock_sleep, _mock_which):
        mock_run.side_effect = [
            SimpleNamespace(returncode=7, stdout="", stderr="temporary"),
            SimpleNamespace(returncode=0, stdout="done", stderr=""),
        ]

        client = CodexLocalClient(
            retry_policy=RetryPolicy(max_attempts=3, initial_backoff_seconds=0.25, backoff_multiplier=2.0),
        )
        result = client.run(CodexExecRequest(prompt="hello"))

        self.assertTrue(result.ok)
        self.assertEqual(mock_run.call_count, 2)
        mock_sleep.assert_called_once_with(0.25)

    @patch("codex_local_sdk.client.shutil.which", return_value="/usr/bin/codex")
    @patch("codex_local_sdk.client.time.sleep")
    @patch("codex_local_sdk.client.subprocess.run")
    def test_retry_policy_respects_exit_code_filter(self, mock_run, mock_sleep, _mock_which):
        mock_run.side_effect = [
            SimpleNamespace(returncode=2, stdout="", stderr="do-not-retry"),
            SimpleNamespace(returncode=0, stdout="done", stderr=""),
        ]

        client = CodexLocalClient(
            raise_on_error=False,
            retry_policy=RetryPolicy(max_attempts=3, retry_on_exit_codes=(7,)),
        )
        result = client.run(CodexExecRequest(prompt="hello"))

        self.assertEqual(result.return_code, 2)
        self.assertEqual(mock_run.call_count, 1)
        mock_sleep.assert_not_called()

    @patch("codex_local_sdk.client.shutil.which", return_value="/usr/bin/codex")
    @patch("codex_local_sdk.client.time.sleep")
    @patch("codex_local_sdk.client.subprocess.run")
    def test_retry_exhaustion_raises_when_enabled(self, mock_run, _mock_sleep, _mock_which):
        mock_run.return_value = SimpleNamespace(returncode=9, stdout="", stderr="boom")

        client = CodexLocalClient(
            raise_on_error=True,
            retry_policy=RetryPolicy(max_attempts=3, initial_backoff_seconds=0.01),
        )

        with self.assertRaises(CodexExecFailedError):
            client.run(CodexExecRequest(prompt="x"))
        self.assertEqual(mock_run.call_count, 3)

    def test_in_memory_session_store_roundtrip(self):
        store = InMemorySessionStore()
        store.set("default", "thread-1")
        self.assertEqual(store.get("default"), "thread-1")
        self.assertEqual(store.all(), {"default": "thread-1"})
        store.delete("default")
        self.assertIsNone(store.get("default"))

    def test_json_file_session_store_persists(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = f"{tmpdir}/sessions.json"
            store_a = JsonFileSessionStore(path)
            store_a.set("pipeline", "thread-xyz")

            store_b = JsonFileSessionStore(path)
            self.assertEqual(store_b.get("pipeline"), "thread-xyz")

            store_b.delete("pipeline")
            self.assertIsNone(store_a.get("pipeline"))

    @patch("codex_local_sdk.client.shutil.which", return_value="/usr/bin/codex")
    @patch("codex_local_sdk.client.subprocess.run")
    def test_start_thread_with_name_persists_session(self, mock_run, _mock_which):
        mock_run.return_value = SimpleNamespace(
            returncode=0,
            stdout=(
                '{"type":"thread.started","thread_id":"thread-abc"}\n'
                '{"type":"turn.completed"}\n'
            ),
            stderr="",
        )

        store = InMemorySessionStore()
        client = CodexLocalClient(session_store=store)
        session, _ = client.start_thread("start", session_name="project-plan")

        self.assertEqual(session.session_id, "thread-abc")
        self.assertEqual(client.get_session_id("project-plan"), "thread-abc")

    @patch("codex_local_sdk.client.shutil.which", return_value="/usr/bin/codex")
    @patch("codex_local_sdk.client.subprocess.run")
    def test_resume_by_session_name_uses_store_lookup(self, mock_run, _mock_which):
        mock_run.return_value = SimpleNamespace(returncode=0, stdout="ok", stderr="")

        store = InMemorySessionStore({"my-flow": "thread-777"})
        client = CodexLocalClient(session_store=store)
        client.resume(prompt="continue", session_name="my-flow", last=False)

        cmd = mock_run.call_args.args[0]
        self.assertIn("thread-777", cmd)
        self.assertNotIn("--last", cmd)

    def test_open_session_raises_for_unknown_name(self):
        client = CodexLocalClient(session_store=InMemorySessionStore())
        with self.assertRaises(CodexError):
            client.open_session("missing")


class TestAsyncApi(unittest.IsolatedAsyncioTestCase):
    async def test_run_async_delegates(self):
        client = CodexLocalClient()
        expected = CodexExecResult(
            return_code=0,
            command=("codex", "exec", "x"),
            stdout="ok",
            stderr="",
            final_message="ok",
        )

        with patch.object(CodexLocalClient, "run", return_value=expected) as mock_run:
            result = await client.run_async(CodexExecRequest(prompt="hello"))

        self.assertIs(result, expected)
        mock_run.assert_called_once()

    @patch("codex_local_sdk.client.shutil.which", return_value="/usr/bin/codex")
    async def test_run_live_async_streams_events(self, _mock_which):
        process = _FakeAsyncProcess(
            stdout_text=(
                '{"type":"thread.started","thread_id":"thread-1"}\n'
                '{"type":"item.completed","item":{"type":"agent_message","text":"async done"}}\n'
                '{"type":"turn.completed"}\n'
            ),
            stderr_text="warn\n",
            returncode=0,
        )

        with patch("codex_local_sdk.client.asyncio.create_subprocess_exec", new=AsyncMock(return_value=process)):
            client = CodexLocalClient()
            live = await client.run_live_async(CodexExecRequest(prompt="hello"))

            events = [event async for event in live.iter_events()]
            result = await live.wait()

        self.assertEqual(len(events), 3)
        self.assertEqual(result.thread_id, "thread-1")
        self.assertEqual(result.final_message, "async done")
        self.assertTrue(result.is_turn_completed)

    async def test_thread_session_continue_prompt_async_updates_last_result(self):
        result = CodexExecResult(
            return_code=0,
            command=("codex", "exec", "resume"),
            stdout="",
            stderr="",
            final_message="next",
            turn_status="completed",
        )

        class _FakeClient:
            async def resume_async(self, **_kwargs):
                return result

        from codex_local_sdk.client import CodexThreadSession

        session = CodexThreadSession(client=_FakeClient(), session_id="thread-x")
        out = await session.continue_prompt_async("go")

        self.assertEqual(out.final_message, "next")
        self.assertTrue(session.is_last_turn_complete)


if __name__ == "__main__":
    unittest.main()
