"""Create evidence-grounded financial visualizations for the RAG assistant."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any, Iterable

import plotly.graph_objects as go


AMOUNT = (
    r"(?P<currency>₹|INR|Rs\.?|USD|US\$|\$)?\s*"
    r"(?P<value>-?\d[\d,]*(?:\.\d+)?)\s*"
    r"(?P<unit>crores?|lakhs?|millions?|billions?|thousands?|%)?"
)
YEAR = r"(?:FY\s*)?\d{4}(?:\s*[-–/]\s*\d{2,4})?"

YEAR_FIRST_PATTERN = re.compile(
    rf"(?P<label>{YEAR})\s*(?:[:=\-–]|was|stood\s+at|reported)?\s*{AMOUNT}",
    re.IGNORECASE,
)
VALUE_FIRST_PATTERN = re.compile(
    rf"{AMOUNT}\s*(?:in|for|during)\s+(?P<label>{YEAR})",
    re.IGNORECASE,
)
CATEGORY_PATTERN = re.compile(
    rf"(?P<label>[A-Za-z][A-Za-z0-9 &/().\-]{{1,60}}?)\s*"
    rf"(?:was|were|is|at|of|stood\s+at|reported|:|=)\s*{AMOUNT}",
    re.IGNORECASE,
)

UNIT_FACTORS = {
    "thousand": 1_000,
    "thousands": 1_000,
    "lakh": 100_000,
    "lakhs": 100_000,
    "million": 1_000_000,
    "millions": 1_000_000,
    "crore": 10_000_000,
    "crores": 10_000_000,
    "billion": 1_000_000_000,
    "billions": 1_000_000_000,
    "%": 1,
}


@dataclass(frozen=True)
class FinancialDataPoint:
    label: str
    value: float
    display_value: str
    unit: str
    currency: str
    page_number: str
    source_file: str

    @property
    def citation(self) -> str:
        return f"[Page {self.page_number}]"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class VisualizationSpec:
    title: str
    chart_type: str
    x_label: str
    y_label: str
    points: tuple[FinancialDataPoint, ...]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["points"] = [point.to_dict() for point in self.points]
        return payload


def _clean_label(label: str) -> str:
    label = re.sub(r"\s+", " ", label).strip(" .,:;–-")
    return label[:80]


def _normalise_currency(currency: str | None) -> str:
    if not currency:
        return ""
    if currency.upper().replace(".", "") in {"RS", "INR"} or currency == "₹":
        return "INR"
    if currency.upper() in {"USD", "US$", "$"}:
        return "USD"
    return currency.upper()


def _point_from_match(
    match: re.Match[str],
    page_number: Any,
    source_file: str,
) -> FinancialDataPoint | None:
    label = _clean_label(match.group("label"))
    raw_value = match.group("value").replace(",", "")
    unit = (match.group("unit") or "").lower()
    currency = _normalise_currency(match.group("currency"))

    if not label or not raw_value:
        return None

    value = float(raw_value)
    display_parts = [part for part in (currency, match.group("value"), unit) if part]
    return FinancialDataPoint(
        label=label,
        value=value,
        display_value=" ".join(display_parts),
        unit=unit,
        currency=currency,
        page_number=str(page_number),
        source_file=source_file,
    )


def extract_financial_data(
    evidence: Iterable[dict[str, Any]],
) -> list[FinancialDataPoint]:
    """Extract explicitly labelled amounts while preserving source metadata."""
    points: list[FinancialDataPoint] = []
    seen: set[tuple[str, float, str, str, str]] = set()

    for result in evidence:
        text = str(result.get("paragraph_text") or result.get("text") or "")
        page = result.get("page_number", "unknown")
        source = str(result.get("source_file") or "unknown.pdf")

        for pattern in (YEAR_FIRST_PATTERN, VALUE_FIRST_PATTERN, CATEGORY_PATTERN):
            for match in pattern.finditer(text):
                point = _point_from_match(match, page, source)
                if point is None:
                    continue

                key = (
                    point.label.casefold(),
                    point.value,
                    point.unit,
                    point.currency,
                    point.page_number,
                )
                if key not in seen:
                    seen.add(key)
                    points.append(point)

    return points


def _is_year_label(label: str) -> bool:
    return re.fullmatch(YEAR, label.strip(), re.IGNORECASE) is not None


def _compatible_group(
    points: list[FinancialDataPoint],
) -> list[FinancialDataPoint]:
    """Select the largest group sharing currency and unit."""
    groups: dict[tuple[str, str], list[FinancialDataPoint]] = {}
    for point in points:
        groups.setdefault((point.currency, point.unit), []).append(point)
    return max(groups.values(), key=len, default=[])


def build_visualization_spec(
    question: str,
    evidence: Iterable[dict[str, Any]],
) -> VisualizationSpec | None:
    """Return a safe chart specification, or None when evidence is insufficient."""
    points = _compatible_group(extract_financial_data(evidence))
    if len(points) < 2:
        return None

    year_series = all(_is_year_label(point.label) for point in points)
    chart_type = "line" if year_series else "bar"
    unit = points[0].unit
    currency = points[0].currency
    y_parts = [part for part in (currency, unit) if part]
    y_label = "Value" + (f" ({' '.join(y_parts)})" if y_parts else "")

    clean_question = question.strip().rstrip("?")
    title = clean_question[:100] if clean_question else "Financial comparison"
    return VisualizationSpec(
        title=title,
        chart_type=chart_type,
        x_label="Financial year" if year_series else "Category",
        y_label=y_label,
        points=tuple(points),
    )


def create_plotly_figure(spec: VisualizationSpec) -> go.Figure:
    """Build an interactive Plotly figure from a validated specification."""
    labels = [point.label for point in spec.points]
    values = [point.value for point in spec.points]
    custom_data = [
        [point.display_value, point.citation, point.source_file]
        for point in spec.points
    ]
    hover_template = (
        "<b>%{x}</b><br>%{customdata[0]}<br>"
        "%{customdata[1]}<br>%{customdata[2]}<extra></extra>"
    )

    if spec.chart_type == "line":
        trace = go.Scatter(
            x=labels,
            y=values,
            mode="lines+markers+text",
            text=[point.display_value for point in spec.points],
            textposition="top center",
            customdata=custom_data,
            hovertemplate=hover_template,
        )
    else:
        trace = go.Bar(
            x=labels,
            y=values,
            text=[point.display_value for point in spec.points],
            textposition="outside",
            customdata=custom_data,
            hovertemplate=hover_template,
        )

    figure = go.Figure(trace)
    figure.update_layout(
        title=spec.title,
        xaxis_title=spec.x_label,
        yaxis_title=spec.y_label,
        hovermode="x unified" if spec.chart_type == "line" else "closest",
        margin={"l": 40, "r": 30, "t": 70, "b": 50},
    )
    return figure


def visualization_rows(spec: VisualizationSpec) -> list[dict[str, Any]]:
    """Return the exact chart values for a Streamlit evidence table."""
    return [
        {
            "Label": point.label,
            "Value": point.value,
            "Displayed value": point.display_value,
            "Page": point.page_number,
            "Source": point.source_file,
        }
        for point in spec.points
    ]
