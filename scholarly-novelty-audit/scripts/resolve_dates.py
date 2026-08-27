"""Resolve earliest verified public dates and enforce strict cutoffs."""

from __future__ import annotations

from copy import deepcopy
from calendar import monthrange
from datetime import date, datetime
from typing import Any, Iterable


SOURCE_PRIORITY = {
    "arxiv_v1": 0,
    "preprint_v1": 0,
    "openreview_first_public": 1,
    "accepted_manuscript": 2,
    "publisher_online": 2,
    "crossref_published_online": 3,
    "crossref_issued": 3,
    "proceedings": 4,
    "publication": 5,
    "year_only": 99,
}


def parse_date(value: Any) -> tuple[date | None, str]:
    if value in (None, ""):
        return None, "missing"
    if isinstance(value, datetime):
        return value.date(), "day"
    if isinstance(value, date):
        return value, "day"
    text = str(value).strip()
    if len(text) == 4 and text.isdigit():
        return None, "year"
    for fmt, precision in (("%Y-%m-%d", "day"), ("%Y-%m", "month")):
        try:
            parsed = datetime.strptime(text, fmt).date()
            return (parsed if precision == "day" else None), precision
        except ValueError:
            pass
    return None, "invalid"


def resolve_earliest_public_date(paper: dict[str, Any]) -> dict[str, Any]:
    candidates: list[dict[str, Any]] = []
    partial: list[dict[str, Any]] = []
    for entry in paper.get("dates") or []:
        if isinstance(entry, str):
            entry = {"value": entry, "source": "publication"}
        value, precision = parse_date(entry.get("value"))
        candidate = {
            "value": entry.get("value"),
            "source": entry.get("source", "publication"),
            "url": entry.get("url"),
            "precision": precision,
            "verified": bool(entry.get("verified", True)),
        }
        if value and candidate["verified"]:
            candidate["parsed"] = value.isoformat()
            candidates.append(candidate)
        elif precision in {"year", "month"} and candidate["verified"]:
            text = str(candidate["value"])
            if precision == "year":
                candidate.update({"lower_bound": f"{text}-01-01", "upper_bound": f"{text}-12-31"})
            else:
                year, month = (int(value) for value in text.split("-"))
                candidate.update({"lower_bound": f"{year:04d}-{month:02d}-01", "upper_bound": f"{year:04d}-{month:02d}-{monthrange(year, month)[1]:02d}"})
            partial.append(candidate)
    if not candidates and paper.get("year"):
        text = str(paper["year"])
        partial.append({"value": text, "source": "year_only", "precision": "year", "verified": True, "lower_bound": f"{text}-01-01", "upper_bound": f"{text}-12-31"})
    if candidates:
        candidates.sort(key=lambda item: (item["parsed"], SOURCE_PRIORITY.get(item["source"], 50)))
        earliest = candidates[0]
        possibly_earlier = [item for item in partial if item["lower_bound"] <= earliest["parsed"]]
        if possibly_earlier:
            possibly_earlier.sort(key=lambda item: (item["lower_bound"], SOURCE_PRIORITY.get(item["source"], 50)))
            return {
                "earliest_public_date": None,
                "date_status": "DATE_UNCERTAIN",
                "date_provenance": possibly_earlier[0],
                "observed_dates": candidates + partial,
            }
        return {
            "earliest_public_date": earliest["parsed"],
            "date_status": "RESOLVED",
            "date_provenance": earliest,
            "observed_dates": candidates + partial,
        }
    return {
        "earliest_public_date": None,
        "date_status": "DATE_UNCERTAIN",
        "date_provenance": partial[0] if partial else None,
        "observed_dates": partial,
    }


def apply_cutoff(paper: dict[str, Any], cutoff: str, strict: bool = True) -> dict[str, Any]:
    result = deepcopy(paper)
    resolved = resolve_earliest_public_date(result)
    result.update(resolved)
    cutoff_date, precision = parse_date(cutoff)
    if not cutoff_date or precision != "day":
        raise ValueError("cutoff must be a complete YYYY-MM-DD date")
    if result["date_status"] == "DATE_UNCERTAIN":
        result["cutoff_status"] = "DATE_UNCERTAIN" if strict else "ELIGIBILITY_UNCERTAIN"
    elif date.fromisoformat(result["earliest_public_date"]) <= cutoff_date:
        result["cutoff_status"] = "ELIGIBLE"
    else:
        result["cutoff_status"] = "POST_CUTOFF"
    result["cutoff"] = cutoff_date.isoformat()
    return result


def apply_cutoff_many(records: Iterable[dict[str, Any]], cutoff: str, strict: bool = True) -> list[dict[str, Any]]:
    return [apply_cutoff(record, cutoff, strict=strict) for record in records]
