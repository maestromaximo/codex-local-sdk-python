import io
import unittest
from unittest.mock import patch

from codex_local_sdk import CodexExecRequest, CodexLiveRun, CodexLocalClient
from codex_local_sdk.exceptions import CodexExecFailedError


class _FakeProcess:
    def __init__(
        self,
        stdout_text: str,
        stderr_text: str = "",
        returncode: int | None = 0,
        complete: bool = True,
    ) -> None:
        self.pid = 4321
        self.stdout = io.StringIO(stdout_text)
        self.stderr = io.StringIO(stderr_text)
        self.returncode = returncode
        self._complete = complete
        self.terminated = False
        self.killed = False

    def poll(self):
        return self.returncode if self._complete else None

    def wait(self, timeout=None):
        self._complete = True
        if self.returncode is None:
            self.returncode = 0
        return self.returncode

    def terminate(self):
        self.terminated = True
        self.returncode = -15
        self._complete = True

    def kill(self):
        self.killed = True
        self.returncode = -9
        self._complete = True


class TestCodexLiveRunExtended(unittest.TestCase):
    def test_iter_events_and_result_parsing(self):
        process = _FakeProcess(
            stdout_text=(
                '{"type":"thread.started","thread_id":"t-1"}\n'
                '{"type":"item.completed","item":{"type":"agent_message","text":"Hi"}}\n'
                '{"type":"turn.completed","usage":{"output_tokens":11}}\n'
            ),
            stderr_text="warn\n",
            returncode=0,
            complete=True,
        )

        live = CodexLiveRun(process, ["codex", "exec", "--json", "x"], started_at=0.0, raise_on_error=True)
        events = list(live.iter_events())

        self.assertEqual(len(events), 3)
        self.assertTrue(live.is_complete)
        self.assertEqual(live.return_code, 0)

        result = live.result()
        self.assertEqual(result.thread_id, "t-1")
        self.assertEqual(result.final_message, "Hi")
        self.assertEqual(result.turn_status, "completed")
        self.assertEqual(result.usage, {"output_tokens": 11})
        self.assertIn("warn", result.stderr)

    def test_result_raises_if_process_not_complete(self):
        process = _FakeProcess(stdout_text="", returncode=None, complete=False)
        live = CodexLiveRun(process, ["codex", "exec", "--json", "x"], started_at=0.0, raise_on_error=True)

        with self.assertRaises(Exception):
            live.result()

    def test_result_is_cached(self):
        process = _FakeProcess(stdout_text='{"type":"turn.completed"}\n', returncode=0, complete=True)
        live = CodexLiveRun(process, ["codex", "exec", "--json", "x"], started_at=0.0, raise_on_error=True)

        r1 = live.result()
        r2 = live.result()
        self.assertIs(r1, r2)

    def test_failed_live_run_raises_when_raise_on_error_true(self):
        process = _FakeProcess(stdout_text='{"type":"turn.failed"}\n', returncode=7, complete=True)
        live = CodexLiveRun(process, ["codex", "exec", "--json", "x"], started_at=0.0, raise_on_error=True)

        with self.assertRaises(CodexExecFailedError):
            live.result()

    def test_failed_live_run_returns_result_when_raise_on_error_false(self):
        process = _FakeProcess(stdout_text='{"type":"turn.failed"}\n', returncode=7, complete=True)
        live = CodexLiveRun(process, ["codex", "exec", "--json", "x"], started_at=0.0, raise_on_error=False)

        result = live.result()
        self.assertEqual(result.return_code, 7)
        self.assertEqual(result.turn_status, "failed")

    def test_terminate_and_kill_delegate(self):
        process = _FakeProcess(stdout_text="", returncode=None, complete=False)
        live = CodexLiveRun(process, ["codex", "exec", "--json", "x"], started_at=0.0, raise_on_error=False)

        live.terminate()
        self.assertTrue(process.terminated)

        process = _FakeProcess(stdout_text="", returncode=None, complete=False)
        live = CodexLiveRun(process, ["codex", "exec", "--json", "x"], started_at=0.0, raise_on_error=False)
        live.kill()
        self.assertTrue(process.killed)


class TestLiveEntryPointsExtended(unittest.TestCase):
    @patch("codex_local_sdk.client.shutil.which", return_value="/usr/bin/codex")
    @patch("codex_local_sdk.client.subprocess.Popen")
    def test_run_live_forces_json_flag(self, mock_popen, _mock_which):
        mock_popen.return_value = _FakeProcess(stdout_text="", returncode=0, complete=True)

        client = CodexLocalClient()
        live = client.run_live(CodexExecRequest(prompt="hello", json_output=False))

        self.assertIn("--json", live.command)

    @patch("codex_local_sdk.client.shutil.which", return_value="/usr/bin/codex")
    @patch("codex_local_sdk.client.subprocess.Popen")
    def test_resume_live_uses_resume_command_shape(self, mock_popen, _mock_which):
        mock_popen.return_value = _FakeProcess(stdout_text="", returncode=0, complete=True)

        client = CodexLocalClient()
        live = client.resume_live(
            prompt="cont",
            session_id="thread-9",
            last=False,
            all_sessions=True,
            reasoning_effort="low",
            extra_args=("--config", "codex.toml"),
        )

        cmd = live.command
        self.assertEqual(cmd[0:3], ("codex", "exec", "resume"))
        self.assertIn("thread-9", cmd)
        self.assertIn("--all", cmd)
        self.assertIn("--json", cmd)
        self.assertIn("--reasoning-effort", cmd)
        self.assertIn("low", cmd)
        self.assertIn("--config", cmd)
        self.assertIn("codex.toml", cmd)


if __name__ == "__main__":
    unittest.main()
