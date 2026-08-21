from backend.rag_service import build_evidence


def test_build_evidence_includes_source_page_and_text():
    results = [
        {
            "source_file": "annual-report.pdf",
            "page_number": 42,
            "text": "Net revenue increased during the year.",
        }
    ]

    evidence = build_evidence(results)

    assert "Evidence 1" in evidence
    assert "annual-report.pdf" in evidence
    assert "Page: 42" in evidence
    assert "Net revenue increased" in evidence
