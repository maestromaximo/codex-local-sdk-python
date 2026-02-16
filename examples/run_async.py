import asyncio

from codex_local_sdk import CodexExecRequest, CodexLocalClient, SandboxMode


async def main() -> None:
    client = CodexLocalClient()

    result = await client.run_async(
        CodexExecRequest(
            prompt="Summarize this repository in 5 bullets.",
            sandbox=SandboxMode.READ_ONLY,
        )
    )
    print("Async final message:")
    print(result.final_message or "<empty>")

    live = await client.run_live_async(
        CodexExecRequest(
            prompt="Stream event types while summarizing repository risks.",
            sandbox=SandboxMode.READ_ONLY,
            json_output=True,
        )
    )
    print(f"Async live PID: {live.pid}")
    async for event in live.iter_events():
        print("event:", event.type)

    final = await live.wait()
    print("Async live final message:")
    print(final.final_message or "<empty>")


if __name__ == "__main__":
    asyncio.run(main())
