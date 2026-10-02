"""Read the table and metadata preamble from a Google Trends CSV export."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ParsedExport:
    headers: tuple[str, ...]
    rows: tuple[tuple[str, ...], ...]
    metadata: dict[str, str]


def parse_export(path: Path) -> ParsedExport:
    """Parse a Google Trends export without changing the source file."""
    try:
        text = path.read_text(encoding="utf-8-sig")
    except OSError as error:
        raise ValueError(f"Cannot read Trends export {path}: {error}") from error

    records = list(csv.reader(text.splitlines()))
    header_index = next(
        (
            index
            for index, row in enumerate(records)
            if row and row[0].strip().casefold() in {"week", "date", "time"}
        ),
        None,
    )
    if header_index is None:
        raise ValueError("Could not find a 'Week', 'Date', or 'Time' header in the Google Trends export")

    metadata: dict[str, str] = {}
    for row in records[:header_index]:
        if not row:
            continue
        first_cell = row[0].strip()
        if ":" in first_cell:
            key, value = first_cell.split(":", 1)
            metadata[key.strip().casefold()] = value.strip()

    headers = tuple(cell.strip() for cell in records[header_index])
    if len(headers) < 2 or any(not header for header in headers):
        raise ValueError("Export header must include a date and named series columns")
    if len(headers) != len(set(headers)):
        raise ValueError("Export contains duplicate column headers")
    if headers[0].casefold() not in {"week", "date", "time"}:
        raise ValueError("The first export column must be Week, Date, or Time")

    rows: list[tuple[str, ...]] = []
    for row in records[header_index + 1 :]:
        if not row or not any(cell.strip() for cell in row):
            continue
        first_cell = row[0].strip()
        if first_cell.casefold().startswith("note:"):
            break
        if len(row) > len(headers) and any(cell.strip() for cell in row[len(headers) :]):
            raise ValueError(f"Export row has more fields than its header: {row!r}")
        padded = row[: len(headers)] + [""] * max(0, len(headers) - len(row))
        rows.append(tuple(cell.strip() for cell in padded))

    if not rows:
        raise ValueError("Google Trends export contains no weekly observations")
    return ParsedExport(headers=headers, rows=tuple(rows), metadata=metadata)