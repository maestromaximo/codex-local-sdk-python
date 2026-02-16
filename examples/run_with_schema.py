import json

from codex_local_sdk import CodexLocalClient, SandboxMode


def main() -> None:
    client = CodexLocalClient()

    schema = {
        "type": "object",
        "properties": {
            "project_name": {"type": "string"},
            "top_languages": {
                "type": "array",
                "items": {"type": "string"},
            },
        },
        "required": ["project_name", "top_languages"],
        "additionalProperties": False,
    }

    result = client.run_with_schema(
        prompt="Extract project metadata from this repository.",
        schema=schema,
        output_json_path="project_metadata.json",
        sandbox=SandboxMode.READ_ONLY,
    )

    print("Schema-constrained output:")
    print(result.final_message)

    if result.final_message:
        parsed = json.loads(result.final_message)
        print("Parsed project name:", parsed.get("project_name"))


if __name__ == "__main__":
    main()
