from __future__ import annotations

import json
import hashlib
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    path: str
    message: str

    def __str__(self) -> str:
        return f"{self.code} at {self.path}: {self.message}"


class PackageValidationError(ValueError):
    def __init__(self, issues: Sequence[ValidationIssue]):
        self.issues = list(issues)
        super().__init__("\n".join(str(issue) for issue in self.issues))


def _default_schema_path() -> Path:
    return Path(__file__).resolve().parents[3] / "schemas" / "wir-package-0.1.0.schema.json"


def _schema_issues(package: Mapping[str, Any], schema_path: Path) -> List[ValidationIssue]:
    try:
        from jsonschema import Draft202012Validator, FormatChecker
    except ImportError as exc:  # pragma: no cover - exercised by deployment setup
        raise RuntimeError(
            "JSON Schema validation requires jsonschema; install requirements-dev.txt"
        ) from exc

    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    issues: List[ValidationIssue] = []
    for error in sorted(validator.iter_errors(package), key=lambda item: list(item.absolute_path)):
        path = "/" + "/".join(str(part) for part in error.absolute_path)
        issues.append(ValidationIssue("schema.invalid", path or "/", error.message))
    return issues


def _detect_cycle(edges: Mapping[str, Sequence[str]]) -> List[str] | None:
    visiting: set[str] = set()
    visited: set[str] = set()

    def walk(node: str, trail: List[str]) -> List[str] | None:
        if node in visiting:
            start = trail.index(node)
            return trail[start:] + [node]
        if node in visited:
            return None
        visiting.add(node)
        trail.append(node)
        for neighbor in edges.get(node, []):
            cycle = walk(neighbor, trail)
            if cycle:
                return cycle
        trail.pop()
        visiting.remove(node)
        visited.add(node)
        return None

    for node in edges:
        cycle = walk(node, [])
        if cycle:
            return cycle
    return None


def _semantic_issues(package: Mapping[str, Any]) -> List[ValidationIssue]:
    if not isinstance(package.get("records"), list) or not isinstance(package.get("manifest"), dict):
        return []

    manifest = package["manifest"]
    records: List[Dict[str, Any]] = [r for r in package["records"] if isinstance(r, dict)]
    issues: List[ValidationIssue] = []
    by_id: Dict[str, Dict[str, Any]] = {}
    by_type: Dict[str, List[Dict[str, Any]]] = {}

    for index, record in enumerate(records):
        record_id = record.get("id")
        record_type = record.get("record_type")
        if isinstance(record_id, str):
            if record_id in by_id:
                issues.append(ValidationIssue("identity.duplicate", f"/records/{index}/id", record_id))
            else:
                by_id[record_id] = record
        if isinstance(record_type, str):
            by_type.setdefault(record_type, []).append(record)

    if len(by_type.get("world_spec", [])) != 1:
        issues.append(ValidationIssue("cardinality.world_spec", "/records", "exactly one world_spec is required"))

    matching_revisions = [r for r in by_type.get("revision", []) if r.get("id") == manifest.get("revision_id")]
    if len(matching_revisions) != 1:
        issues.append(ValidationIssue("revision.head_missing", "/manifest/revision_id", "must reference exactly one revision record"))
    elif matching_revisions[0].get("world_id") != manifest.get("world_id"):
        issues.append(ValidationIssue("revision.world_mismatch", "/manifest/world_id", "head revision belongs to another world"))

    entities = {r["id"]: r for r in by_type.get("entity", []) if "id" in r}
    constraints = {r["id"]: r for r in by_type.get("constraint", []) if "id" in r}
    recipes = {r["id"]: r for r in by_type.get("recipe", []) if "id" in r}
    profiles = {r["id"]: r for r in by_type.get("target_profile", []) if "id" in r}
    revisions = {r["id"]: r for r in by_type.get("revision", []) if "id" in r}

    containment: Dict[str, List[str]] = {entity_id: [] for entity_id in entities}
    for entity_id, entity in entities.items():
        parent_id = entity.get("parent_id")
        if parent_id is not None:
            if parent_id not in entities:
                issues.append(ValidationIssue("reference.parent_missing", f"/records/{entity_id}/parent_id", str(parent_id)))
            else:
                containment[entity_id].append(parent_id)
        for constraint_id in entity.get("constraint_ids", []):
            if constraint_id not in constraints:
                issues.append(ValidationIssue("reference.constraint_missing", f"/records/{entity_id}/constraint_ids", constraint_id))
        recipe_id = entity.get("recipe_id")
        if recipe_id is not None and recipe_id not in recipes:
            issues.append(ValidationIssue("reference.recipe_missing", f"/records/{entity_id}/recipe_id", recipe_id))
        bounds = entity.get("bounds", {})
        if "min" in bounds and "max" in bounds:
            if any(lo > hi for lo, hi in zip(bounds["min"], bounds["max"])):
                issues.append(ValidationIssue("geometry.bounds_inverted", f"/records/{entity_id}/bounds", "min must not exceed max"))
        transform = entity.get("transform", {})
        quaternion = transform.get("rotation_xyzw")
        if isinstance(quaternion, list) and len(quaternion) == 4:
            norm = math.sqrt(sum(float(value) ** 2 for value in quaternion))
            if abs(norm - 1.0) > 1e-9:
                issues.append(ValidationIssue("geometry.quaternion_not_normalized", f"/records/{entity_id}/transform/rotation_xyzw", f"norm={norm:.12g}"))

    cycle = _detect_cycle(containment)
    if cycle:
        issues.append(ValidationIssue("graph.containment_cycle", "/records", " -> ".join(cycle)))

    for relation in by_type.get("relation", []):
        relation_id = relation.get("id", "unknown")
        for field, refs in (("source_id", [relation.get("source_id")]), ("target_ids", relation.get("target_ids", []))):
            for ref in refs:
                if ref not in entities:
                    issues.append(ValidationIssue("reference.relation_entity_missing", f"/records/{relation_id}/{field}", str(ref)))

    for constraint_id, constraint in constraints.items():
        for ref in constraint.get("scope_entity_ids", []):
            if ref not in entities:
                issues.append(ValidationIssue("reference.constraint_entity_missing", f"/records/{constraint_id}/scope_entity_ids", ref))
        checked_revision = constraint.get("validation", {}).get("checked_revision_id")
        if checked_revision not in revisions:
            issues.append(ValidationIssue("reference.checked_revision_missing", f"/records/{constraint_id}/validation", str(checked_revision)))

    recipe_edges: Dict[str, List[str]] = {}
    for recipe_id, recipe in recipes.items():
        dependencies = recipe.get("dependency_recipe_ids", [])
        recipe_edges[recipe_id] = list(dependencies)
        for ref in dependencies:
            if ref not in recipes:
                issues.append(ValidationIssue("reference.recipe_dependency_missing", f"/records/{recipe_id}/dependency_recipe_ids", ref))
        outcome = recipe.get("outcome", {})
        feasibility = outcome.get("feasibility")
        termination = outcome.get("termination_reason")
        proof_ref = outcome.get("proof_ref")
        if feasibility == "infeasible" and (termination != "completed" or not proof_ref):
            issues.append(ValidationIssue("outcome.infeasible_without_proof", f"/records/{recipe_id}/outcome", "infeasible requires completed proof and proof_ref"))
        if feasibility == "feasible" and termination != "completed":
            issues.append(ValidationIssue("outcome.feasible_not_completed", f"/records/{recipe_id}/outcome", "feasible requires completed termination"))
        if termination in {"search_exhausted", "timeout", "budget_exhausted", "cancelled", "error"} and feasibility != "unknown":
            issues.append(ValidationIssue("outcome.uncertain_termination", f"/records/{recipe_id}/outcome", "non-completed termination must use unknown feasibility"))
    cycle = _detect_cycle(recipe_edges)
    if cycle:
        issues.append(ValidationIssue("graph.recipe_cycle", "/records", " -> ".join(cycle)))

    for spec in by_type.get("world_spec", []):
        bounds = spec.get("region_bounds", {})
        if "min" in bounds and "max" in bounds and any(lo > hi for lo, hi in zip(bounds["min"], bounds["max"])):
            issues.append(ValidationIssue("geometry.world_bounds_inverted", f"/records/{spec.get('id')}/region_bounds", "min must not exceed max"))
        for ref in spec.get("target_profile_ids", []):
            if ref not in profiles:
                issues.append(ValidationIssue("reference.target_profile_missing", f"/records/{spec.get('id')}/target_profile_ids", ref))

    for report in by_type.get("export_report", []):
        report_id = report.get("id", "unknown")
        if report.get("revision_id") not in revisions:
            issues.append(ValidationIssue("reference.export_revision_missing", f"/records/{report_id}/revision_id", str(report.get("revision_id"))))
        if report.get("target_profile_id") not in profiles:
            issues.append(ValidationIssue("reference.export_profile_missing", f"/records/{report_id}/target_profile_id", str(report.get("target_profile_id"))))
        counts = {key: 0 for key in ("preserved", "approximated", "omitted", "unsupported", "failed")}
        for item in report.get("items", []):
            source_id = item.get("source_id")
            if source_id not in entities:
                issues.append(ValidationIssue("reference.export_source_missing", f"/records/{report_id}/items", str(source_id)))
            classification = item.get("classification")
            if classification in counts:
                counts[classification] += 1
        if report.get("summary") != counts:
            issues.append(ValidationIssue("export.summary_mismatch", f"/records/{report_id}/summary", f"expected {counts}"))

    if matching_revisions:
        head = matching_revisions[0]
        hard_failures = sum(1 for c in constraints.values() if c.get("severity") == "hard" and c.get("validation", {}).get("state") == "fail")
        unknown = sum(1 for c in constraints.values() if c.get("validation", {}).get("state") == "unknown")
        summary = head.get("validation_summary", {})
        if summary.get("hard_failures") != hard_failures or summary.get("unknown_checks") != unknown:
            issues.append(ValidationIssue("revision.validation_summary_mismatch", f"/records/{head.get('id')}/validation_summary", f"expected hard_failures={hard_failures}, unknown_checks={unknown}"))

    return issues


def _resource_issues(package: Mapping[str, Any], package_dir: Path) -> List[ValidationIssue]:
    issues: List[ValidationIssue] = []
    records = package.get("records", [])
    if not isinstance(records, list):
        return issues
    for record in records:
        if not isinstance(record, dict) or record.get("record_type") != "asset":
            continue
        uri = record.get("uri")
        if not isinstance(uri, str) or "://" in uri:
            continue
        candidate = (package_dir / uri).resolve()
        try:
            candidate.relative_to(package_dir.resolve())
        except ValueError:
            issues.append(ValidationIssue("resource.path_escape", f"/records/{record.get('id')}/uri", uri))
            continue
        if not candidate.is_file():
            issues.append(ValidationIssue("resource.missing", f"/records/{record.get('id')}/uri", uri))
            continue
        actual_hash = "sha256:" + hashlib.sha256(candidate.read_bytes()).hexdigest()
        if actual_hash != record.get("content_hash"):
            issues.append(ValidationIssue("resource.hash_mismatch", f"/records/{record.get('id')}/content_hash", f"expected {record.get('content_hash')}, got {actual_hash}"))
    return issues


def validate_package(package: Mapping[str, Any], schema_path: Path | None = None) -> None:
    schema_path = schema_path or _default_schema_path()
    issues = _schema_issues(package, schema_path)
    if not issues:
        issues.extend(_semantic_issues(package))
    if issues:
        raise PackageValidationError(issues)


def load_and_validate(path: str | Path, schema_path: Path | None = None) -> Dict[str, Any]:
    package_path = Path(path)
    package = json.loads(package_path.read_text(encoding="utf-8"))
    validate_package(package, schema_path)
    resource_issues = _resource_issues(package, package_path.parent)
    if resource_issues:
        raise PackageValidationError(resource_issues)
    return package
