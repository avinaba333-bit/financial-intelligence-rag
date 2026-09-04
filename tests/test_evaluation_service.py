import pytest

from backend.evaluation_service import (
    citation_validity,
    evaluate_question,
    extract_page_citations,
    retrieval_metrics,
    summarise_results,
)


def test_retrieval_metrics_calculates_precision_recall_and_rank():
    precision, recall, reciprocal_rank = retrieval_metrics(
        retrieved_pages=[10, 20, 30],
        expected_pages=[20, 40],
    )

    assert precision == pytest.approx(1 / 3)
    assert recall == pytest.approx(1 / 2)
    assert reciprocal_rank == pytest.approx(1 / 2)


def test_retrieval_metrics_returns_zero_without_ground_truth():
    assert retrieval_metrics([10], []) == (0.0, 0.0, 0.0)


def test_extract_page_citations_is_case_insensitive():
    assert extract_page_citations("Profit rose [Page 42] and [page 43].") == [
        "42",
        "43",
    ]


def test_citation_validity_checks_citations_against_evidence():
    score = citation_validity(
        "Revenue increased [Page 10], while costs fell [Page 99].",
        evidence_pages=[10, 11],
    )

    assert score == pytest.approx(0.5)
    assert citation_validity("No citations here.", [10]) is None


def test_evaluate_question_runs_retrieval_and_generation():
    def retrieve(question):
        assert question == "What was the revenue?"
        return [
            {"page_number": 12, "text": "Revenue was INR 100 crore."},
            {"page_number": 15, "text": "Other information."},
        ]

    def generate(question, results):
        assert results[0]["page_number"] == 12
        return "Revenue was INR 100 crore [Page 12]."

    result = evaluate_question(
        question="What was the revenue?",
        expected_pages=[12],
        retrieve=retrieve,
        generate=generate,
    )

    assert result.precision_at_k == pytest.approx(0.5)
    assert result.recall_at_k == pytest.approx(1.0)
    assert result.reciprocal_rank == pytest.approx(1.0)
    assert result.citation_validity == pytest.approx(1.0)
    assert result.latency_ms >= 0


def test_summarise_results_handles_empty_input():
    summary = summarise_results([])

    assert summary["questions"] == 0
    assert summary["mean_citation_validity"] is None
