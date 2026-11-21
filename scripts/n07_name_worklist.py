"""Build the deterministic N-07 human name-confirmation work-list.

Candidates are grouped only when their normalized dHash values are exactly
equal. Distinct hashes at the existing one-bit boundary stay separate and are
flagged for review; similarity never merges a name or transfers confirmation.
The default path uses no OCR runtime.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Mapping

from image_extraction_adapter.pipeline_v0 import (
    DEFAULT_DHASH_THRESHOLD,
    cluster_description_crops,
)
from n04_name_suggestions import (
    CropReference,
    NameRecognition,
    NameSuggester,
    NameSuggestion,
)
from run_n02_product_candidates import (
    CandidateOccurrence,
    aggregate_candidate_occurrences,
    collect_candidate_occurrences,
)

SCHEMA_VERSION = "n07.name-worklist.v1"
SOURCE_SCHEMA_VERSION = "n02.product-candidates.v1"
_CONFIRMATION_SCHEMA_VERSION = "n07.name-confirmations.v1"
_CROP_ID = re.compile(r"^(?P<invoice>[0-9]+)_row(?P<row>[0-9]+)$")
_CLUSTER_ID = re.compile(r"^name-dhash-[0-9a-f]{16}$")


def serialize_worklist(document: dict[str, Any]) -> str:
    return json.dumps(document, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def load_confirmations(path: str | Path) -> dict[str, str]:
    """Load explicit human confirmations keyed by exact stable crop-cluster ID."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("schema_version") != _CONFIRMATION_SCHEMA_VERSION:
        raise ValueError(f"confirmation file must use {_CONFIRMATION_SCHEMA_VERSION!r}")
    entries = data.get("confirmations")
    if not isinstance(entries, list):
        raise ValueError("confirmation file must contain a confirmations array")
    result: dict[str, str] = {}
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise ValueError(f"confirmation entry {index} must be an object")
        cluster_id = entry.get("name_crop_cluster_id")
        confirmed_name = entry.get("confirmed_name")
        if not isinstance(cluster_id, str) or not _CLUSTER_ID.fullmatch(cluster_id):
            raise ValueError(f"confirmation entry {index} has an invalid cluster ID")
        if not isinstance(confirmed_name, str) or not confirmed_name.strip():
            raise ValueError(f"confirmation entry {index} must contain a non-empty confirmed_name")
        if cluster_id in result:
            raise ValueError(f"duplicate confirmation for cluster {cluster_id}")
        result[cluster_id] = confirmed_name.strip()
    return result


def _crop_identity(occurrence: CandidateOccurrence) -> tuple[str, int]:
    match = _CROP_ID.fullmatch(occurrence.source_crop_id)
    if match is None:
        raise ValueError(f"invalid source crop ID: {occurrence.source_crop_id!r}")
    return occurrence.source_crop_id, int(match.group("row"))


def _exact_hash_occurrences(
    occurrences: list[CandidateOccurrence],
    crop_images: Mapping[str, Any],
) -> tuple[list[CandidateOccurrence], dict[str, int]]:
    """Re-key every crop by exact normalized dHash, not threshold similarity."""
    cells: list[SimpleNamespace] = []
    for occurrence in occurrences:
        crop_id, row_index = _crop_identity(occurrence)
        if crop_id not in crop_images:
            raise ValueError(f"missing crop image for {crop_id}")
        cells.append(SimpleNamespace(
            field_name=f"line.{row_index}.description",
            crop_id=crop_id,
            bbox=(0, 0, 1, 1),
            image=crop_images[crop_id],
        ))

    descriptions = cluster_description_crops(cells)
    if len(descriptions) != len(occurrences):
        raise RuntimeError("dHash output count does not match the candidate crop count")

    exact_occurrences: list[CandidateOccurrence] = []
    hash_by_cluster: dict[str, int] = {}
    for occurrence, description in zip(occurrences, descriptions, strict=True):
        try:
            digest = int(description.dhash, 16)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"invalid dHash for {occurrence.source_crop_id}") from exc
        cluster_id = f"name-dhash-{digest:016x}"
        exact_occurrences.append(replace(occurrence, name_crop_cluster_id=cluster_id))
        hash_by_cluster[cluster_id] = digest
    return exact_occurrences, hash_by_cluster


def _near_threshold_neighbors(
    hash_by_cluster: Mapping[str, int],
    *,
    threshold: int = DEFAULT_DHASH_THRESHOLD,
) -> dict[str, tuple[str, ...]]:
    """Return symmetric one-bit-boundary neighbors without joining candidates."""
    cluster_ids = sorted(hash_by_cluster)
    neighbors: dict[str, set[str]] = {cluster_id: set() for cluster_id in cluster_ids}
    for index, left_id in enumerate(cluster_ids):
        for right_id in cluster_ids[index + 1:]:
            distance = (hash_by_cluster[left_id] ^ hash_by_cluster[right_id]).bit_count()
            if distance == threshold:
                neighbors[left_id].add(right_id)
                neighbors[right_id].add(left_id)
    return {cluster_id: tuple(sorted(values)) for cluster_id, values in neighbors.items()}


def _name_confirmation(
    cluster_id: str,
    *,
    confirmed_names: Mapping[str, str],
    near_threshold_cluster_ids: tuple[str, ...],
) -> dict[str, Any]:
    confirmed_name = confirmed_names.get(cluster_id, "")
    if not isinstance(confirmed_name, str):
        raise TypeError(f"confirmed_name for {cluster_id} must be a string")
    confirmed_name = confirmed_name.strip()
    if confirmed_name and len(confirmed_name) > 512:
        raise ValueError(f"confirmed_name for {cluster_id} exceeds 512 characters")

    review_required = bool(near_threshold_cluster_ids)
    if review_required:
        status = "REVIEW"
        reasons = ["NEAR_THRESHOLD_CLUSTER"]
    elif confirmed_name:
        status = "CONFIRMED"
        reasons = []
    else:
        status = "UNCONFIRMED"
        reasons = []
    return {
        "confirmed_name": confirmed_name,
        "confirmation_status": status,
        "confirmation_source_cluster_id": cluster_id if confirmed_name else None,
        "review_required": review_required,
        "review_reasons": reasons,
        "near_threshold_cluster_ids": list(near_threshold_cluster_ids),
    }


def build_name_worklist_from_occurrences(
    occurrences: list[CandidateOccurrence],
    crop_images: Mapping[str, Any],
    output_dir: str | Path,
    *,
    confirmed_names: Mapping[str, str] | None = None,
    suggester: NameSuggester | None = None,
) -> dict[str, Any]:
    """Build candidate work items and write one representative crop image each."""
    if not occurrences:
        raise ValueError("N-07 requires at least one ProductCandidate occurrence")
    if suggester is not None:
        for attribute in ("engine_name", "engine_version", "model_version", "suggest"):
            if not hasattr(suggester, attribute):
                raise TypeError(f"suggester must declare {attribute}")

    confirmations = dict(confirmed_names or {})
    for cluster_id, name in confirmations.items():
        if not isinstance(cluster_id, str) or not _CLUSTER_ID.fullmatch(cluster_id):
            raise ValueError(f"invalid confirmation cluster ID: {cluster_id!r}")
        if not isinstance(name, str) or not name.strip():
            raise ValueError(f"confirmed_name for {cluster_id} must be a non-empty string")

    exact_occurrences, hash_by_cluster = _exact_hash_occurrences(occurrences, crop_images)
    candidates = aggregate_candidate_occurrences(exact_occurrences)
    near_neighbors = _near_threshold_neighbors(hash_by_cluster)
    destination = Path(output_dir).expanduser().resolve()
    crop_dir = destination / "crops"
    crop_dir.mkdir(parents=True, exist_ok=True)

    work_items: list[dict[str, Any]] = []
    for candidate in candidates:
        candidate_id = candidate.name_crop_cluster_id
        representative_crop_id = candidate.source_crop_ids[0]
        crop_image = crop_images[representative_crop_id]
        relative_crop_file = f"crops/{candidate_id}.png"
        crop_path = destination / relative_crop_file
        crop_image.save(crop_path, format="PNG", optimize=False)
        crop_sha256 = hashlib.sha256(crop_path.read_bytes()).hexdigest()

        candidate_document = candidate.to_dict()
        neighbor_ids = near_neighbors.get(candidate_id, ())
        candidate_document["name_confirmation"] = _name_confirmation(
            candidate_id,
            confirmed_names=confirmations,
            near_threshold_cluster_ids=neighbor_ids,
        )
        candidate_document["name_suggestions"] = []
        if suggester is not None:
            recognition = suggester.suggest(crop_path)
            if not isinstance(recognition, NameRecognition):
                raise TypeError("suggester.suggest() must return NameRecognition")
            reference_path = candidate_document["reference_crop_file"]
            suggestion = NameSuggestion(
                lines=recognition.lines,
                confidence=recognition.confidence,
                engine=str(suggester.engine_name),
                engine_version=str(suggester.engine_version),
                model_version=str(suggester.model_version),
                crop_reference=CropReference(
                    crop_id=representative_crop_id,
                    file=reference_path,
                    sha256=crop_sha256,
                ),
            )
            candidate_document["name_suggestions"] = [suggestion.to_dict()]

        work_items.append({
            "candidate": candidate_document,
            "crop_image": {
                "file": relative_crop_file,
                "sha256": crop_sha256,
            },
        })

    work_items.sort(key=lambda item: item["candidate"]["name_crop_cluster_id"])
    return {
        "schema_version": SCHEMA_VERSION,
        "source_schema_version": SOURCE_SCHEMA_VERSION,
        "confirmation_reuse_key": "name_crop_cluster_id",
        "cluster_policy": {
            "assignment": "exact-dhash-only",
            "near_threshold_distance": DEFAULT_DHASH_THRESHOLD,
            "near_threshold_action": "review-without-merge",
        },
        "name_suggestions_enabled": suggester is not None,
        "work_items": work_items,
    }


def build_name_worklist(
    repo_root: Path,
    output_dir: str | Path,
    *,
    captured_at: str | None = None,
    confirmed_names: Mapping[str, str] | None = None,
    suggester: NameSuggester | None = None,
) -> dict[str, Any]:
    """Build N-02 source occurrences and render them into N-07 work items."""
    occurrences, crop_images = collect_candidate_occurrences(
        Path(repo_root).resolve(),
        captured_at=captured_at,
    )
    return build_name_worklist_from_occurrences(
        occurrences,
        crop_images,
        output_dir,
        confirmed_names=confirmed_names,
        suggester=suggester,
    )


def write_confirmation_file(path: str | Path, confirmed_names: Mapping[str, str]) -> None:
    """Write a canonical machine-readable input for future human confirmations."""
    entries = [
        {"name_crop_cluster_id": cluster_id, "confirmed_name": confirmed_names[cluster_id]}
        for cluster_id in sorted(confirmed_names)
    ]
    document = {
        "schema_version": _CONFIRMATION_SCHEMA_VERSION,
        "confirmations": entries,
    }
    Path(path).write_text(serialize_worklist(document), encoding="utf-8", newline="\n")
