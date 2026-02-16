"""Template: persist and resume a named session using JsonFileSessionStore."""

from codex_local_sdk import CodexLocalClient, JsonFileSessionStore, SandboxMode


def main() -> None:
    store = JsonFileSessionStore(".codex_sessions.json")
    client = CodexLocalClient(session_store=store)

    session_name = "todo-session"

    if client.get_session_id(session_name):
        result = client.resume(
            prompt="TODO: continue prompt",
            session_name=session_name,
            last=False,
            json_output=True,
            timeout_seconds=120,
        )
        print("resumed turn status:", result.turn_status)
        print("resumed final message:\n", result.final_message)
        return

    session, first = client.start_thread(
        prompt="TODO: initial prompt",
        sandbox=SandboxMode.READ_ONLY,
        session_name=session_name,
        timeout_seconds=120,
    )
    print("created session:", session.session_name, session.session_id)
    print("first turn status:", first.turn_status)


if __name__ == "__main__":
    main()
