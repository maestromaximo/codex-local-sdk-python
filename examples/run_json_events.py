from codex_local_sdk import CodexExecRequest, CodexLocalClient, SandboxMode


def main() -> None:
    client = CodexLocalClient()

    result = client.run(
        CodexExecRequest(
            prompt="Summarize repo risks and suggest next steps.",
            sandbox=SandboxMode.READ_ONLY,
            json_output=True,
        )
    )

    print(f"Events captured: {len(result.events)}")
    print(f"Thread/session ID: {result.thread_id}")
    print(f"Turn status: {result.turn_status}")
    print(f"Turn completed: {result.is_turn_completed}")
    print(f"Final message: {result.final_message}")


if __name__ == "__main__":
    main()
