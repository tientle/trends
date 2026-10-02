from datetime import date, timedelta

import pandas as pd

from trends_pipeline.features import calculate_features
from trends_pipeline.validation import TIDY_COLUMNS


def _tidy(scores: list[float | None], partial_indices: set[int] | None = None) -> pd.DataFrame:
    partial_indices = partial_indices or set()
    records = []
    start = date(2023, 10, 1)
    for index, score in enumerate(scores):
        records.append(
            {
                "request_id": "request-001",
                "series_id": "brat",
                "topic_label": "Brat (album)",
                "topic_description": "2024 album",
                "entity_type": "album",
                "date": (start + timedelta(days=7 * index)).isoformat(),
                "interest_index": score,
                "geography": "US",
                "frequency": "weekly",
                "partial_week": index in partial_indices,
            }
        )
    return pd.DataFrame.from_records(records, columns=TIDY_COLUMNS)


def test_features_calculate_tied_peak_and_complete_horizons() -> None:
    features = calculate_features(_tidy([100, *range(1, 27)]))
    feature = features.iloc[0]

    assert feature["global_max"] == 100
    assert feature["peak_date"] == "2023-10-01"
    assert feature["peak_tie_count"] == 1
    assert feature["observation_count"] == 27
    assert feature["whole_window_median"] == 14
    assert feature["post_peak_mean_4"] == 2.5
    assert feature["post_peak_mean_12"] == 6.5
    assert feature["post_peak_mean_26"] == 13.5
    assert bool(feature["post_peak_26_complete"])


def test_features_report_tied_peaks_and_incomplete_missing_week() -> None:
    scores = [10, 100, 4, 100, *range(1, 27)]
    scores[4] = None
    feature = calculate_features(_tidy(scores)).iloc[0]

    assert feature["peak_date"] == "2023-10-08"
    assert feature["peak_tie_count"] == 2
    assert pd.isna(feature["post_peak_mean_4"])
    assert not bool(feature["post_peak_4_complete"])
    assert not bool(feature["post_peak_12_complete"])


def test_all_zero_series_has_no_defined_peak() -> None:
    feature = calculate_features(_tidy([0] * 30)).iloc[0]

    assert feature["global_max"] == 0
    assert not bool(feature["has_detectable_interest"])
    assert pd.isna(feature["peak_date"])
    assert pd.isna(feature["peak_tie_count"])
    assert pd.isna(feature["post_peak_mean_4"])
    assert not bool(feature["post_peak_4_complete"])


def test_partial_week_cannot_complete_post_peak_horizon() -> None:
    feature = calculate_features(_tidy([100, *range(1, 27)], {4})).iloc[0]

    assert pd.isna(feature["post_peak_mean_4"])
    assert not bool(feature["post_peak_4_complete"])