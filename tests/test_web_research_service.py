from datetime import datetime, timezone

import pytest

from backend.web_research_service import WebResearchError, search_current_web


def test_web_search_is_source_linked_deduplicated_and_separate():
    calls = []

    def fake_search(query, max_results):
        calls.append((query, max_results))
        return [
            {
                'title': 'Investor update',
                'href': 'https://example.com/investors/update#section',
                'body': 'The company announced a Rs 500 crore expansion plan.',
                'date': '2026-08-30',
            },
            {
                'title': 'Duplicate result',
                'url': 'https://example.com/investors/update',
                'snippet': 'Duplicate text should not become another source.',
            },
            {
                'title': 'Exchange filing',
                'url': 'https://exchange.example/filing',
                'description': 'The filing describes the planned project timetable.',
            },
        ]

    result = search_current_web(
        'Example Industries',
        'What are the future investment plans?',
        max_results=5,
        search_fn=fake_search,
        now=datetime(2026, 9, 5, 12, 0, tzinfo=timezone.utc),
    )

    assert len(calls) == 1
    assert all('Example Industries' in query for query, _ in calls)
    assert len(result.sources) == 2
    assert [source.evidence_id for source in result.sources] == ['W1', 'W2']
    assert result.sources[0].url == 'https://example.com/investors/update'
    assert 'Rs 500 crore' in result.answer
    assert '[W1]' in result.answer
    assert '[E1]' not in result.answer
    assert result.searched_at == '2026-09-05T12:00:00+00:00'


def test_unsafe_or_empty_results_are_not_presented_as_sources():
    def fake_search(*_):
        return [
            {'title': 'Unsafe', 'href': 'javascript:alert(1)', 'body': 'Bad'},
            {'title': 'Empty', 'href': 'https://example.com/empty', 'body': ''},
        ]

    result = search_current_web('Example', 'future plans', search_fn=fake_search)
    assert result.sources == ()
    assert 'No relevant current web source was found' in result.answer


def test_provider_failure_becomes_safe_web_research_error():
    def failed_search(*_):
        raise RuntimeError('provider internals')

    with pytest.raises(WebResearchError, match='temporarily unavailable'):
        search_current_web('Example', 'latest plans', search_fn=failed_search)


def test_company_domain_is_ranked_before_generic_and_speculative_results():
    def fake_search(*_):
        return [
            {
                'title': 'General market commentary',
                'href': 'https://generic.example/article',
                'body': 'Commentary about the company.',
            },
            {
                'title': 'Example Energy investor relations',
                'href': 'https://exampleenergy.com/investors/plans',
                'body': 'The official investor page describes its expansion programme.',
            },
            {
                'title': 'Example Energy share price target 2030',
                'href': 'https://tips.example/target',
                'body': 'An unsupported price prediction.',
            },
        ]

    result = search_current_web('Example Energy Ltd', 'future plans', search_fn=fake_search)
    assert result.sources[0].domain == 'exampleenergy.com'
    assert all('target' not in source.url for source in result.sources)


def test_invalid_max_results_is_rejected_before_search():
    with pytest.raises(ValueError, match='at least 1'):
        search_current_web('Example', 'latest plans', max_results=0, search_fn=lambda *_: [])
