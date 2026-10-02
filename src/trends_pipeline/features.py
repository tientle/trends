"""Calculate the approved descriptive weekly features for each Topic."""

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd


HORIZONS = (4, 12, 26)


def calculate_features(tidy: pd.DataFrame) -> pd.DataFrame:
    """Return one feature row per series without imputing missing observations."""
    output: list[dict[str, object]] = []
    for series_id, group in tidy.groupby("series_id", sort=False):
        ordered = group.sort_values("date").reset_index(drop=True)
        observed = ordered.dropna(subset=["interest_index"])
        values = observed["interest_index"].astype(float)
        maximum = float(values.max()) if not values.empty else None
        detectable = maximum is not None and maximum > 0
        peak_date: date | None = None
        peak_tie_count: int | None = None
        if detectable:
            peak_rows = observed.loc[observed["interest_index"] == maximum]
            peak_date = date.fromisoformat(str(peak_rows.iloc[0]["date"]))
            peak_tie_count = len(peak_rows)

        first = ordered.iloc[0]
        feature: dict[str, object] = {
            "request_id": first["request_id"],
            "series_id": series_id,
            "topic_label": first["topic_label"],
            "topic_description": first["topic_description"],
            "entity_type": first["entity_type"],
            "coverage_start": ordered["date"].min(),
            "coverage_end": ordered["date"].max(),
            "observation_count": len(observed),
            "global_max": maximum,
            "peak_date": peak_date.isoformat() if peak_date is not None else None,
            "peak_tie_count": peak_tie_count,
            "whole_window_median": float(values.median()) if not values.empty else None,
            "has_detectable_interest": bool(detectable),
        }

        for horizon in HORIZONS:
            horizon_values: list[float] = []
            complete = peak_date is not None
            if peak_date is not None:
                date_to_row = {
                    date.fromisoformat(str(row.date)): row
                    for row in ordered.itertuples(index=False)
                }
                for offset in range(1, horizon + 1):
                    expected_date = peak_date + timedelta(days=7 * offset)
                    row = date_to_row.get(expected_date)
                    if row is None or row.partial_week or pd.isna(row.interest_index):
                        complete = False
                        break
                    horizon_values.append(float(row.interest_index))
            feature[f"post_peak_mean_{horizon}"] = (
                sum(horizon_values) / horizon if complete else None
            )
            feature[f"post_peak_{horizon}_complete"] = bool(complete)
        output.append(feature)
    return pd.DataFrame.from_records(output)