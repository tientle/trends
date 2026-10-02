"""Validate a parsed export and convert it to one row per Topic and week."""

from __future__ import annotations

import math
from datetime import date, datetime, timedelta
import re

import pandas as pd

from trends_pipeline.csv_export import ParsedExport
from trends_pipeline.manifest import Manifest


TIDY_COLUMNS = [
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


def _score(value: str, context: str) -> float | None:
    if not value.strip():
        return None
    try:
        score = float(value)
    except ValueError as error:
        raise ValueError(f"Invalid interest score {value!r} at {context}") from error
    if not math.isfinite(score) or not 0 <= score <= 100:
        raise ValueError(f"Interest score must be between 0 and 100 at {context}: {value!r}")
    return score


def _check_metadata(metadata: dict[str, str], manifest: Manifest) -> None:
    expected = {
        "category": manifest.category,
        "search type": manifest.property,
        "property": manifest.property,
        "geography": manifest.geography,
        "location": manifest.geography,
    }
    for key, value in metadata.items():
        if key in expected and value and value.casefold() != expected[key].casefold():
            raise ValueError(
                f"Export metadata {key!r} is {value!r}, but manifest specifies {expected[key]!r}"
            )
    time_range = metadata.get("time range")
    if time_range:
        date_tokens = re.findall(r"\d{4}-\d{2}-\d{2}|[A-Za-z]+ \d{1,2}, \d{4}", time_range)
        if len(date_tokens) != 2:
            raise ValueError(f"Cannot verify export Time range metadata: {time_range!r}")
        parsed_dates: list[date] = []
        for token in date_tokens:
            try:
                parsed_dates.append(date.fromisoformat(token))
            except ValueError:
                parsed_date = None
                for date_format in ("%b %d, %Y", "%B %d, %Y"):
                    try:
                        parsed_dates.append(datetime.strptime(token, date_format).date())
                        break
                    except ValueError:
                        continue
                else:
                    raise ValueError(f"Cannot verify export Time range metadata: {time_range!r}")
        if parsed_dates != [manifest.start_date, manifest.end_date]:
            raise ValueError(
                f"Export Time range is {time_range!r}, but manifest specifies "
                f"{manifest.start_date.isoformat()} through {manifest.end_date.isoformat()}"
            )


def validate_export(
    parsed: ParsedExport, manifest: Manifest
) -> tuple[pd.DataFrame, list[str], dict[str, object]]:
    """Validate the export and return tidy data, warnings, and quality details."""
    _check_metadata(parsed.metadata, manifest)
    headers = list(parsed.headers)
    if not headers or headers[0].casefold() not in {"week", "date", "time"}:
        raise ValueError("The first export column must be Week, Date, or Time")
    expected_columns = [item.export_column for item in manifest.series]
    missing = [column for column in expected_columns if column not in headers]
    if missing:
        raise ValueError(f"Manifest export columns are missing from CSV: {missing}")
    unexpected = [column for column in headers[1:] if column not in expected_columns]
    if unexpected:
        raise ValueError(f"CSV has unmapped Topic columns: {unexpected}")
    if len(headers) != len(expected_columns) + 1:
        raise ValueError("CSV column count does not match the manifest series mapping")

    raw_rows: list[tuple[date, tuple[float | None, ...]]] = []
    for row_number, row in enumerate(parsed.rows, start=1):
        date_text = row[0]
        try:
            observed_date = date.fromisoformat(date_text)
        except ValueError as error:
            raise ValueError(f"Invalid ISO date {date_text!r} on data row {row_number}") from error
        week_end = observed_date + timedelta(days=6)
        if observed_date > manifest.end_date or week_end < manifest.start_date:
            raise ValueError(
                f"Weekly observation {observed_date.isoformat()} is outside the manifest request interval "
                f"{manifest.start_date.isoformat()} through {manifest.end_date.isoformat()}"
            )
        scores = tuple(
            _score(row[headers.index(column)], f"row {row_number}, column {column!r}")
            for column in expected_columns
        )
        raw_rows.append((observed_date, scores))

    by_date: dict[date, tuple[float | None, ...]] = {}
    warnings: list[str] = []
    duplicate_count = 0
    for observed_date, scores in raw_rows:
        if observed_date in by_date:
            if by_date[observed_date] != scores:
                raise ValueError(f"Conflicting duplicate Topic/date values for {observed_date}")
            duplicate_count += 1
            continue
        by_date[observed_date] = scores
    if duplicate_count:
        warnings.append(f"Collapsed {duplicate_count} identical duplicate weekly row(s)")

    dates = sorted(by_date)
    if any(right.weekday() != dates[0].weekday() for right in dates):
        raise ValueError("Weekly observations have inconsistent weekday alignment")
    intervals = [(right - left).days for left, right in zip(dates, dates[1:])]
    if any(interval % 7 for interval in intervals):
        raise ValueError("Unexpected cadence: weekly observation dates are not 7-day aligned")
    gap_weeks = sum(max(interval // 7 - 1, 0) for interval in intervals)
    if gap_weeks:
        warnings.append(f"Found {gap_weeks} missing weekly observation(s)")

    tidy_records: list[dict[str, object]] = []
    missing_by_series: dict[str, int] = {}
    for series_index, series in enumerate(manifest.series):
        missing_by_series[series.series_id] = 0
        for observed_date in dates:
            score = by_date[observed_date][series_index]
            if score is None:
                missing_by_series[series.series_id] += 1
            partial_week = (
                observed_date < manifest.start_date
                or observed_date + timedelta(days=6) > manifest.end_date
            )
            tidy_records.append(
                {
                    "request_id": manifest.request_id,
                    "series_id": series.series_id,
                    "topic_label": series.topic_label,
                    "topic_description": series.topic_description,
                    "entity_type": series.entity_type,
                    "date": observed_date.isoformat(),
                    "interest_index": score,
                    "geography": manifest.geography,
                    "frequency": manifest.frequency,
                    "partial_week": partial_week,
                }
            )
    tidy = pd.DataFrame.from_records(tidy_records, columns=TIDY_COLUMNS)
    quality: dict[str, object] = {
        "date_start": dates[0].isoformat(),
        "date_end": dates[-1].isoformat(),
        "weekly_rows": len(dates),
        "gap_weeks": gap_weeks,
        "partial_week_count": sum(
            record["partial_week"] for record in tidy_records
        ) // len(manifest.series),
        "missing_values_by_series": missing_by_series,
        "identical_duplicates_collapsed": duplicate_count,
    }
    return tidy, warnings, quality