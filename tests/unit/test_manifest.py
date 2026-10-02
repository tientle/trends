from pathlib import Path

import pytest

from trends_pipeline.manifest import load_manifest


def _write_manifest(path: Path, series: str = "") -> None:
    path.write_text(
        """request:
  request_id: request-001
  retrieved_at: '2026-10-01T12:00:00Z'
  query_url: https://trends.google.com/trends/explore
  geography: US
  start_date: '2023-10-01'
  end_date: '2026-10-01'
  category: All categories
  property: Web Search
  frequency: weekly
raw:
  file: trends.csv
  sha256: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
series:
"""
        + series,
        encoding="utf-8",
    )


def test_load_manifest_preserves_request_and_topic_mapping(tmp_path: Path) -> None:
    path = tmp_path / "manifest.yaml"
    _write_manifest(
        path,
        """  - series_id: brat
    topic_label: Brat
    topic_description: 2024 album
    entity_type: album
    export_column: Brat
""",
    )

    manifest = load_manifest(path)

    assert manifest.request_id == "request-001"
    assert manifest.start_date.isoformat() == "2023-10-01"
    assert manifest.series[0].export_column == "Brat"


def test_manifest_rejects_duplicate_topic_mappings(tmp_path: Path) -> None:
    path = tmp_path / "manifest.yaml"
    entry = """  - series_id: {series_id}
    topic_label: Brat
    topic_description: 2024 album
    entity_type: album
    export_column: {column}
"""
    _write_manifest(path, entry.format(series_id="brat", column="Brat") + entry.format(series_id="brat-copy", column="Brat 2"))

    with pytest.raises(ValueError, match="topic_label values must be unique"):
        load_manifest(path)


def test_manifest_rejects_non_weekly_frequency(tmp_path: Path) -> None:
    path = tmp_path / "manifest.yaml"
    _write_manifest(
        path,
        """  - series_id: brat
    topic_label: Brat
    topic_description: 2024 album
    entity_type: album
    export_column: Brat
""",
    )
    text = path.read_text(encoding="utf-8").replace("frequency: weekly", "frequency: daily")
    path.write_text(text, encoding="utf-8")

    with pytest.raises(ValueError, match="frequency must be weekly"):
        load_manifest(path)