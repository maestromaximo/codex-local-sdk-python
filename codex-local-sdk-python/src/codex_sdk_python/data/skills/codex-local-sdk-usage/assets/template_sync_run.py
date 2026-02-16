"""Template: synchronous one-shot execution with CodexLocalClient.run."""

from codex_local_sdk import CodexExecRequest, CodexLocalClient, SandboxMode


def main() -> None:
    client = CodexLocalClient()

    request = CodexExecRequest(
        prompt="TODO: replace with your prompt",
        sandbox=SandboxMode.READ_ONLY,
        json_output=True,
    )

    result = client.run(request, timeout_seconds=120)

    print("return_code:", result.return_code)
    print("turn_status:", result.turn_status)
    print("thread_id:", result.thread_id)
    print("final_message:\n", result.final_message)


if __name__ == "__main__":
    main()
