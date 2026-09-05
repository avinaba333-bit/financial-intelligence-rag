"""UI integration tests with synthetic reports; no AWS or model downloads."""
from pathlib import Path
import hashlib
import numpy as np
import faiss
import pymupdf
import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def fake_reports(monkeypatch):
    import config
    import backend.embedding_service as embeddings
    from backend.storage_service import S3Storage, S3Document
    st.cache_resource.clear()
    st.cache_data.clear()
    monkeypatch.setattr(config, 'S3_BUCKET', 'synthetic-test-bucket')
    with pymupdf.open() as doc:
        page = doc.new_page()
        page.insert_text((72, 72), 'Net profit was Rs 1,250 crore.')
        pdf = doc.tobytes()
    chunks = [{'text': 'Net profit was Rs 1,250 crore.',
               'paragraph_text': 'Net profit was Rs 1,250 crore.\nConsolidated results.',
               'paragraph_id': 'p1-b1', 'page_number': 1, 'source_file': 'report.pdf',
               'bbox': [65, 55, 400, 80], 'pdf_sha256': hashlib.sha256(pdf).hexdigest()}]
    index = faiss.IndexFlatIP(3)
    index.add(np.array([[1, 0, 0]], dtype=np.float32))
    metadata = {'index_s3_key': 'test.faiss', 'schema_version': 2, 'document_id': 'synthetic',
                'company': 'Example Bank', 'financial_year': '2025-26', 'source_file': 'report.pdf',
                'storage': {'raw_s3_key': 'original.pdf'}, 'chunks': chunks}
    reports = [S3Document('reports/example/2025-26/vector-store/report_metadata.json', 'Example'),
               S3Document('reports/other/2025-26/vector-store/report_metadata.json', 'Other')]
    monkeypatch.setattr(S3Storage, '__init__', lambda self, *a, **k: None)
    monkeypatch.setattr(S3Storage, 'list_vector_metadata', lambda self: reports)
    monkeypatch.setattr(S3Storage, 'download_json', lambda self, key: metadata)
    monkeypatch.setattr(S3Storage, 'download_bytes', lambda self, key: pdf if key.endswith('.pdf') else faiss.serialize_index(index).tobytes())

    class FakeEmbedding:
        def encode(self, *args, **kwargs):
            return np.array([[1, 0, 0]], dtype=np.float32)

    monkeypatch.setattr(embeddings, 'get_embedding_model', lambda: FakeEmbedding())
    yield metadata
    st.cache_resource.clear()
    st.cache_data.clear()


def button(at, label):
    return next(b for b in at.button if b.label == label)


def test_chat_evidence_pdf_preview_and_report_switch(fake_reports):
    at = AppTest.from_file(
        str(ROOT / 'pages/5_ai_assistant.py'),
        default_timeout=15,
    ).run()
    assert not at.exception
    at.radio[0].set_value('Source excerpts').run()
    at.chat_input[0].set_value('What was net profit?').run()
    assert not at.exception
    assert len(at.chat_message) == 2
    assert 'Source excerpts' in at.session_state['messages'][-1]['content']
    assert at.session_state['messages'][-1]['evidence'][0]['paragraph_text'].endswith('Consolidated results.')
    button(at, 'Show original page').click().run()
    assert not at.exception
    assert len(at.get('image')) == 1
    # On rerun the same source buttons must have stable keys and keep history.
    button(at, 'E1 · PDF page 1 — Open original').click().run()
    assert not at.exception
    assert len(at.chat_message) == 2
    at.selectbox[0].select_index(1).run()
    assert not at.exception
    assert at.session_state['messages'] == []
    assert 'active_evidence' not in at.session_state


def test_model_failure_retains_sources(fake_reports, monkeypatch):
    import backend.rag_service as rag
    import config
    monkeypatch.setattr(config, 'CHAT_MODEL_ID', '')

    def fail(*args):
        raise rag.GenerationError('Test model unavailable')

    monkeypatch.setattr(rag, 'generate_local_answer', fail)
    at = AppTest.from_file(str(ROOT / 'pages/5_ai_assistant.py'), default_timeout=15).run()
    at.chat_input[0].set_value('What was net profit?').run()
    assert not at.exception
    assert 'model is unavailable' in at.session_state['messages'][-1]['content']
    assert at.session_state['messages'][-1]['evidence']


def test_future_question_keeps_report_and_web_answers_separate(fake_reports, monkeypatch):
    from datetime import datetime, timezone
    import backend.web_research_service as web

    def fake_web_search(*args, **kwargs):
        return web.WebResearchResult(
            query='Example Bank investment outlook 2026',
            answer='A current investor update describes a planned branch investment. [W1]',
            sources=(
                web.WebSource(
                    evidence_id='W1',
                    title='Investor update',
                    url='https://example.com/investor-update',
                    summary='A planned branch investment was announced.',
                    domain='example.com',
                    published='2026-08-30',
                ),
            ),
            searched_at=datetime(2026, 9, 5, tzinfo=timezone.utc).isoformat(),
        )

    monkeypatch.setattr(web, 'search_current_web', fake_web_search)
    at = AppTest.from_file(str(ROOT / 'pages/5_ai_assistant.py'), default_timeout=15).run()
    at.chat_input[0].set_value('What will net profit be in FY 2028-29?').run()

    assert not at.exception
    response = at.session_state['messages'][-1]
    assert response['content'].startswith(
        'The selected report evidence is insufficient to answer this question.'
    )
    assert response['research_plan']['document_out_of_period']
    assert response['web_research']['sources'][0]['evidence_id'] == 'W1'
    assert all(source['evidence_id'].startswith('E') for source in response['evidence'])
    rendered = '\n'.join(markdown.value for markdown in at.markdown)
    assert 'Uploaded report evidence answer' in rendered
    assert 'Current web research answer' in rendered
    assert '[W1]' in rendered


def test_landing_page_has_working_navigation():
    at = AppTest.from_file(str(ROOT / 'app.py'), default_timeout=15).run()
    assert not at.exception
    assert len(at.get('page_link')) == 4
