"""Live web search with source-linked, extractive answers.

Web results are deliberately represented with W-prefixed citations and never
fed into the uploaded-report RAG prompt.  Search-result extracts are shown as
unverified current sources, not as audited results or model forecasts.
"""
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import re
from typing import Any, Callable, Iterable
from urllib.parse import urlsplit, urlunsplit


class WebResearchError(RuntimeError):
    """Raised when the optional live-search provider cannot complete."""


@dataclass(frozen=True)
class WebSource:
    evidence_id: str
    title: str
    url: str
    summary: str
    domain: str
    published: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class WebResearchResult:
    query: str
    answer: str
    sources: tuple[WebSource, ...]
    searched_at: str

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["sources"] = [source.to_dict() for source in self.sources]
        return payload


SearchFunction = Callable[[str, int], Iterable[dict[str, Any]]]

REGULATORY_DOMAINS = {
    "bseindia.com",
    "nseindia.com",
    "sebi.gov.in",
    "sec.gov",
}
ESTABLISHED_NEWS_DOMAINS = {
    "reuters.com",
    "bloomberg.com",
    "business-standard.com",
    "economictimes.indiatimes.com",
    "livemint.com",
    "moneycontrol.com",
}
GENERIC_COMPANY_WORDS = {
    "and", "bank", "company", "corp", "corporation", "group", "holdings",
    "industries", "limited", "ltd", "motors", "plc", "the",
}
SPECULATIVE_LISTING_PATTERN = re.compile(
    r"\b(?:share price target|stock price target|buy or sell|technical analysis|"
    r"price prediction|share prediction)\b",
    re.IGNORECASE,
)


def _clean_text(value: Any, limit: int) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if len(text) <= limit:
        return text
    shortened = text[: limit + 1].rsplit(" ", 1)[0].rstrip(" ,;:")
    return (shortened or text[:limit]).rstrip() + "\u2026"


def _safe_url(value: Any) -> str | None:
    try:
        parts = urlsplit(str(value or "").strip())
    except ValueError:
        return None
    if parts.scheme.lower() not in {"http", "https"} or not parts.netloc:
        return None
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path, parts.query, ""))


def build_web_queries(company: str, question: str, current_year: int) -> tuple[str, ...]:
    """Build focused queries for the user's question and primary-source outlook."""
    company_name = _clean_text(company, 120) or "selected company"
    user_question = _clean_text(question, 300)
    return (
        f'"{company_name}" official investor relations {user_question} '
        f'investment plans outlook {current_year}',
    )


def _default_search(
    query: str,
    max_results: int,
    region: str,
    timeout: int,
    backend: str,
):
    try:
        from ddgs import DDGS
    except ImportError as error:
        raise WebResearchError("The DDGS live-search dependency is not installed.") from error
    try:
        return DDGS(timeout=timeout).text(
            query,
            region=region,
            safesearch="moderate",
            max_results=max_results,
            backend=backend,
        )
    except Exception as error:  # Provider/network exceptions vary by DDGS engine.
        raise WebResearchError("Live web search is temporarily unavailable.") from error


def _company_domain_terms(company: str) -> tuple[str, ...]:
    words = [
        word for word in re.findall(r"[a-z0-9]+", company.lower())
        if word not in GENERIC_COMPANY_WORDS and len(word) >= 3
    ]
    joined = "".join(words)
    return tuple(dict.fromkeys(([joined] if joined else []) + words))


def _source_score(source: WebSource, company: str) -> int:
    domain = source.domain.lower()
    searchable = f"{source.title} {source.url}".lower()
    score = 0
    if any(domain == trusted or domain.endswith('.' + trusted) for trusted in REGULATORY_DOMAINS):
        score += 10
    if any(domain == trusted or domain.endswith('.' + trusted) for trusted in ESTABLISHED_NEWS_DOMAINS):
        score += 5
    compact_domain = re.sub(r"[^a-z0-9]", "", domain.split('.', 1)[0])
    terms = _company_domain_terms(company)
    if terms and terms[0] and terms[0] in compact_domain:
        score += 9
    elif any(term in compact_domain for term in terms[1:]):
        score += 4
    if any(term in searchable for term in ('investor', 'annual-report', 'press-release', 'exchange filing')):
        score += 3
    if source.published:
        score += 1
    return score


def _normalise_sources(
    raw_results: Iterable[dict[str, Any]],
    company: str,
    max_results: int,
) -> tuple[WebSource, ...]:
    unique: list[tuple[int, WebSource]] = []
    seen_urls: set[str] = set()
    for position, item in enumerate(raw_results):
        url = _safe_url(item.get("href") or item.get("url"))
        if not url or url in seen_urls:
            continue
        title = _clean_text(item.get("title"), 180) or urlsplit(url).netloc
        summary = _clean_text(item.get("body") or item.get("snippet") or item.get("description"), 520)
        if not summary or SPECULATIVE_LISTING_PATTERN.search(title):
            continue
        seen_urls.add(url)
        unique.append((
            position,
            WebSource(
                evidence_id="",
                title=title,
                url=url,
                summary=summary,
                domain=urlsplit(url).netloc.removeprefix("www."),
                published=_clean_text(item.get("date") or item.get("published"), 60) or None,
            ),
        ))

    ranked = sorted(unique, key=lambda pair: (-_source_score(pair[1], company), pair[0]))
    return tuple(
        WebSource(
            evidence_id=f"W{position}",
            title=source.title,
            url=source.url,
            summary=source.summary,
            domain=source.domain,
            published=source.published,
        )
        for position, (_, source) in enumerate(ranked[:max_results], 1)
    )


def _extractive_answer(sources: tuple[WebSource, ...]) -> str:
    if not sources:
        return (
            "No relevant current web source was found. No future financial "
            "result has been estimated."
        )
    lines = [
        "Current web search returned these source extracts. They may describe "
        "plans, investments, targets, or outlook, but they are not audited "
        "future results and no missing figure has been estimated."
    ]
    lines.extend(f"{source.summary} [{source.evidence_id}]" for source in sources[:3])
    return "\n\n".join(lines)


def search_current_web(
    company: str,
    question: str,
    max_results: int = 5,
    region: str = "in-en",
    timeout: int = 10,
    backend: str = "auto",
    search_fn: SearchFunction | None = None,
    now: datetime | None = None,
) -> WebResearchResult:
    """Search current sources and return a separately citable result object."""
    if max_results < 1:
        raise ValueError("max_results must be at least 1")
    searched = now or datetime.now(timezone.utc)
    if searched.tzinfo is None:
        searched = searched.replace(tzinfo=timezone.utc)
    queries = build_web_queries(company, question, searched.year)

    raw_results: list[dict[str, Any]] = []
    per_query = max(max_results * 2, 10)
    for query in queries:
        try:
            found = (
                search_fn(query, per_query)
                if search_fn
                else _default_search(query, per_query, region, timeout, backend)
            )
            raw_results.extend(list(found or []))
        except WebResearchError:
            raise
        except Exception as error:
            raise WebResearchError("Live web search is temporarily unavailable.") from error

    sources = _normalise_sources(raw_results, company, max_results)
    return WebResearchResult(
        query=queries[0],
        answer=_extractive_answer(sources),
        sources=sources,
        searched_at=searched.astimezone(timezone.utc).isoformat(timespec="seconds"),
    )
