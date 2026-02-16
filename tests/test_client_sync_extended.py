import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from codex_local_sdk import CodexError, CodexExecRequest, CodexLocalClient, SandboxMode
from codex_local_sdk.exceptions import CodexExecFailedError, CodexNotInstalledError


class TestCodexLocalClientSyncExtended(unittest.TestCase):
    @patch("codex_local_sdk.client.shutil.which", return_value=None)
    def test_run_raises_when_codex_not_installed(self, _mock_which):
        client = CodexLocalClient(codex_bin="codex")
        with self.assertRaises(CodexNotInstalledError):
            client.run(CodexExecRequest(prompt="hello"))

    @patch("codex_local_sdk.client.shutil.which", return_value="/usr/bin/codex")
    @patch("codex_local_sdk.client.subprocess.run")
    def test_run_non_json_uses_stdout_as_final_message(self, mock_run, _mock_which):
        mock_run.return_value = SimpleNamespace(returncode=0, stdout="  answer\n", stderr="")

        client = CodexLocalClient()
        result = client.run(CodexExecRequest(prompt="hello"))

        self.assertEqual(result.final_message, "answer")
        self.assertIsNone(result.thread_id)
        self.assertIsNone(result.turn_status)

    @patch("codex_local_sdk.client.shutil.which", return_value="/usr/bin/codex")
    @patch("codex_local_sdk.client.subprocess.run")
    def test_run_json_parses_thread_id_camel_case(self, mock_run, _mock_which):
        mock_run.return_value = SimpleNamespace(
            returncode=0,
            stdout=(
                '{"type":"thread.started","threadId":"thread-camel"}\n'
                '{"type":"item.completed","item":{"type":"agent_message","text":"hello"}}\n'
            ),
            stderr="",
        )

        result = CodexLocalClient().run(CodexExecRequest(prompt="x", json_output=True))
        self.assertEqual(result.thread_id, "thread-camel")

    @patch("codex_local_sdk.client.shutil.which", return_value="/usr/bin/codex")
    @patch("codex_local_sdk.client.subprocess.run")
    def test_run_json_parses_thread_id_from_thread_object(self, mock_run, _mock_which):
        mock_run.return_value = SimpleNamespace(
            returncode=0,
            stdout=(
                '{"type":"thread.started","thread":{"id":"thread-object"}}\n'
                '{"type":"item.completed","item":{"type":"agent_message","text":"hello"}}\n'
            ),
            stderr="",
        )

        result = CodexLocalClient().run(CodexExecRequest(prompt="x", json_output=True))
        self.assertEqual(result.thread_id, "thread-object")

    @patch("codex_local_sdk.client.shutil.which", return_value="/usr/bin/codex")
    @patch("codex_local_sdk.client.subprocess.run")
    def test_turn_status_from_turn_object_when_no_turn_event(self, mock_run, _mock_which):
        mock_run.return_value = SimpleNamespace(
            returncode=0,
            stdout=(
                '{"type":"item.completed","item":{"type":"agent_message","text":"hello"}}\n'
                '{"type":"misc","turn":{"status":"failed","usage":{"input_tokens":3}}}\n'
            ),
            stderr="",
        )

        result = CodexLocalClient().run(CodexExecRequest(prompt="x", json_output=True))
        self.assertEqual(result.turn_status, "failed")
        self.assertEqual(result.usage, {"input_tokens": 3})
        self.assertTrue(result.is_turn_failed)

    @patch("codex_local_sdk.client.shutil.which", return_value="/usr/bin/codex")
    @patch("codex_local_sdk.client.subprocess.run")
    def test_invalid_json_lines_are_ignored(self, mock_run, _mock_which):
        mock_run.return_value = SimpleNamespace(
            returncode=0,
            stdout=(
                'not-json\n'
                '{"type":"item.completed","item":{"type":"agent_message","text":"ok"}}\n'
            ),
            stderr="",
        )

        result = CodexLocalClient().run(CodexExecRequest(prompt="x", json_output=True))
        self.assertEqual(len(result.events), 1)
        self.assertEqual(result.final_message, "ok")

    @patch("codex_local_sdk.client.shutil.which", return_value="/usr/bin/codex")
    @patch("codex_local_sdk.client.subprocess.run")
    def test_run_raise_on_error_false_returns_failed_result(self, mock_run, _mock_which):
        mock_run.return_value = SimpleNamespace(returncode=42, stdout="", stderr="boom")

        client = CodexLocalClient(raise_on_error=False)
        result = client.run(CodexExecRequest(prompt="x"))

        self.assertEqual(result.return_code, 42)
        self.assertFalse(result.ok)

    @patch("codex_local_sdk.client.shutil.which", return_value="/usr/bin/codex")
    @patch("codex_local_sdk.client.subprocess.run")
    def test_run_raise_on_error_true_raises_failed_error(self, mock_run, _mock_which):
        mock_run.return_value = SimpleNamespace(returncode=3, stdout="", stderr="boom")

        client = CodexLocalClient(raise_on_error=True)
        with self.assertRaises(CodexExecFailedError) as ctx:
            client.run(CodexExecRequest(prompt="x"))

        self.assertEqual(ctx.exception.result.return_code, 3)

    @patch("codex_local_sdk.client.shutil.which", return_value="/usr/bin/codex")
    @patch("codex_local_sdk.client.subprocess.run")
    def test_api_key_injected_into_environment(self, mock_run, _mock_which):
        mock_run.return_value = SimpleNamespace(returncode=0, stdout="done", stderr="")

        client = CodexLocalClient(default_env={"MY_FLAG": "1"})
        client.run(CodexExecRequest(prompt="x"), api_key="abc123")

        env = mock_run.call_args.kwargs["env"]
        self.assertEqual(env.get("CODEX_API_KEY"), "abc123")
        self.assertEqual(env.get("MY_FLAG"), "1")

    @patch("codex_local_sdk.client.shutil.which", return_value="/usr/bin/codex")
    @patch("codex_local_sdk.client.subprocess.run")
    def test_run_with_schema_creates_flag_and_cleans_temp_file(self, mock_run, _mock_which):
        mock_run.return_value = SimpleNamespace(returncode=0, stdout='{"ok":true}', stderr="")

        client = CodexLocalClient()
        schema = {
            "type": "object",
            "properties": {"ok": {"type": "boolean"}},
            "required": ["ok"],
            "additionalProperties": False,
        }

        client.run_with_schema(
            prompt="Return JSON",
            schema=schema,
            output_json_path="out.json",
            sandbox=SandboxMode.READ_ONLY,
        )

        cmd = mock_run.call_args.args[0]
        self.assertIn("--output-schema", cmd)
        self.assertIn("--output-last-message", cmd)
        schema_path = cmd[cmd.index("--output-schema") + 1]
        self.assertFalse(os.path.exists(schema_path))

    @patch("codex_local_sdk.client.shutil.which", return_value="/usr/bin/codex")
    @patch("codex_local_sdk.client.subprocess.run")
    def test_resume_with_defaults_uses_last(self, mock_run, _mock_which):
        mock_run.return_value = SimpleNamespace(returncode=0, stdout="ok", stderr="")

        client = CodexLocalClient()
        client.resume(prompt="continue")

        cmd = mock_run.call_args.args[0]
        self.assertEqual(cmd[0:3], ["codex", "exec", "resume"])
        self.assertIn("--last", cmd)
        self.assertEqual(cmd[-1], "continue")

    @patch("codex_local_sdk.client.shutil.which", return_value="/usr/bin/codex")
    @patch("codex_local_sdk.client.subprocess.run")
    def test_resume_with_session_id_and_all_sessions(self, mock_run, _mock_which):
        mock_run.return_value = SimpleNamespace(returncode=0, stdout="ok", stderr="")

        client = CodexLocalClient()
        client.resume(
            prompt="continue",
            session_id="thread-777",
            last=False,
            all_sessions=True,
            json_output=True,
        )

        cmd = mock_run.call_args.args[0]
        self.assertIn("thread-777", cmd)
        self.assertNotIn("--last", cmd)
        self.assertIn("--all", cmd)
        self.assertIn("--json", cmd)

    @patch("codex_local_sdk.client.shutil.which", return_value="/usr/bin/codex")
    @patch("codex_local_sdk.client.subprocess.run")
    def test_resume_supports_reasoning_effort_and_extra_args(self, mock_run, _mock_which):
        mock_run.return_value = SimpleNamespace(returncode=0, stdout="ok", stderr="")

        client = CodexLocalClient()
        client.resume(
            prompt="continue",
            session_id="thread-888",
            last=False,
            reasoning_effort="medium",
            extra_args=("--config", "codex.toml"),
        )

        cmd = mock_run.call_args.args[0]
        self.assertIn("--reasoning-effort", cmd)
        self.assertIn("medium", cmd)
        self.assertIn("--config", cmd)
        self.assertIn("codex.toml", cmd)

    @patch("codex_local_sdk.client.shutil.which", return_value="/usr/bin/codex")
    @patch("codex_local_sdk.client.subprocess.run")
    def test_start_thread_raises_when_thread_id_missing(self, mock_run, _mock_which):
        mock_run.return_value = SimpleNamespace(
            returncode=0,
            stdout='{"type":"turn.completed"}\n',
            stderr="",
        )

        client = CodexLocalClient()
        with self.assertRaises(CodexError):
            client.start_thread(prompt="start")


if __name__ == "__main__":
    unittest.main()
