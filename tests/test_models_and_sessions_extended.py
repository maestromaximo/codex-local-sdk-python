import unittest
from types import SimpleNamespace
from unittest.mock import patch

from codex_local_sdk import CodexExecRequest, CodexExecResult, CodexLocalClient, CodexThreadSession


class TestModelsAndSessionsExtended(unittest.TestCase):
    def test_codex_exec_result_status_helpers(self):
        result = CodexExecResult(
            return_code=0,
            command=("codex", "exec", "x"),
            stdout="",
            stderr="",
            final_message=None,
            turn_status="completed",
        )

        self.assertTrue(result.ok)
        self.assertTrue(result.is_turn_completed)
        self.assertTrue(result.is_turn_terminal)
        self.assertFalse(result.is_turn_failed)

    @patch("codex_local_sdk.client.shutil.which", return_value="/usr/bin/codex")
    @patch("codex_local_sdk.client.subprocess.run")
    def test_thread_session_continue_prompt_updates_last_result(self, mock_run, _mock_which):
        mock_run.return_value = SimpleNamespace(
            returncode=0,
            stdout=(
                '{"type":"turn.completed"}\n'
                '{"type":"item.completed","item":{"type":"agent_message","text":"next"}}\n'
            ),
            stderr="",
        )

        client = CodexLocalClient()
        session = CodexThreadSession(client=client, session_id="thread-a")
        self.assertFalse(session.is_last_turn_complete)

        result = session.continue_prompt("go", json_output=True)
        self.assertEqual(result.final_message, "next")
        self.assertTrue(session.is_last_turn_complete)

    def test_thread_session_continue_live_delegates(self):
        class _FakeClient:
            def __init__(self):
                self.kwargs = None

            def resume_live(self, **kwargs):
                self.kwargs = kwargs
                return "live-run"

        fake_client = _FakeClient()
        session = CodexThreadSession(client=fake_client, session_id="thread-b", default_cwd="/tmp")

        out = session.continue_live(
            "continue this",
            reasoning_effort="high",
            extra_args=("--config", "codex.toml"),
        )

        self.assertEqual(out, "live-run")
        self.assertEqual(fake_client.kwargs["session_id"], "thread-b")
        self.assertEqual(fake_client.kwargs["cwd"], "/tmp")
        self.assertEqual(fake_client.kwargs["reasoning_effort"], "high")
        self.assertEqual(fake_client.kwargs["extra_args"], ("--config", "codex.toml"))

    def test_thread_session_continue_prompt_forwards_reasoning_and_extra_args(self):
        result = CodexExecResult(
            return_code=0,
            command=("codex", "exec", "resume"),
            stdout="",
            stderr="",
            final_message="ok",
            turn_status="completed",
        )

        class _FakeClient:
            def __init__(self):
                self.kwargs = None

            def resume(self, **kwargs):
                self.kwargs = kwargs
                return result

        fake_client = _FakeClient()
        session = CodexThreadSession(client=fake_client, session_id="thread-z")
        out = session.continue_prompt(
            "continue this",
            reasoning_effort="medium",
            extra_args=("--config", "codex.toml"),
        )

        self.assertEqual(out, result)
        self.assertEqual(fake_client.kwargs["reasoning_effort"], "medium")
        self.assertEqual(fake_client.kwargs["extra_args"], ("--config", "codex.toml"))

    @patch("codex_local_sdk.client.shutil.which", return_value="/usr/bin/codex")
    @patch("codex_local_sdk.client.subprocess.run")
    def test_start_thread_uses_json_mode_even_if_overridden_false(self, mock_run, _mock_which):
        mock_run.return_value = SimpleNamespace(
            returncode=0,
            stdout=(
                '{"type":"thread.started","thread_id":"t-force"}\n'
                '{"type":"turn.completed"}\n'
            ),
            stderr="",
        )

        client = CodexLocalClient()
        session, _result = client.start_thread(prompt="start", json_output=False)

        cmd = mock_run.call_args.args[0]
        self.assertIn("--json", cmd)
        self.assertEqual(session.session_id, "t-force")

    def test_request_model_defaults(self):
        req = CodexExecRequest(prompt="x")
        self.assertIsNone(req.reasoning_effort)
        self.assertEqual(req.images, ())
        self.assertEqual(req.extra_args, ())


if __name__ == "__main__":
    unittest.main()
