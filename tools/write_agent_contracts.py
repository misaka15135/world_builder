"""Publish/check the JSON Schema copies of the executable agent contracts."""
import argparse
import json

from jsonschema import Draft202012Validator
from world_builder.agents.contracts import CONFIG_SCHEMA, REQUEST_SCHEMA, ROOT, contract_document, response_schema
from world_builder.agents.scene_requirements import SCENE_BRIEF_SCHEMA, SCENE_LINKS_SCHEMA
from world_builder.agents.style_scene import LAYOUT, LAYOUT_PARAMETERS, BUILDING, PLAZA, REVIEW
from world_builder.agents.city_scene import BASE as CITY_BASE, CATALOGUE as CITY_CATALOGUE, LAYOUT as CITY_LAYOUT, CASTLE
from world_builder.agents.nature_scene import BASE as NATURE_BASE, LAYOUT as NATURE_LAYOUT


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    documents = {"agent-response-0.1.0.schema.json": contract_document(),
                 "agent-compact-e-0.1.1.schema.json": response_schema("E", compact_e=True),
                 "agent-request-0.1.0.schema.json": {"$schema": "https://json-schema.org/draft/2020-12/schema", **REQUEST_SCHEMA},
                 "agent-config-0.1.0.schema.json": {"$schema": "https://json-schema.org/draft/2020-12/schema", **CONFIG_SCHEMA},
                 "scene-brief-0.2.0-draft.1.schema.json": SCENE_BRIEF_SCHEMA,
                 "scene-links-0.2.0-draft.1.schema.json": SCENE_LINKS_SCHEMA,
                 "style042-layout-0.1.0.schema.json": LAYOUT,
                 "style042-layout-parameters-0.1.1.schema.json": LAYOUT_PARAMETERS,
                 "style042-building-0.1.0.schema.json": BUILDING,
                 "style042-plaza-0.1.0.schema.json": PLAZA,
                 "style042-review-0.1.0.schema.json": REVIEW,
                 "city045-base-0.1.0.schema.json": CITY_BASE,
                 "city045-catalogue-0.1.0.schema.json": CITY_CATALOGUE,
                 "city045-layout-0.1.0.schema.json": CITY_LAYOUT,
                 "city045-castle-0.1.0.schema.json": CASTLE,
                 "nature046-base-0.1.0.schema.json": NATURE_BASE,
                 "nature046-layout-0.1.0.schema.json": NATURE_LAYOUT}
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
