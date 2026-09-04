from backend.ui import excerpt_html, format_excerpt_text


def test_pdf_line_breaks_become_inline_paragraph():
    blocks = format_excerpt_text(
        'Net profit increased during the year.\n'
        'The increase reflected stronger operating income.'
    )

    assert blocks == [
        'Net profit increased during the year. '
        'The increase reflected stronger operating income.'
    ]


def test_blank_lines_create_separate_paragraphs():
    html = excerpt_html('First financial paragraph.\n\nSecond financial paragraph.')

    assert html.count('<p>') == 2


def test_bullets_render_as_list_items():
    html = excerpt_html('- Credit risk\n- Liquidity risk')

    assert '<ul>' in html
    assert '<li>Credit risk</li>' in html
    assert '<li>Liquidity risk</li>' in html


def test_pdf_html_is_escaped_and_never_executed():
    html = excerpt_html('<script>alert("unsafe")</script>')

    assert '<script>' not in html
    assert '&lt;script&gt;' in html


def test_matched_text_remains_highlighted_after_line_joining():
    html = excerpt_html(
        'Net profit was Rs 1,250 crore.\nConsolidated results improved.',
        'Net profit was Rs 1,250 crore.',
    )

    assert '<mark>Net profit was Rs 1,250 crore.</mark>' in html
