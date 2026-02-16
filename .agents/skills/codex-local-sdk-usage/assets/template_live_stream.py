"""Template: live JSON event streaming with CodexLocalClient.run_live."""

from codex_local_sdk import CodexExecRequest, CodexLocalClient, SandboxMode


def main() -> None:
    client = CodexLocalClient()

    live = client.run_live(
        CodexExecRequest(
            prompt="TODO: replace with your prompt",
            sandbox=SandboxMode.READ_ONLY,
            json_output=True,
        )
    )

    print("pid:", live.pid)
    for event in live.iter_events():
        print("event:", event.type)

    result = live.wait()
    print("return_code:", result.return_code)
    print("turn_status:", result.turn_status)
    print("final_message:\n", result.final_message)


if __name__ == "__main__":
    main()
