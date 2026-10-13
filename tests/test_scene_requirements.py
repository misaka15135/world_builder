"""Draft v0.2 requirement categories are checked without running the v0.1 pipeline."""
from copy import deepcopy

import pytest
from jsonschema import Draft202012Validator

from world_builder.agents.contracts import AgentError, ROOT, strict_json
from world_builder.agents.scene_requirements import (
    SCENE_BRIEF_SCHEMA, SCENE_LINKS_SCHEMA, VERSION, validate_scene_brief,
    validate_scene_links,
)


@pytest.fixture
def cases():
    return strict_json((ROOT / "examples/scene_requirements_v02.json").read_bytes())["cases"]


@pytest.mark.parametrize("case", ["street", "forest", "camp"])
def test_typed_brief_and_cross_stage_links_accept_three_scene_kinds(cases, case):
    brief, links = cases[case]["brief"], cases[case]["links"]
    validate_scene_links(brief, links, region_m=32, max_sites=1)
    if case == "forest":
        assert not links["sites"] and not links["roads"]
    if case == "street":
        assert sum(r["min_count"] for r in brief["requirements"] if r["kind"] == "site") == 1


def test_schema_files_match_executable_draft_and_legacy_remains_separate(cases):
    for name, schema in (("scene-brief-0.2.0-draft.1.schema.json", SCENE_BRIEF_SCHEMA),
                         ("scene-links-0.2.0-draft.1.schema.json", SCENE_LINKS_SCHEMA)):
        Draft202012Validator.check_schema(schema)
        assert strict_json((ROOT / "schemas" / name).read_bytes()) == schema
    legacy = strict_json((ROOT / "examples/agent_scene.responses.json").read_bytes())
    with pytest.raises(AgentError) as exc:
        validate_scene_brief(legacy["responses"]["A:scene"], region_m=32, max_sites=4)
    assert exc.value.code == "scene.brief_schema"
    assert cases["street"]["brief"]["contract_version"] == VERSION


@pytest.mark.parametrize("mutation,code", [
    (lambda b: b["requirements"][0].update(min_count=2, max_count=2), "scene.site_budget"),
    (lambda b: b["requirements"][0].update(min_count=0), "scene.required_count"),
    (lambda b: b["requirements"][1].update(connects=["shop_room"]), "scene.road_reference"),
    (lambda b: b["requirements"][2].update(parent_site_id="street"), "scene.interior_parent"),
    (lambda b: b["acceptance_criteria"].pop(), "scene.criterion_coverage"),
    (lambda b: b["relations"][0].update(object_id="missing"), "scene.relation_reference"),
])
def test_brief_rejects_bad_counts_and_refs(cases, mutation, code):
    brief = deepcopy(cases["street"]["brief"])
    mutation(brief)
    with pytest.raises(AgentError) as exc:
        validate_scene_brief(brief, region_m=32, max_sites=1)
    assert exc.value.code == code


@pytest.mark.parametrize("mutation,code", [
    (lambda links: links["catalogue"][0].update(requirement_id="street"), "scene.catalogue_kind"),
    (lambda links: links["sites"][0].update(catalogue_id="missing"), "scene.site_kind"),
    (lambda links: links["roads"][0].update(requirement_id="shop"), "scene.road_kind"),
    (lambda links: links["interior_spaces"][0].update(requirement_id="street"), "scene.interior_kind"),
    (lambda links: links["roads"].clear(), "scene.coverage"),
    (lambda links: links["sites"].clear(), "scene.interior_kind"),
])
def test_cross_stage_links_reject_category_confusion_and_missing_required_objects(cases, mutation, code):
    brief = cases["street"]["brief"]
    links = deepcopy(cases["street"]["links"])
    mutation(links)
    with pytest.raises(AgentError) as exc:
        validate_scene_links(brief, links, region_m=32, max_sites=1)
    assert exc.value.code == code


def test_road_cannot_be_sneaked_in_as_a_site_type(cases):
    brief = cases["street"]["brief"]
    links = deepcopy(cases["street"]["links"])
    links["catalogue"].append({"id": "street_type", "requirement_id": "street", "kind": "site"})
    links["sites"].append({"id": "street_site", "catalogue_id": "street_type"})
    links["roads"].clear()
    with pytest.raises(AgentError) as exc:
        validate_scene_links(brief, links, region_m=32, max_sites=2)
    assert exc.value.code == "scene.catalogue_kind"


def test_optional_road_is_not_forced_into_a_natural_camp(cases):
    brief, links = deepcopy(cases["camp"]["brief"]), deepcopy(cases["camp"]["links"])
    brief["requirements"].append({"id": "track", "kind": "road_network", "description": "Optional footpath",
                                  "necessity": "optional", "connects": ["cabin"]})
    brief["acceptance_criteria"][0]["requirement_ids"].append("track")
    validate_scene_links(brief, links, region_m=32, max_sites=1)


def test_forest_needs_no_building_site_budget(cases):
    brief, links = cases["forest"]["brief"], cases["forest"]["links"]
    validate_scene_links(brief, links, region_m=32, max_sites=0)


def test_draft_rejects_unknown_fields_and_versions(cases):
    brief = deepcopy(cases["forest"]["brief"])
    brief["requirements"][0]["execute_code"] = "ignored"
    with pytest.raises(AgentError) as exc:
        validate_scene_brief(brief, region_m=32, max_sites=0)
    assert exc.value.code == "scene.brief_schema"
    brief = deepcopy(cases["forest"]["brief"])
    brief["contract_version"] = "0.1.0"
    with pytest.raises(AgentError) as exc:
        validate_scene_brief(brief, region_m=32, max_sites=0)
    assert exc.value.code == "scene.brief_schema"
