"""Template for adding a new SDK example under examples/.

Copy this file to `examples/run_<topic>.py` and replace placeholders.
"""

from codex_local_sdk import CodexExecRequest, CodexLocalClient


def main() -> None:
    client = CodexLocalClient()

    result = client.run(
        CodexExecRequest(
            prompt="TODO: replace with your prompt",
            json_output=False,
        ),
        timeout_seconds=60,
    )

    print("return_code:", result.return_code)
    print("turn_status:", result.turn_status)
    print("final_message:\n", result.final_message)


if __name__ == "__main__":
    main()
