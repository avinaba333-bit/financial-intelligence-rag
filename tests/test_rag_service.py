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
                                 source_excerpt_answer, _checked)


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
    assert 'did not pass' in answer
    assert 'No synthesized answer' in answer


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
