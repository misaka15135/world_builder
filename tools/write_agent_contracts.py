"""Publish/check the JSON Schema copies of the executable agent contracts."""
import argparse
import json

from jsonschema import Draft202012Validator
from world_builder.agents.contracts import CONFIG_SCHEMA, REQUEST_SCHEMA, ROOT, contract_document


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    documents = {"agent-response-0.1.0.schema.json": contract_document(),
                 "agent-request-0.1.0.schema.json": {"$schema": "https://json-schema.org/draft/2020-12/schema", **REQUEST_SCHEMA},
                 "agent-config-0.1.0.schema.json": {"$schema": "https://json-schema.org/draft/2020-12/schema", **CONFIG_SCHEMA}}
    for name, schema in documents.items():
        Draft202012Validator.check_schema(schema)
        path = ROOT / "schemas" / name
        data = (json.dumps(schema, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        if args.check:
            if not path.exists() or path.read_bytes() != data:
                raise SystemExit(f"Schema drift: {path}")
        else:
            path.write_bytes(data)
    print("Agent response/config schemas are valid and in sync.")


if __name__ == "__main__":
    main()
