"""Template: schema-constrained output with run_with_schema."""

import json

from codex_local_sdk import CodexLocalClient, SandboxMode


def main() -> None:
    client = CodexLocalClient()

    schema = {
        "type": "object",
        "properties": {
            "summary": {"type": "string"},
            "actions": {
                "type": "array",
                "items": {"type": "string"},
            },
        },
        "required": ["summary", "actions"],
        "additionalProperties": False,
    }

    result = client.run_with_schema(
        prompt="TODO: replace with your prompt",
        schema=schema,
        output_json_path="structured_output.json",
        sandbox=SandboxMode.READ_ONLY,
        timeout_seconds=120,
    )

    print("return_code:", result.return_code)
    print("final_message:\n", result.final_message)

    if result.final_message:
        parsed = json.loads(result.final_message)
        print("parsed keys:", sorted(parsed.keys()))


if __name__ == "__main__":
    main()
