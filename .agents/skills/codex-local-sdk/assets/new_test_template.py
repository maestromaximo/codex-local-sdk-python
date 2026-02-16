"""Template for adding a new unittest module under tests/."""

import unittest
from unittest.mock import patch

from codex_local_sdk import CodexExecRequest, CodexLocalClient


class TestNewBehavior(unittest.TestCase):
    @patch("codex_local_sdk.client.shutil.which", return_value="/usr/bin/codex")
    @patch("codex_local_sdk.client.subprocess.run")
    def test_placeholder(self, mock_run, _mock_which):
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = "ok"
        mock_run.return_value.stderr = ""

        client = CodexLocalClient()
        result = client.run(CodexExecRequest(prompt="hello"))

        self.assertTrue(result.ok)


if __name__ == "__main__":
    unittest.main()
