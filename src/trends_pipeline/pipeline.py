"""Orchestrate checksum verification, validation, features, and output writing."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from trends_pipeline.csv_export import parse_export
from trends_pipeline.features import calculate_features
from trends_pipeline.manifest import Manifest, load_manifest
from trends_pipeline.validation import validate_export


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _validate_input_path(input_path: Path, manifest: Manifest) -> str:
    if Path(manifest.raw_file).name != input_path.name:
        raise ValueError(
            f"Manifest raw.file is {manifest.raw_file!r}, but input file is {input_path.name!r}"
        )
    actual_hash = sha256_file(input_path)
    if actual_hash != manifest.sha256:
        raise ValueError(
            f"Raw CSV SHA-256 does not match manifest: expected {manifest.sha256}, got {actual_hash}"
        )
    return actual_hash


def _request_report(manifest: Manifest) -> dict[str, object]:
    return {
        "request_id": manifest.request_id,
        "retrieved_at": manifest.retrieved_at,
        "query_url": manifest.query_url,
        "geography": manifest.geography,
        "start_date": manifest.start_date.isoformat(),
        "end_date": manifest.end_date.isoformat(),
        "category": manifest.category,
        "property": manifest.property,
        "frequency": manifest.frequency,
        "series": [
            {
                "series_id": item.series_id,
                "topic_label": item.topic_label,
                "topic_description": item.topic_description,
                "entity_type": item.entity_type,
                "export_column": item.export_column,
            }
            for item in manifest.series
        ],
    }


def _write_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def validate_files(input_path: Path, manifest_path: Path) -> tuple[dict[str, Any], Any, Any]:
    """Validate a raw export and return its report, tidy data, and features."""
    manifest = load_manifest(manifest_path)
    if len(manifest.series) != 5:
        raise ValueError("Manifest must map exactly five Topics for the approved study")
    checksum = _validate_input_path(input_path, manifest)
    parsed = parse_export(input_path)
    tidy, warnings, quality = validate_export(parsed, manifest)
    features = calculate_features(tidy)
    report: dict[str, Any] = {
        "valid": True,
        "request": _request_report(manifest),
        "input": {"file": manifest.raw_file, "sha256": checksum},
        "quality": quality,
        "warnings": warnings,
    }
    return report, tidy, features


def run_pipeline(
    input_path: Path,
    manifest_path: Path,
    output_dir: Path,
    report_path: Path,
) -> dict[str, Any]:
    """Validate inputs and write tidy time-series, features, and report files."""
    report, tidy, features = validate_files(input_path, manifest_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    tidy.to_csv(output_dir / "time_series.csv", index=False)
    features.to_csv(output_dir / "features.csv", index=False)
    _write_report(report_path, report)
    return report


def write_validation_report(path: Path, report: dict[str, Any]) -> None:
    """Write a validation report, including failures, as JSON."""
    _write_report(path, report)