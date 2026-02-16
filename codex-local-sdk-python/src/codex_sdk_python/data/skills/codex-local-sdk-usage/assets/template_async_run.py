"""Template: async run and async live streaming."""

import asyncio

from codex_local_sdk import CodexExecRequest, CodexLocalClient, SandboxMode


async def main() -> None:
    client = CodexLocalClient()

    result = await client.run_async(
        CodexExecRequest(
            prompt="TODO: replace with your prompt",
            sandbox=SandboxMode.READ_ONLY,
        ),
        timeout_seconds=120,
    )
    print("async return_code:", result.return_code)
    print("async final_message:\n", result.final_message)

    live = await client.run_live_async(
        CodexExecRequest(
            prompt="TODO: streaming prompt",
            sandbox=SandboxMode.READ_ONLY,
            json_output=True,
        )
    )
    async for event in live.iter_events():
        print("event:", event.type)

    final = await live.wait()
    print("live turn_status:", final.turn_status)


if __name__ == "__main__":
    asyncio.run(main())
