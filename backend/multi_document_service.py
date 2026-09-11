"""Helpers for deterministic, source-balanced multi-report retrieval."""
from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Any

from backend.retrieval_service import deduplicate


def _number(value: Any, fallback: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback


def _quality_key(result: dict[str, Any]) -> tuple[float, float, float, str, int]:
    """Return a stable cross-report ordering for already fused candidates."""
    page = result.get("page_number")
    try:
        page_number = int(page)
    except (TypeError, ValueError):
        page_number = 0
    return (
        _number(result.get("retrieval_score")),
        _number(result.get("similarity_score"), -1.0),
        _number(result.get("keyword_score")),
        str(result.get("document_id") or result.get("source_file") or ""),
        -page_number,
    )


def merge_report_results(
    report_results: Iterable[Sequence[dict[str, Any]]],
    top_k: int,
) -> list[dict[str, Any]]:
    """Merge per-report rankings while retaining cross-report evidence.

    The first relevant result from each selected report is considered before
    remaining candidates. This makes comparison questions much less likely to
    lose an entire company or financial year merely because another report has
    several near-identical top scores. Remaining slots use the fused retrieval,
    dense-similarity and keyword scores in that order.
    """
    if top_k <= 0:
        raise ValueError("top_k must be positive.")

    groups = [deduplicate(list(results)) for results in report_results]
    groups = [group for group in groups if group]
    if not groups:
        return []

    seeds = [group[0] for group in groups]
    if len(seeds) >= top_k:
        return deduplicate(sorted(seeds, key=_quality_key, reverse=True))[:top_k]

    merged = deduplicate(seeds)
    remaining = [result for group in groups for result in group[1:]]
    for result in sorted(remaining, key=_quality_key, reverse=True):
        candidate = deduplicate([*merged, result])
        if len(candidate) == len(merged):
            continue
        merged = candidate
        if len(merged) >= top_k:
            break
    return merged[:top_k]


def selected_report_scope(
    metadata_items: Iterable[dict[str, Any]],
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Return stable unique company and financial-year labels."""
    companies: list[str] = []
    years: list[str] = []
    for metadata in metadata_items:
        company = str(metadata.get("company") or "").strip()
        year = str(metadata.get("financial_year") or "").strip()
        if company and company not in companies:
            companies.append(company)
        if year and year not in years:
            years.append(year)
    return tuple(companies), tuple(years)
