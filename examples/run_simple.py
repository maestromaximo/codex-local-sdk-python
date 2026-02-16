from codex_local_sdk import CodexExecRequest, CodexLocalClient, SandboxMode


def main() -> None:
    client = CodexLocalClient()

    result = client.run(
        CodexExecRequest(
            prompt="Summarize this repository in 5 bullets.",
            sandbox=SandboxMode.READ_ONLY,
        )
    )

    print("Final message:\n")
    print(result.final_message or "<empty>")


if __name__ == "__main__":
    main()
