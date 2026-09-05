"""Plan source-isolated report and web research for one question.

The report path remains authoritative for uploaded-document claims.  The web
path is enabled only by an explicit mode or a current/future-looking question;
it never changes which evidence is supplied to the report answer generator.
"""
from dataclasses import asdict, dataclass
import re


WEB_AUTO = "Automatic for current/future questions"
WEB_ALWAYS = "Always include"
WEB_OFF = "Off"
WEB_MODES = (WEB_AUTO, WEB_ALWAYS, WEB_OFF)

CURRENT_OR_FUTURE_PATTERN = re.compile(
    r"\b(?:current|currently|latest|recent|today|future|plan(?:s|ned)?|"
    r"outlook|roadmap|strategy|strategic|guidance|forecast|predict(?:ion|ed)?|"
    r"expected|upcoming|investment(?:s)?|investing|capex|expansion|target(?:s|ed)?)\b",
    re.IGNORECASE,
)
YEAR_RANGE_PATTERN = re.compile(
    r"(?<!\d)((?:19|20|21)\d{2})\s*[-/\u2013\u2014]\s*(\d{2,4})(?!\d)"
)
FOUR_DIGIT_YEAR_PATTERN = re.compile(r"(?<!\d)((?:19|20|21)\d{2})(?!\d)")


@dataclass(frozen=True)
class ResearchPlan:
    """The independently executable source plan for a question."""

    include_web: bool
    web_reason: str
    requested_years: tuple[int, ...]
    report_end_year: int | None
    document_out_of_period: bool

    def to_dict(self):
        return asdict(self)


def _expanded_end_year(start: int, raw_end: str) -> int:
    if len(raw_end) == 4:
        return int(raw_end)
    end = (start // 100) * 100 + int(raw_end)
    return end + 100 if end < start else end


def extract_years(text: str) -> tuple[int, ...]:
    """Return explicit calendar/FY years, expanding ranges such as 2028-29."""
    value = str(text or "")
    years: set[int] = set()
    for match in YEAR_RANGE_PATTERN.finditer(value):
        start = int(match.group(1))
        years.update((start, _expanded_end_year(start, match.group(2))))
    years.update(int(year) for year in FOUR_DIGIT_YEAR_PATTERN.findall(value))
    return tuple(sorted(years))


def report_year_bounds(financial_year: str | None) -> tuple[int | None, int | None]:
    years = extract_years(financial_year or "")
    if not years:
        return None, None
    return min(years), max(years)


def plan_research(
    question: str,
    financial_year: str | None,
    web_mode: str = WEB_AUTO,
) -> ResearchPlan:
    """Route a question without blending report evidence and web sources."""
    if web_mode not in WEB_MODES:
        raise ValueError(f"Unknown web research mode: {web_mode}")

    requested_years = extract_years(question)
    _, report_end_year = report_year_bounds(financial_year)
    out_of_period = bool(
        requested_years
        and report_end_year is not None
        and max(requested_years) > report_end_year
    )
    current_or_future = bool(CURRENT_OR_FUTURE_PATTERN.search(question or ""))

    if web_mode == WEB_ALWAYS:
        include_web = True
        reason = "Web research was requested for every question."
    elif web_mode == WEB_OFF:
        include_web = False
        reason = "Web research is switched off."
    elif out_of_period:
        include_web = True
        reason = "The question asks about a period later than the selected report."
    elif current_or_future:
        include_web = True
        reason = "The question asks for current information, plans, or outlook."
    else:
        include_web = False
        reason = "The question can be answered from the selected report alone."

    return ResearchPlan(
        include_web=include_web,
        web_reason=reason,
        requested_years=requested_years,
        report_end_year=report_end_year,
        document_out_of_period=out_of_period,
    )


def document_scope_answer(
    plan: ResearchPlan,
    financial_year: str | None,
    insufficient_message: str,
) -> str | None:
    """Return a deterministic refusal when a report cannot cover a later year."""
    if not plan.document_out_of_period:
        return None
    requested = ", ".join(str(year) for year in plan.requested_years)
    coverage = financial_year or "the stated reporting period"
    return (
        f"{insufficient_message}\n\n"
        f"The question requests {requested}, which is later than the selected "
        f"report coverage ({coverage}). No future result or forecast has been "
        "inferred from the uploaded document."
    )
