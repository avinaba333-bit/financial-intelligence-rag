import pytest

from backend.financial_visualization_service import (
    build_visualization_spec,
    create_plotly_figure,
    extract_financial_data,
    visualization_rows,
)


def test_extracts_labelled_values_with_source_pages():
    evidence = [
        {
            "paragraph_text": (
                "Retail Banking was INR 1,250 crore. "
                "Wholesale Banking was INR 980 crore."
            ),
            "page_number": 42,
            "source_file": "annual-report.pdf",
        }
    ]

    points = extract_financial_data(evidence)

    assert [point.label for point in points] == [
        "Retail Banking",
        "Wholesale Banking",
    ]
    assert [point.value for point in points] == [1250.0, 980.0]
    assert points[0].currency == "INR"
    assert points[0].unit == "crore"
    assert points[0].citation == "[Page 42]"


def test_year_series_creates_line_chart_specification():
    evidence = [
        {
            "text": "FY 2024-25: INR 1,250 crore. FY 2023-24: INR 1,100 crore.",
            "page_number": 12,
            "source_file": "annual-report.pdf",
        }
    ]

    spec = build_visualization_spec("How did revenue change?", evidence)

    assert spec is not None
    assert spec.chart_type == "line"
    assert spec.x_label == "Financial year"
    assert len(spec.points) == 2


def test_categories_create_bar_chart_specification():
    evidence = [
        {
            "text": "Retail Banking: INR 500 crore. Treasury: INR 350 crore.",
            "page_number": 90,
            "source_file": "annual-report.pdf",
        }
    ]

    spec = build_visualization_spec("Compare segment profit", evidence)

    assert spec is not None
    assert spec.chart_type == "bar"
    assert spec.x_label == "Category"


def test_no_chart_is_created_for_only_one_value():
    evidence = [
        {
            "text": "Net profit was INR 1,250 crore.",
            "page_number": 42,
            "source_file": "annual-report.pdf",
        }
    ]

    assert build_visualization_spec("What was net profit?", evidence) is None


def test_duplicate_evidence_values_are_removed():
    item = {
        "text": "Net profit was INR 1,250 crore.",
        "page_number": 42,
        "source_file": "annual-report.pdf",
    }

    points = extract_financial_data([item, item])

    assert len(points) == 1


def test_plotly_chart_and_table_preserve_citations():
    evidence = [
        {
            "text": "Retail Banking: INR 500 crore. Treasury: INR 350 crore.",
            "page_number": 90,
            "source_file": "annual-report.pdf",
        }
    ]
    spec = build_visualization_spec("Compare segment profit", evidence)
    assert spec is not None

    figure = create_plotly_figure(spec)
    rows = visualization_rows(spec)

    assert len(figure.data) == 1
    assert list(figure.data[0].y) == [500.0, 350.0]
    assert figure.data[0].customdata[0][1] == "[Page 90]"
    assert rows[0]["Page"] == "90"
    assert rows[0]["Source"] == "annual-report.pdf"


def test_mixed_units_use_largest_compatible_group():
    evidence = [
        {
            "text": (
                "Revenue was INR 1,250 crore. Profit was INR 250 crore. "
                "Margin was 20%."
            ),
            "page_number": 7,
            "source_file": "annual-report.pdf",
        }
    ]

    spec = build_visualization_spec("Compare the financial results", evidence)

    assert spec is not None
    assert len(spec.points) == 2
    assert all(point.unit == "crore" for point in spec.points)
