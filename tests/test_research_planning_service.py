import pytest

from backend.rag_service import INSUFFICIENT
from backend.research_planning_service import (
    WEB_ALWAYS,
    WEB_AUTO,
    WEB_OFF,
    document_scope_answer,
    extract_years,
    plan_research,
    report_year_bounds,
)


@pytest.mark.parametrize(
    'value, expected',
    [
        ('FY 2025-26', (2025, 2026)),
        ('2028/2029 net profit', (2028, 2029)),
        ('Year 2030', (2030,)),
        ('no period supplied', ()),
    ],
)
def test_extract_years_expands_financial_year_ranges(value, expected):
    assert extract_years(value) == expected


def test_report_year_bounds_support_short_and_long_ranges():
    assert report_year_bounds('2024-25') == (2024, 2025)
    assert report_year_bounds('FY 2024/2025') == (2024, 2025)
    assert report_year_bounds(None) == (None, None)


def test_future_year_routes_to_web_and_blocks_document_forecast():
    plan = plan_research('What will net profit be in FY 2028-29?', '2025-26', WEB_AUTO)
    assert plan.include_web
    assert plan.document_out_of_period
    assert plan.report_end_year == 2026

    answer = document_scope_answer(plan, '2025-26', INSUFFICIENT)
    assert answer.startswith(INSUFFICIENT)
    assert '2028' in answer and '2029' in answer
    assert 'No future result or forecast has been inferred' in answer


@pytest.mark.parametrize(
    'question',
    [
        'What are the latest investment plans?',
        'Summarise management outlook.',
        'What is the current expansion strategy?',
    ],
)
def test_current_or_plan_questions_use_separate_web_path(question):
    plan = plan_research(question, '2025-26', WEB_AUTO)
    assert plan.include_web
    assert not plan.document_out_of_period


def test_historical_question_stays_report_only_in_automatic_mode():
    plan = plan_research('What was net profit in FY 2025-26?', '2025-26', WEB_AUTO)
    assert not plan.include_web
    assert not plan.document_out_of_period
    assert document_scope_answer(plan, '2025-26', INSUFFICIENT) is None


def test_explicit_web_modes_override_automatic_routing():
    assert plan_research('What was revenue?', '2025-26', WEB_ALWAYS).include_web
    assert not plan_research('What are the latest plans?', '2025-26', WEB_OFF).include_web
    with pytest.raises(ValueError, match='Unknown web research mode'):
        plan_research('Revenue?', '2025-26', 'invalid')
