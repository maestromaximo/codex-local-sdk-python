from __future__ import annotations

import json
import os
import shutil
import unittest

from codex_local_sdk import CodexExecRequest, CodexLocalClient, SandboxMode


class TestCodexCliIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if os.getenv("CODEX_INTEGRATION") != "1":
            raise unittest.SkipTest("Set CODEX_INTEGRATION=1 to run integration tests.")

        codex_bin = os.getenv("CODEX_BIN", "codex")
        if shutil.which(codex_bin) is None:
            raise unittest.SkipTest(f"Codex CLI '{codex_bin}' is not available on PATH.")

        cls.cwd = os.getenv("CODEX_INTEGRATION_CWD", os.getcwd())
        cls.api_key = os.getenv("CODEX_API_KEY")
        cls.client = CodexLocalClient(codex_bin=codex_bin)

    def test_non_json_run_success(self) -> None:
        result = self.client.run(
            CodexExecRequest(
                prompt="Reply with exactly the text integration_ok.",
                cwd=self.cwd,
                sandbox=SandboxMode.READ_ONLY,
            ),
            api_key=self.api_key,
            timeout_seconds=120,
        )

        self.assertTrue(result.ok)
        self.assertIsNotNone(result.final_message)
        assert result.final_message is not None
        self.assertIn("integration", result.final_message.lower())

    def test_json_run_has_events_and_terminal_status(self) -> None:
        result = self.client.run(
            CodexExecRequest(
                prompt="Summarize this repository in one short sentence.",
                cwd=self.cwd,
                sandbox=SandboxMode.READ_ONLY,
                json_output=True,
            ),
            api_key=self.api_key,
            timeout_seconds=120,
        )

        self.assertTrue(result.ok)
        self.assertGreater(len(result.events), 0)
        self.assertTrue(result.is_turn_terminal)

    def test_start_thread_then_resume(self) -> None:
        session, first = self.client.start_thread(
            prompt="Give an initial one-sentence plan for this repository.",
            api_key=self.api_key,
            timeout_seconds=120,
            cwd=self.cwd,
            sandbox=SandboxMode.READ_ONLY,
        )

        self.assertTrue(first.ok)
        self.assertIsNotNone(session.session_id)

        second = session.continue_prompt(
            "Now refine that into exactly three concise action items.",
            json_output=True,
            timeout_seconds=120,
        )
        self.assertTrue(second.ok)
        self.assertTrue(second.is_turn_terminal)

    def test_schema_constrained_output(self) -> None:
        schema = {
            "type": "object",
            "properties": {
                "status": {"type": "string"},
                "checks": {
                    "type": "array",
                    "items": {"type": "string"},
                },
            },
            "required": ["status", "checks"],
            "additionalProperties": False,
        }

        result = self.client.run_with_schema(
            prompt="Return a JSON object with status and checks for this repository.",
            schema=schema,
            timeout_seconds=120,
            cwd=self.cwd,
            sandbox=SandboxMode.READ_ONLY,
            api_key=self.api_key,
        )

        self.assertTrue(result.ok)
        self.assertIsNotNone(result.final_message)
        parsed = json.loads(result.final_message or "{}")
        self.assertIn("status", parsed)
        self.assertIn("checks", parsed)


if __name__ == "__main__":
    unittest.main()
