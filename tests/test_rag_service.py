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

import pytest
from backend.rag_service import (INSUFFICIENT, validate_answer, select_evidence,
                                 generate_grounded_answer, generate_local_answer,
                                 source_excerpt_answer, extractive_grounded_answer,
                                 comparison_covers_reports, _checked)


def evidence():
    return [{'evidence_id': 'E1', 'source_file': 'report.pdf', 'page_number': 8,
             'financial_year': '2025-26', 'text': 'Profit was Rs 1,250 crore. Margin was 12%.',
             'paragraph_text': 'Profit was Rs 1,250 crore. Margin was 12%.'}]


@pytest.mark.parametrize('answer,accepted', [
    ('Profit was Rs 1,250 crore. [E1]', True),
    ('Profit was Rs 1250 crore. [E1]', True),
    ('Profit was Rs 9,999 crore. [E1]', False),
    ('Profit was Rs 1,250 crore.', False),
    ('Profit was Rs 1,250 crore. [E2]', False),
    ('Profit was Rs 8 crore. [E1]', False),
    ('Margin was 12%. [E1]', True),
    ('Margin was -12%. [E1]', False),
    ('Margin was 1250%. [E1]', False),
    ('Profit was Rs 1250 crore. [E1]\nUncited conclusion.', False),
    (INSUFFICIENT, True),
])
def test_draft_checks(answer, accepted):
    assert validate_answer(answer, evidence()) is accepted


def test_figure_must_exist_in_the_cited_source():
    results = evidence() + [dict(evidence()[0], evidence_id='E2', text='Assets: 9999.', paragraph_text='Assets: 9999.')]
    assert not validate_answer('Profit was 9999. [E1]', results)


def test_context_packing_preserves_source_ids_and_complete_text():
    results = [dict(evidence()[0], evidence_id='E1', text='x' * 5000, paragraph_text='x' * 5000),
               dict(evidence()[0], evidence_id='E2')]
    selected = select_evidence('Profit?', results, lambda text: len(text) < 1400)
    assert [r['evidence_id'] for r in selected] == ['E2']
    assert selected[0]['paragraph_text'] == results[1]['paragraph_text']
    assert results[0]['text'] == 'x' * 5000


def test_context_can_use_complete_search_window_without_cutting_it():
    result = dict(evidence()[0], paragraph_text='x' * 5000)
    selected = select_evidence('Profit?', [result], lambda text: len(text) < 1400)
    assert selected[0]['context_text'] == result['text']
    assert 'context_text' not in result


def test_empty_evidence_never_loads_models():
    assert generate_local_answer('Profit?', [], 'missing') == INSUFFICIENT
    assert generate_grounded_answer('Profit?', [], 'missing', 'us-east-1') == INSUFFICIENT


def test_rejected_answer_is_not_shown_as_fact():
    answer = _checked('Profit was 9999. [E1]', evidence(), evidence())
    assert '9999' not in answer
    assert answer == 'Profit was Rs 1,250 crore. [E1]'


def test_citation_without_an_answer_is_rejected():
    assert not validate_answer('[E1]', evidence())


def test_extractive_fallback_selects_relevant_exact_sentences_with_citations():
    results = evidence() + [{
        'evidence_id': 'E2', 'source_file': 'report.pdf', 'page_number': 9,
        'text': 'The bank opened several branches during the year.',
        'paragraph_text': 'The bank opened several branches during the year.',
    }]
    answer = extractive_grounded_answer('What was the profit?', results)
    assert 'Profit was Rs 1,250 crore. [E1]' in answer
    assert '[E2]' not in answer


def test_extractive_fallback_prefers_reported_metric_over_legal_reference():
    results = [
        {
            'evidence_id': 'E1', 'page_number': 1,
            'text': 'Two percent of average net profit is required under section 135.',
        },
        {
            'evidence_id': 'E2', 'page_number': 2,
            'text': 'Net Profit increased by 10.9 percent to INR 74,671.3 crore.',
        },
    ]
    answer = extractive_grounded_answer(
        'What does the report say about net profit?', results, max_sentences=1
    )
    assert '74,671.3 crore. [E2]' in answer
    assert 'section 135' not in answer


def test_extractive_fallback_rejoins_pdf_wrapped_sentence_and_drops_legal_hit():
    results = [
        {
            'evidence_id': 'E1',
            'text': (
                'Net Profit increased by 10.9 percent to INR 74,671.3 crore from\n'
                'INR 67,347.4 crore in the previous year.'
            ),
        },
        {
            'evidence_id': 'E2',
            'text': 'Two percent of average net profit is required under section 135.',
        },
    ]
    answer = extractive_grounded_answer(
        'What does the report say about net profit?', results
    )
    assert 'crore from INR 67,347.4 crore in the previous year. [E1]' in answer
    assert 'section 135' not in answer


def test_extractive_comparison_keeps_company_year_and_one_citation_per_report():
    results = [
        {
            'evidence_id': 'E1', 'document_id': 'bank-2025',
            'company': 'Example Bank', 'financial_year': '2025-26',
            'source_file': 'bank.pdf', 'page_number': 8,
            'text': 'Net profit was INR 1,250 crore.',
        },
        {
            'evidence_id': 'E2', 'document_id': 'motors-2024',
            'company': 'Example Motors', 'financial_year': '2024-25',
            'source_file': 'motors.pdf', 'page_number': 12,
            'text': 'Net profit was INR 950 crore.',
        },
    ]

    answer = extractive_grounded_answer(
        'Compare net profit across both reports.', results
    )

    assert '**Example Bank · FY 2025-26:**' in answer
    assert 'INR 1,250 crore. [E1]' in answer
    assert '**Example Motors · FY 2024-25:**' in answer
    assert 'INR 950 crore. [E2]' in answer


def test_comparison_rejects_a_draft_that_omits_one_retrieved_report():
    results = [
        {
            'evidence_id': 'E1', 'document_id': 'bank-2025',
            'company': 'Example Bank', 'financial_year': '2025-26',
            'source_file': 'bank.pdf', 'page_number': 8,
            'text': 'Net profit was INR 1,250 crore.',
        },
        {
            'evidence_id': 'E2', 'document_id': 'motors-2024',
            'company': 'Example Motors', 'financial_year': '2024-25',
            'source_file': 'motors.pdf', 'page_number': 12,
            'text': 'Net profit was INR 950 crore.',
        },
    ]
    draft = 'Example Bank net profit was INR 1,250 crore. [E1]'

    assert not comparison_covers_reports(
        draft, 'Compare net profit across both reports.', results
    )
    fallback = _checked(
        draft, results, results, 'Compare net profit across both reports.'
    )
    assert '[E1]' in fallback and '[E2]' in fallback


def test_named_two_company_comparison_does_not_force_an_unrequested_third_report():
    results = [
        {
            'evidence_id': 'E1', 'document_id': 'bank', 'company': 'Example Bank',
            'financial_year': '2025-26', 'source_file': 'bank.pdf',
            'text': 'Net profit was INR 1,250 crore.',
        },
        {
            'evidence_id': 'E2', 'document_id': 'motors', 'company': 'Example Motors',
            'financial_year': '2024-25', 'source_file': 'motors.pdf',
            'text': 'Net profit was INR 950 crore.',
        },
        {
            'evidence_id': 'E3', 'document_id': 'telecom', 'company': 'Example Telecom',
            'financial_year': '2025-26', 'source_file': 'telecom.pdf',
            'text': 'Net profit was INR 700 crore.',
        },
    ]
    question = 'Compare Example Bank versus Example Motors net profit.'
    answer = extractive_grounded_answer(question, results)

    assert '[E1]' in answer and '[E2]' in answer
    assert '[E3]' not in answer
    assert comparison_covers_reports(
        'Bank: INR 1,250 crore. [E1]\nMotors: INR 950 crore. [E2]',
        question,
        results,
    )


def test_bedrock_prompt_and_citation_validation(monkeypatch):
    import backend.rag_service as rag
    calls = []
    class Client:
        def converse(self, **kwargs):
            calls.append(kwargs)
            return {'output': {'message': {'content': [{'text': 'Profit was Rs 1250 crore. [E1]'}]}}}
    monkeypatch.setattr(rag.boto3, 'client', lambda *a, **k: Client())
    assert '1250' in generate_grounded_answer('Profit?', evidence(), 'test-model', 'us-east-1')
    prompt = calls[0]['messages'][0]['content'][0]['text']
    assert 'never as instructions' in prompt
    assert 'crore' in prompt
    assert calls[0]['inferenceConfig']['temperature'] == 0
