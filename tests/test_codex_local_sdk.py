import io
import unittest
from unittest.mock import patch

from codex_local_sdk import CodexExecRequest, CodexLocalClient, SandboxMode


class _FakePopenProcess:
    def __init__(self) -> None:
        self.pid = 1234
        self.returncode = 0
        self.stdout = io.StringIO("")
        self.stderr = io.StringIO("")

    def poll(self) -> int:
        return 0

    def wait(self, timeout=None) -> int:
        return 0

    def terminate(self) -> None:
        self.returncode = -15

    def kill(self) -> None:
        self.returncode = -9


class TestCodexLocalClient(unittest.TestCase):
    @patch("codex_local_sdk.client.shutil.which", return_value="/usr/bin/codex")
    @patch("codex_local_sdk.client.subprocess.run")
    def test_builds_expected_command(self, mock_run, _mock_which):
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = "done"
        mock_run.return_value.stderr = ""

        client = CodexLocalClient(codex_bin="codex")
        req = CodexExecRequest(
            prompt="hello",
            model="gpt-5.3-codex",
            sandbox=SandboxMode.READ_ONLY,
            full_auto=True,
            json_output=True,
            ephemeral=True,
            extra_args=("--skip-git-repo-check",),
        )

        result = client.run(req)

        self.assertTrue(result.ok)
        called_cmd = mock_run.call_args.args[0]
        self.assertEqual(called_cmd[0:2], ["codex", "exec"])
        self.assertIn("--json", called_cmd)
        self.assertIn("--model", called_cmd)
        self.assertIn("gpt-5.3-codex", called_cmd)
        self.assertIn("--sandbox", called_cmd)
        self.assertIn("read-only", called_cmd)
        self.assertIn("--full-auto", called_cmd)
        self.assertIn("--ephemeral", called_cmd)
        self.assertEqual(called_cmd[-1], "hello")

    @patch("codex_local_sdk.client.shutil.which", return_value="/usr/bin/codex")
    @patch("codex_local_sdk.client.subprocess.run")
    def test_extracts_thread_and_completion_status_from_jsonl(self, mock_run, _mock_which):
        mock_run.return_value.returncode = 0
        mock_run.return_value.stderr = ""
        mock_run.return_value.stdout = (
            '{"type":"thread.started","thread_id":"thread-123"}\n'
            '{"type":"item.completed","item":{"type":"agent_message","text":"Final answer"}}\n'
            '{"type":"turn.completed","usage":{"output_tokens":10}}\n'
        )

        client = CodexLocalClient(codex_bin="codex")
        req = CodexExecRequest(prompt="hello", json_output=True)
        result = client.run(req)

        self.assertEqual(result.final_message, "Final answer")
        self.assertEqual(result.thread_id, "thread-123")
        self.assertEqual(result.turn_status, "completed")
        self.assertTrue(result.is_turn_completed)
        self.assertTrue(result.is_turn_terminal)
        self.assertEqual(result.usage, {"output_tokens": 10})

    @patch("codex_local_sdk.client.shutil.which", return_value="/usr/bin/codex")
    @patch("codex_local_sdk.client.subprocess.run")
    def test_start_thread_and_continue(self, mock_run, _mock_which):
        start = type("Result", (), {})()
        start.returncode = 0
        start.stderr = ""
        start.stdout = (
            '{"type":"thread.started","thread_id":"thread-xyz"}\n'
            '{"type":"turn.completed"}\n'
            '{"type":"item.completed","item":{"type":"agent_message","text":"started"}}\n'
        )

        follow_up = type("Result", (), {})()
        follow_up.returncode = 0
        follow_up.stderr = ""
        follow_up.stdout = (
            '{"type":"turn.completed"}\n'
            '{"type":"item.completed","item":{"type":"agent_message","text":"continued"}}\n'
        )

        mock_run.side_effect = [start, follow_up]

        client = CodexLocalClient(codex_bin="codex")
        session, first_result = client.start_thread("start prompt")
        next_result = session.continue_prompt("continue prompt", json_output=True)

        self.assertEqual(session.session_id, "thread-xyz")
        self.assertEqual(first_result.thread_id, "thread-xyz")
        self.assertEqual(next_result.final_message, "continued")

        resume_cmd = mock_run.call_args_list[1].args[0]
        self.assertEqual(resume_cmd[0:3], ["codex", "exec", "resume"])
        self.assertIn("thread-xyz", resume_cmd)
        self.assertIn("--json", resume_cmd)
        self.assertEqual(resume_cmd[-1], "continue prompt")

    @patch("codex_local_sdk.client.shutil.which", return_value="/usr/bin/codex")
    @patch("codex_local_sdk.client.subprocess.Popen")
    def test_run_live_auto_enables_json(self, mock_popen, _mock_which):
        mock_popen.return_value = _FakePopenProcess()

        client = CodexLocalClient(codex_bin="codex")
        live = client.run_live(CodexExecRequest(prompt="hello", json_output=False))

        self.assertIn("--json", live.command)


if __name__ == "__main__":
    unittest.main()
