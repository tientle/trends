from datetime import date
from pathlib import Path

import pytest

from trends_pipeline.csv_export import ParsedExport, parse_export
from trends_pipeline.manifest import Manifest, SeriesMapping
from trends_pipeline.validation import validate_export


def _manifest(start: str = "2023-10-01", end: str = "2023-10-27") -> Manifest:
    return Manifest(
        request_id="request-001",
        retrieved_at="2026-10-01T12:00:00Z",
        query_url="https://trends.google.com/trends/explore",
        geography="US",
        start_date=date.fromisoformat(start),
        end_date=date.fromisoformat(end),
        category="All categories",
        property="Web Search",
        frequency="weekly",
        raw_file="trends.csv",
        sha256="a" * 64,
        series=(
            SeriesMapping("brat", "Brat (album)", "2024 album", "album", "Brat (album)"),
            SeriesMapping("wicked", "Wicked (film)", "2024 film", "film", "Wicked (film)"),
        ),
    )


def _parsed(rows: tuple[tuple[str, ...], ...]) -> ParsedExport:
    return ParsedExport(
        headers=("Week", "Brat (album)", "Wicked (film)"),
        rows=rows,
        metadata={"category": "All categories", "search type": "Web Search"},
    )


def test_parse_google_csv_metadata_header_and_footer(tmp_path: Path) -> None:
    path = tmp_path / "export.csv"
    path.write_text(
        "Category: All categories\n"
        "Time range: 2023-10-01 2023-10-27\n"
        "Interest over time\n"
        'Week,"Brat (album)","Wicked (film)"\n'
        "2023-10-01,0,12\n"
        "2023-10-08,,15\n"
        '"Note: Values are normalized",,\n'
        "bad footer text\n",
        encoding="utf-8",
    )

    parsed = parse_export(path)

    assert parsed.metadata["category"] == "All categories"
    assert parsed.metadata["time range"] == "2023-10-01 2023-10-27"
    assert parsed.headers == ("Week", "Brat (album)", "Wicked (film)")
    assert parsed.rows == (("2023-10-01", "0", "12"), ("2023-10-08", "", "15"))


def test_parse_and_validate_google_weekly_csv_with_time_header(tmp_path: Path) -> None:
    path = tmp_path / "time_header_export.csv"
    path.write_text(
        "Category: All categories\n"
        "Interest over time\n"
        'Time,"Brat (album)","Wicked (film)"\n'
        "2023-10-01,0,12\n"
        "2023-10-08,5,15\n",
        encoding="utf-8",
    )

    parsed = parse_export(path)
    tidy, warnings, quality = validate_export(parsed, _manifest())

    assert parsed.headers[0] == "Time"
    assert parsed.rows[0][0] == "2023-10-01"
    assert len(tidy) == 4
    assert tidy.iloc[0]["interest_index"] == 0
    assert warnings == []
    assert quality["weekly_rows"] == 2


def test_validation_preserves_zero_blank_and_marks_partial_edge() -> None:
    import pandas as pd

    tidy, warnings, quality = validate_export(
        _parsed((("2023-10-01", "0", "12"), ("2023-10-08", "", "15"))),
        _manifest(end="2023-10-10"),
    )

    assert tidy.iloc[0]["interest_index"] == 0
    assert pd.isna(tidy.iloc[1]["interest_index"])
    assert not tidy.iloc[0]["partial_week"]
    assert tidy.iloc[1]["partial_week"]
    assert not tidy.iloc[2]["partial_week"]
    assert tidy.iloc[3]["partial_week"]
    assert warnings == []
    assert quality["missing_values_by_series"] == {"brat": 1, "wicked": 0}


def test_validation_allows_weekly_buckets_overlapping_both_request_edges() -> None:
    tidy, _, quality = validate_export(
        _parsed((("2023-09-28", "1", "2"), ("2023-10-05", "3", "4"))),
        _manifest(start="2023-10-01", end="2023-10-10"),
    )

    assert quality["weekly_rows"] == 2
    assert tidy["partial_week"].all()


@pytest.mark.parametrize("observed_date", ["2023-09-21", "2023-10-12"])
def test_validation_rejects_weekly_buckets_outside_request_interval(
    observed_date: str,
) -> None:
    with pytest.raises(ValueError, match="outside the manifest request interval"):
        validate_export(
            _parsed(((observed_date, "1", "2"),)),
            _manifest(start="2023-10-01", end="2023-10-10"),
        )


@pytest.mark.parametrize(
    ("rows", "message"),
    [
        ((("bad-date", "1", "2"),), "Invalid ISO date"),
        ((("2023-10-01", "101", "2"),), "between 0 and 100"),
        ((("2023-10-01", "not-a-score", "2"),), "Invalid interest score"),
        (
            (("2023-10-01", "1", "2"), ("2023-10-01", "1", "3")),
            "Conflicting duplicate",
        ),
        (
            (("2023-10-01", "1", "2"), ("2023-10-09", "1", "2")),
            "inconsistent weekday alignment",
        ),
    ],
)
def test_validation_rejects_invalid_values_and_cadence(
    rows: tuple[tuple[str, ...], ...], message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        validate_export(_parsed(rows), _manifest())


def test_identical_duplicate_is_collapsed_with_warning() -> None:
    tidy, warnings, quality = validate_export(
        _parsed((("2023-10-01", "1", "2"), ("2023-10-01", "1", "2"))),
        _manifest(),
    )

    assert len(tidy) == 2
    assert warnings == ["Collapsed 1 identical duplicate weekly row(s)"]
    assert quality["identical_duplicates_collapsed"] == 1


def test_time_range_metadata_must_match_manifest() -> None:
    parsed = ParsedExport(
        headers=("Week", "Brat (album)", "Wicked (film)"),
        rows=(("2023-10-01", "1", "2"),),
        metadata={"time range": "Oct 1, 2023 - Oct 1, 2026"},
    )

    with pytest.raises(ValueError, match="manifest specifies 2023-10-01 through 2023-10-27"):
        validate_export(parsed, _manifest())


def test_gaps_are_reported_not_imputed() -> None:
    tidy, warnings, quality = validate_export(
        _parsed((("2023-10-01", "1", "2"), ("2023-10-15", "3", "4"))),
        _manifest(),
    )

    assert len(tidy) == 4
    assert warnings == ["Found 1 missing weekly observation(s)"]
    assert quality["gap_weeks"] == 1