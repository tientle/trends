# Approved Project Plan

**Goal And Scope**
Build a small Python pipeline that takes a fixed Google Trends CSV export, validates and cleans it, derives descriptive weekly features, and writes human-inspectable outputs. Use one export for all five Topics; do not build a dashboard, forecasting model, or automated scraper.

**Study And Acquisition**
Use Google Trends Explore’s manual CSV export with United States geography, Web Search, weekly aggregation, and a fixed three-year interval around 2023-10-01 to 2026-10-01. Before accepting data, verify that each candidate has a clear, correctly disambiguated **Topic** in Explore and record its exact displayed label and entity description. The selected candidates are:

- Brat, 2024 album
- Wicked, 2024 film
- KPop Demon Hunters, 2025 film
- Labubu, character/toy
- Love Island USA, recurring reality TV series

All five must be included together in one chart/export with identical settings. If one lacks a suitable Topic, ask the user to select a replacement phenomenon that does have one. Do not substitute a Search Term. If all five cannot be exported together, stop for a scope decision rather than combining separately normalized exports.

The official Trends API was announced as a limited alpha, so do not depend on access unless it is verified. BigQuery’s public datasets focus on curated Top and Rising queries, not these arbitrary candidates. `pytrends` is unofficial and archived; it is not the acquisition method for this MVP.

**Pipeline And Outputs**
Preserve the downloaded CSV unchanged under `data/raw/`, alongside a manifest recording its checksum, retrieval time, query URL, geography, dates, category, property, frequency, and the mapping from each stable series ID to its exact Topic label and export column.

The pipeline stages are: ingest raw input, parse the export, validate schema and manifest, convert to tidy long form, check data quality, calculate features, then write outputs and a validation report.

Write a cleaned time-series CSV under `data/processed/`, with one row per Topic/week and fields for request ID, series ID, Topic label and description, entity type, date, interest index, geography, frequency, and partial-week status. Write a one-row-per-Topic feature CSV and a JSON validation report.

Use CSV for inspectability; no database or Parquet is needed. Provide `validate` and `run` CLI commands. Package the CLI in a Docker image that runs against mounted input/output directories; no service or credentials are required. Suggested structure: `src/trends_pipeline/`, `data/raw/`, `data/processed/`, `reports/`, `tests/unit/`, `tests/integration/`, plus a root `Dockerfile`, `pyproject.toml`, and README. Keep runtime dependencies to pandas and PyYAML, with pytest for development.

**Validation And Features**
Fail on missing or ambiguous Topic mappings, invalid dates or scores, scores outside 0–100, conflicting duplicate Topic/date rows, missing required metadata, and unexpected cadence. Collapse identical duplicates only with a warning. Preserve zero as zero; keep blank values missing; do not impute or interpolate. Report gaps and partial edge weeks, and do not calculate a horizon that lacks complete observations.

For each Topic, calculate coverage dates, observation count, global maximum, earliest date at that maximum, tie count, and whole-window median. Calculate mean interest for the 4, 12, and 26 complete weekly observations _after_ the global peak, excluding the peak week. Return null and an incomplete flag if any required observation is unavailable. For all-zero series, flag no detectable indexed interest and leave peak date undefined.

Do not claim “time to peak,” pre-event baseline, attention half-life, or decay rate: there are no independent event dates, and a percentage-of-peak threshold does not define a defensible decay measure here. Love Island USA has recurring seasons, so its fixed post-peak windows are observations, not a single-cycle decay curve.

**Tests And Verification**
Unit tests should cover the real CSV format, metadata/header/footer parsing, manifest mappings, score/date validation, blank versus zero, duplicates, gaps, partial weeks, all-zero data, tied peaks, and complete/incomplete post-peak horizons. An integration test should run a synthetic export through the full pipeline and assert outputs and schemas. A Docker smoke test should run that fixture in the container; automated tests must not require live Google access.

For manual verification, compare the real export’s dates, Topic labels, row counts, and selected values or peaks against the Explore chart. Inspect zeros, blanks, gaps, partial weeks, generated CSVs, and the JSON report. Confirm the export and manifest describe the same single request.

**Limitations And Future Work**
Google Trends values are sampled, normalized relative search-interest indices, not search counts, audience size, or total public attention. Zero does not mean no searches; low-volume values can be noisy. Topic grouping is also a methodological limitation: Google’s Knowledge Graph grouping is not fully transparent and may include or omit variants. That limits the candidate pool and the claims; this five-case cohort is illustrative, not representative of internet culture.

Defer API automation, scraping, cross-request calibration, event-date annotation, resurgence/local-peak classification, uncertainty modeling, forecasting, ML, clustering, databases, visualization/scrollytelling, and cloud deployment. Document attribution to Google Trends and the fact that transformations are reproducible against preserved inputs, while a future Google export may differ.
