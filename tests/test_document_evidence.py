import hashlib
import pytest
import pymupdf
from backend.pdf_processor import extract_pdf_pages, render_evidence_page
from backend.text_chunker import chunk_document
from backend.chunk_service import generate_chunk_payload
from backend.retrieval_service import KeywordIndex, fuse_results
from backend.ui import excerpt_html


def make_pdf(path):
    with pymupdf.open() as doc:
        page = doc.new_page()
        page.insert_textbox((60, 60, 520, 150),
                            'Net profit was Rs 1,250 crore.\nThe amount relates to the consolidated business.')
        page.insert_textbox((60, 200, 520, 280), 'Risk management\nLiquidity risk is monitored daily.')
        doc.new_page()  # scanned/blank page must not create evidence
        doc.save(path)


def test_pdf_to_chunk_pipeline_and_highlight(tmp_path):
    path = tmp_path / 'annual-report.pdf'
    make_pdf(path)
    pages = extract_pdf_pages(str(path))
    assert len(pages) == 2
    assert pages[1]['text'] == ''
    assert len(pages[0]['paragraphs']) == 2
    document = {'company': 'Example Bank', 'financial_year': '2025-26',
                'source_file': path.name, 'storage': {'raw_s3_key': 'original.pdf'}, 'pages': pages}
    payload, chunks = generate_chunk_payload(document, 60, 10)
    assert payload['storage']['raw_s3_key'] == 'original.pdf'
    assert all(c['document_id'] == payload['document_id'] for c in chunks)
    assert all(c['company'] == 'Example Bank' for c in chunks)
    assert all(c['bbox'] and c['paragraph_text'] for c in chunks)
    original = path.read_bytes()
    result = chunks[0]
    png = render_evidence_page(original, 1, [result['bbox']], result['pdf_sha256'])
    assert png.startswith(b'\x89PNG')
    assert path.read_bytes() == original
    assert png != render_evidence_page(original, 1)
    with pytest.raises(ValueError, match='changed'):
        render_evidence_page(original, 1, expected_sha256='wrong')
    with pytest.raises(ValueError, match='outside'):
        render_evidence_page(original, 3)


def test_search_windows_preserve_full_parent_and_words():
    text = ' '.join(f'Token{i}' for i in range(100)) + ' Rs 1,234.56 crore.'
    chunks = chunk_document([{'page_number': 3, 'text': text}], 70, 15)
    assert len(chunks) > 1
    assert all(c['paragraph_text'] == text for c in chunks)
    assert set(text.split()) == {word for c in chunks for word in c['text'].split()}
    assert [c['chunk_id'] for c in chunks] == list(range(1, len(chunks) + 1))


def test_long_token_and_sentence_boundaries_terminate():
    chunks = chunk_document([{'page_number': 1, 'text': 'x' * 100 + ' trailing word.'}], 20, 19)
    assert chunks[0]['text'] == 'x' * 100
    assert len(chunks) < 20
    text = 'First sentence ends here. Second sentence has more words.'
    chunks = chunk_document([{'text': text}], 35, 0)
    assert chunks[0]['text'] == 'First sentence ends here.'


@pytest.mark.parametrize('size,overlap', [(0, 0), (10, 10), (10, -1)])
def test_invalid_chunk_parameters(size, overlap):
    with pytest.raises(ValueError):
        chunk_document([], size, overlap)


def test_document_identity_changes_when_pdf_changes():
    a, _ = generate_chunk_payload({'pages': [{'text': 'Report', 'pdf_sha256': 'a'}]})
    b, _ = generate_chunk_payload({'pages': [{'text': 'Report', 'pdf_sha256': 'b'}]})
    assert a['document_id'] != b['document_id']


def test_hybrid_ranking_and_parent_deduplication():
    chunks = [
        {'text': 'Capital adequacy ratio CET1 is 18%.', 'paragraph_id': 'a', 'page_number': 1},
        {'text': 'More CET1 capital adequacy information.', 'paragraph_id': 'a', 'page_number': 1},
        {'text': 'Office staff and facilities.', 'paragraph_id': 'b', 'page_number': 2},
    ]
    lexical = KeywordIndex(chunks).search('CET1 capital adequacy', 10)
    assert lexical[0][0] in (0, 1)
    dense = [{'_index_position': 2, 'similarity_score': .7},
             {'_index_position': 0, 'similarity_score': .6}]
    results = fuse_results(chunks, dense, lexical, 5)
    assert results[0]['paragraph_id'] == 'a'
    assert len(results) == 2
    assert 'similarity_score' in results[0]
    assert KeywordIndex(chunks).search('astronaut', 10) == []
    assert fuse_results(chunks, [{'_index_position': 0, 'similarity_score': -.2}], [], 5) == []


def test_document_text_is_escaped_and_only_exact_match_highlighted():
    html = excerpt_html('<script>alert(1)</script> profit $12', 'profit $12')
    assert '<script>' not in html
    assert '&lt;script&gt;' in html
    assert '<mark>profit $12</mark>' in html
