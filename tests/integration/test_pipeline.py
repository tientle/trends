import json
import shutil
from pathlib import Path

import pandas as pd
import pytest
import yaml

from trends_pipeline.pipeline import run_pipeline, validate_files


FIXTURE_DIR = Path(__file__).parents[1] / "fixtures" / "synthetic"


def test_synthetic_export_runs_through_pipeline_and_writes_expected_schemas(
    tmp_path: Path,
) -> None:
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    raw_path = input_dir / "trends.csv"
    manifest_path = input_dir / "manifest.yaml"
    shutil.copyfile(FIXTURE_DIR / "trends.csv", raw_path)
    shutil.copyfile(FIXTURE_DIR / "manifest.yaml", manifest_path)

    report, tidy, features = validate_files(raw_path, manifest_path)
    assert report["valid"] is True
    assert report["request"]["request_id"] == "synthetic-request-001"
    assert report["quality"]["weekly_rows"] == 4
    assert report["quality"]["missing_values_by_series"]["synthetic_3"] == 1
    assert len(tidy) == 20
    assert len(features) == 5

    output_dir = tmp_path / "processed"
    report_path = tmp_path / "reports" / "validation.json"
    written_report = run_pipeline(raw_path, manifest_path, output_dir, report_path)
    time_series = pd.read_csv(output_dir / "time_series.csv")
    feature_output = pd.read_csv(output_dir / "features.csv")
    report_output = json.loads(report_path.read_text(encoding="utf-8"))

    assert written_report["valid"] is True
    assert list(time_series.columns) == [
        "request_id",
        "series_id",
        "topic_label",
        "topic_description",
        "entity_type",
        "date",
        "interest_index",
        "geography",
        "frequency",
        "partial_week",
    ]
    assert len(time_series) == 20
    assert list(feature_output["series_id"]) == [
        "synthetic_1",
        "synthetic_2",
        "synthetic_3",
        "synthetic_4",
        "synthetic_5",
    ]
    assert report_output["input"]["file"] == "trends.csv"
    assert "not Google Trends data" in report_output["request"]["series"][0]["topic_description"]


def test_pipeline_rejects_raw_file_checksum_mismatch(tmp_path: Path) -> None:
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    raw_path = input_dir / "trends.csv"
    manifest_path = input_dir / "manifest.yaml"
    shutil.copyfile(FIXTURE_DIR / "trends.csv", raw_path)
    shutil.copyfile(FIXTURE_DIR / "manifest.yaml", manifest_path)
    raw_path.write_text(raw_path.read_text(encoding="utf-8") + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="SHA-256 does not match"):
        validate_files(raw_path, manifest_path)


def test_pipeline_requires_exactly_five_topics(tmp_path: Path) -> None:
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    raw_path = input_dir / "trends.csv"
    manifest_path = input_dir / "manifest.yaml"
    shutil.copyfile(FIXTURE_DIR / "trends.csv", raw_path)
    document = yaml.safe_load((FIXTURE_DIR / "manifest.yaml").read_text(encoding="utf-8"))
    document["series"].pop()
    manifest_path.write_text(yaml.safe_dump(document), encoding="utf-8")

    with pytest.raises(ValueError, match="exactly five Topics"):
        validate_files(raw_path, manifest_path)