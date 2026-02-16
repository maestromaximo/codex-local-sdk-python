from codex_local_sdk import CodexExecRequest, CodexLocalClient, SandboxMode


def main() -> None:
    client = CodexLocalClient()

    live = client.run_live(
        CodexExecRequest(
            prompt="Summarize this repository and suggest next 3 tasks.",
            sandbox=SandboxMode.READ_ONLY,
        )
    )

    print(f"Started PID: {live.pid}")
    for event in live.iter_events():
        print(f"event: {event.type}")

    result = live.wait()
    print("Turn status:", result.turn_status)
    print("Completed:", result.is_turn_completed)
    print("Final message:")
    print(result.final_message)


if __name__ == "__main__":
    main()
