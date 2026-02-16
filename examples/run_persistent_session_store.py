from codex_local_sdk import CodexLocalClient, JsonFileSessionStore, SandboxMode


def main() -> None:
    store = JsonFileSessionStore(".codex_sessions.json")
    client = CodexLocalClient(session_store=store)

    session, first = client.start_thread(
        prompt="Analyze this repository and create an implementation plan.",
        sandbox=SandboxMode.READ_ONLY,
        session_name="repo-plan",
    )

    print("Stored session:", session.session_name, session.session_id)
    print("First completed:", first.is_turn_completed)

    follow_up = client.resume(
        prompt="Continue with concrete task breakdown.",
        session_name="repo-plan",
        last=False,
        json_output=True,
    )
    print("Follow-up completed:", follow_up.is_turn_completed)
    print("Follow-up final message:")
    print(follow_up.final_message or "<empty>")


if __name__ == "__main__":
    main()
