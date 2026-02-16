from codex_local_sdk import CodexLocalClient, SandboxMode


def main() -> None:
    client = CodexLocalClient()

    session, first = client.start_thread(
        prompt="Analyze this repository and provide an initial plan.",
        sandbox=SandboxMode.READ_ONLY,
    )

    print("Session ID:", session.session_id)
    print("First turn completed:", first.is_turn_completed)

    second = session.continue_prompt(
        "Now give me the first concrete implementation step.",
        json_output=True,
    )

    print("Second turn completed:", second.is_turn_completed)
    print("Second turn final message:")
    print(second.final_message)


if __name__ == "__main__":
    main()
