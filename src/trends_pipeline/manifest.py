"""Load and validate the metadata that binds one export to one Trends request."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class SeriesMapping:
    series_id: str
    topic_label: str
    topic_description: str
    entity_type: str
    export_column: str


@dataclass(frozen=True)
class Manifest:
    request_id: str
    retrieved_at: str
    query_url: str
    geography: str
    start_date: date
    end_date: date
    category: str
    property: str
    frequency: str
    raw_file: str
    sha256: str
    series: tuple[SeriesMapping, ...]


def _required(mapping: dict[str, Any], key: str, context: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{context}.{key} must be a non-empty string")
    return value.strip()


def _parse_date(value: Any, key: str) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError as error:
            raise ValueError(f"request.{key} must use YYYY-MM-DD") from error
    raise ValueError(f"request.{key} must use YYYY-MM-DD")


def load_manifest(path: Path) -> Manifest:
    """Load a YAML manifest and reject missing or ambiguous series mappings."""
    try:
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        raise ValueError(f"Cannot read manifest {path}: {error}") from error

    if not isinstance(document, dict):
        raise ValueError("Manifest root must be a YAML mapping")
    request = document.get("request")
    raw = document.get("raw")
    if not isinstance(request, dict) or not isinstance(raw, dict):
        raise ValueError("Manifest must contain request and raw mappings")

    start_date = _parse_date(request.get("start_date"), "start_date")
    end_date = _parse_date(request.get("end_date"), "end_date")
    if start_date >= end_date:
        raise ValueError("request.start_date must be earlier than request.end_date")

    frequency = _required(request, "frequency", "request")
    if frequency.lower() not in {"week", "weekly"}:
        raise ValueError("request.frequency must be weekly")

    entries = document.get("series")
    if not isinstance(entries, list) or not entries:
        raise ValueError("Manifest series must be a non-empty list")

    series: list[SeriesMapping] = []
    for index, entry in enumerate(entries):
        context = f"series[{index}]"
        if not isinstance(entry, dict):
            raise ValueError(f"{context} must be a YAML mapping")
        series.append(
            SeriesMapping(
                series_id=_required(entry, "series_id", context),
                topic_label=_required(entry, "topic_label", context),
                topic_description=_required(entry, "topic_description", context),
                entity_type=_required(entry, "entity_type", context),
                export_column=_required(entry, "export_column", context),
            )
        )

    for field, values in (
        ("series_id", [item.series_id for item in series]),
        ("topic_label", [item.topic_label for item in series]),
        ("export_column", [item.export_column for item in series]),
    ):
        if len(values) != len(set(values)):
            raise ValueError(f"Series {field} values must be unique")

    retrieved_at = _required(request, "retrieved_at", "request")
    try:
        datetime.fromisoformat(retrieved_at.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError("request.retrieved_at must be an ISO-8601 timestamp") from error

    checksum = _required(raw, "sha256", "raw").lower()
    if len(checksum) != 64 or any(character not in "0123456789abcdef" for character in checksum):
        raise ValueError("raw.sha256 must be a 64-character hexadecimal SHA-256")

    return Manifest(
        request_id=_required(request, "request_id", "request"),
        retrieved_at=retrieved_at,
        query_url=_required(request, "query_url", "request"),
        geography=_required(request, "geography", "request"),
        start_date=start_date,
        end_date=end_date,
        category=_required(request, "category", "request"),
        property=_required(request, "property", "request"),
        frequency=frequency,
        raw_file=_required(raw, "file", "raw"),
        sha256=checksum,
        series=tuple(series),
    )