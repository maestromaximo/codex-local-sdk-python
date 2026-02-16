"""Template: start a thread and continue it in-process."""

from codex_local_sdk import CodexLocalClient, SandboxMode


def main() -> None:
    client = CodexLocalClient()

    session, first = client.start_thread(
        prompt="TODO: initial prompt",
        sandbox=SandboxMode.READ_ONLY,
        timeout_seconds=120,
    )

    print("session_id:", session.session_id)
    print("first turn status:", first.turn_status)

    second = session.continue_prompt(
        "TODO: follow-up prompt",
        json_output=True,
        timeout_seconds=120,
    )

    print("second turn status:", second.turn_status)
    print("second final message:\n", second.final_message)


if __name__ == "__main__":
    main()
