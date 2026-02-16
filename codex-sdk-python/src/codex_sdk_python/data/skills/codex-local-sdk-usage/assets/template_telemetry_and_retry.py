"""Template: telemetry hook plus retry policy for robust sync execution."""

from codex_local_sdk import (
    CodexClientEvent,
    CodexExecFailedError,
    CodexExecRequest,
    CodexLocalClient,
    RetryPolicy,
    SandboxMode,
)


def on_event(event: CodexClientEvent) -> None:
    print(
        event.type,
        event.operation,
        event.attempt,
        event.return_code,
        event.turn_status,
    )


def main() -> None:
    client = CodexLocalClient(
        retry_policy=RetryPolicy(
            max_attempts=3,
            initial_backoff_seconds=0.5,
            backoff_multiplier=2.0,
            max_backoff_seconds=4.0,
            retry_on_exit_codes=None,
            jitter_ratio=0.2,
            max_total_retry_seconds=10.0,
            retry_on_timeouts=True,
        ),
        event_hook=on_event,
    )

    request = CodexExecRequest(
        prompt="TODO: replace with your prompt",
        sandbox=SandboxMode.READ_ONLY,
        json_output=True,
    )

    try:
        result = client.run(request, timeout_seconds=60)
    except CodexExecFailedError as exc:
        print("failed return_code:", exc.result.return_code)
        print("stderr:\n", exc.result.stderr)
        return

    print("success turn_status:", result.turn_status)
    print("final_message:\n", result.final_message)


if __name__ == "__main__":
    main()
