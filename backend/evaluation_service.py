import re
import time
from dataclasses import asdict, dataclass
from statistics import mean
from typing import Any, Callable


PAGE_CITATION_PATTERN = re.compile(r"\[Page\s+([^\]]+)\]", re.IGNORECASE)


def _normalise_page(page: Any) -> str:
    return str(page).strip().lower()


@dataclass(frozen=True)
class EvaluationResult:
    question: str
    precision_at_k: float
    recall_at_k: float
    reciprocal_rank: float
    citation_validity: float | None
    latency_ms: float
    retrieved_pages: list[str]
    expected_pages: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def retrieval_metrics(
    retrieved_pages: list[Any],
    expected_pages: list[Any],
) -> tuple[float, float, float]:
    """Return precision@k, recall@k and reciprocal rank for page retrieval."""
    retrieved = [_normalise_page(page) for page in retrieved_pages]
    expected = {_normalise_page(page) for page in expected_pages}

    if not retrieved or not expected:
        return 0.0, 0.0, 0.0

    relevant_count = sum(page in expected for page in retrieved)
    precision = relevant_count / len(retrieved)
    recall = len(set(retrieved) & expected) / len(expected)

    reciprocal_rank = 0.0
    for rank, page in enumerate(retrieved, start=1):
        if page in expected:
            reciprocal_rank = 1 / rank
            break

    return precision, recall, reciprocal_rank


def extract_page_citations(answer: str) -> list[str]:
    """Extract page identifiers from citations such as ``[Page 42]``."""
    return [match.strip() for match in PAGE_CITATION_PATTERN.findall(answer)]


def citation_validity(answer: str, evidence_pages: list[Any]) -> float | None:
    """Measure the share of answer citations supported by retrieved evidence."""
    citations = extract_page_citations(answer)
    if not citations:
        return None

    evidence = {_normalise_page(page) for page in evidence_pages}
    valid_count = sum(_normalise_page(page) in evidence for page in citations)
    return valid_count / len(citations)


def evaluate_question(
    question: str,
    expected_pages: list[Any],
    retrieve: Callable[[str], list[dict[str, Any]]],
    generate: Callable[[str, list[dict[str, Any]]], str] | None = None,
) -> EvaluationResult:
    """Evaluate one benchmark question using injected retrieval/generation calls."""
    started_at = time.perf_counter()
    results = retrieve(question)
    answer = generate(question, results) if generate else ""
    latency_ms = (time.perf_counter() - started_at) * 1000

    retrieved_pages = [str(item.get("page_number", "unknown")) for item in results]
    expected_page_labels = [str(page) for page in expected_pages]
    precision, recall, reciprocal_rank = retrieval_metrics(
        retrieved_pages,
        expected_page_labels,
    )

    return EvaluationResult(
        question=question,
        precision_at_k=precision,
        recall_at_k=recall,
        reciprocal_rank=reciprocal_rank,
        citation_validity=(
            citation_validity(answer, retrieved_pages) if generate else None
        ),
        latency_ms=latency_ms,
        retrieved_pages=retrieved_pages,
        expected_pages=expected_page_labels,
    )


def summarise_results(results: list[EvaluationResult]) -> dict[str, float | int | None]:
    """Aggregate question-level evaluation results for dashboard display."""
    if not results:
        return {
            "questions": 0,
            "mean_precision_at_k": 0.0,
            "mean_recall_at_k": 0.0,
            "mean_reciprocal_rank": 0.0,
            "mean_citation_validity": None,
            "mean_latency_ms": 0.0,
        }

    citation_scores = [
        result.citation_validity
        for result in results
        if result.citation_validity is not None
    ]

    return {
        "questions": len(results),
        "mean_precision_at_k": mean(result.precision_at_k for result in results),
        "mean_recall_at_k": mean(result.recall_at_k for result in results),
        "mean_reciprocal_rank": mean(result.reciprocal_rank for result in results),
        "mean_citation_validity": mean(citation_scores) if citation_scores else None,
        "mean_latency_ms": mean(result.latency_ms for result in results),
    }
