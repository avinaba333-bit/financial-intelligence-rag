import pytest

from backend.multi_document_service import merge_report_results, selected_report_scope


def result(document, page, retrieval, similarity, text=None):
    return {
        'document_id': document,
        'source_file': f'{document}.pdf',
        'page_number': page,
        'paragraph_id': f'{document}-p{page}',
        'text': text or f'{document} evidence on page {page}',
        'retrieval_score': retrieval,
        'similarity_score': similarity,
        'keyword_score': retrieval * 10,
    }


def test_merge_report_results_keeps_one_source_from_each_report():
    bank = [
        result('bank', 10, .030, .82),
        result('bank', 11, .029, .81),
        result('bank', 12, .028, .80),
    ]
    motors = [
        result('motors', 20, .020, .72),
        result('motors', 21, .019, .71),
    ]

    merged = merge_report_results([bank, motors], top_k=3)

    assert [item['document_id'] for item in merged[:2]] == ['bank', 'motors']
    assert merged[2]['document_id'] == 'bank'


def test_merge_report_results_deduplicates_and_validates_top_k():
    duplicate = result('bank', 10, .030, .82)
    assert merge_report_results([[duplicate, dict(duplicate)]], top_k=5) == [duplicate]
    assert merge_report_results([], top_k=5) == []
    with pytest.raises(ValueError, match='positive'):
        merge_report_results([[duplicate]], top_k=0)


def test_selected_report_scope_is_unique_and_stable():
    companies, years = selected_report_scope([
        {'company': 'Example Bank', 'financial_year': '2025-26'},
        {'company': 'Example Motors', 'financial_year': '2024-25'},
        {'company': 'Example Bank', 'financial_year': '2025-26'},
    ])

    assert companies == ('Example Bank', 'Example Motors')
    assert years == ('2025-26', '2024-25')
