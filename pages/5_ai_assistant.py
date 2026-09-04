from pathlib import PurePosixPath
import streamlit as st

from backend.embedding_service import DEFAULT_MODEL, deserialize_faiss_index, search_faiss_index
from backend.financial_visualization_service import (
    build_visualization_spec,
    create_plotly_figure,
    extract_financial_data,
    visualization_rows,
)
from backend.pdf_processor import render_evidence_page
from backend.rag_service import (GenerationError, generate_grounded_answer,
                                 generate_local_answer, source_excerpt_answer)
from backend.retrieval_service import KeywordIndex, fuse_results, rerank_results
from backend.storage_service import S3Storage, StorageError
from backend.ui import apply_style, hero, readable_report_label, show_excerpt
from config import AWS_REGION, CHAT_MODEL_ID, LOCAL_CHAT_MODEL_ID, S3_BUCKET, S3_PREFIX

st.set_page_config(page_title='FinSight | Report assistant', page_icon='💬', layout='wide')
apply_style()
hero('Your reports. Clearer answers.',
     'Explore financial reports with traceable evidence and the original PDF beside your conversation.')

if not S3_BUCKET:
    st.info('Configure S3_BUCKET, upload a report, and build its vector index to start chatting.')
    st.page_link('pages/1_upload_reports.py', label='Upload financial reports', icon='📄')
    st.stop()


@st.cache_resource(show_spinner=False, ttl=300, max_entries=3)
def load_vector_store(bucket, region, prefix, metadata_key):
    storage = S3Storage(bucket, region, prefix)
    metadata = storage.download_json(metadata_key)
    if not metadata.get('index_s3_key'):
        raise ValueError('The index location is missing. Rebuild the vector index.')
    if metadata.get('embedding_model', DEFAULT_MODEL) != DEFAULT_MODEL:
        raise ValueError('This index uses a different embedding model. Rebuild with the current model.')
    index = deserialize_faiss_index(storage.download_bytes(metadata['index_s3_key']))
    chunks = metadata.get('chunks', [])
    if index.ntotal != len(chunks):
        raise ValueError('Index and chunk counts differ. Rebuild the vector index.')
    chunks = [dict(chunk, company=metadata.get('company'),
                   financial_year=metadata.get('financial_year')) for chunk in chunks]
    return index, chunks, metadata, KeywordIndex(chunks)


@st.cache_data(show_spinner=False, ttl=300, max_entries=3)
def load_pdf(bucket, region, prefix, raw_key):
    return S3Storage(bucket, region, prefix).download_bytes(raw_key)


@st.cache_data(show_spinner=False, ttl=60)
def list_reports(bucket, region, prefix):
    return S3Storage(bucket, region, prefix).list_vector_metadata()


def clear_chat():
    st.session_state.messages = []
    st.session_state.pop('active_evidence', None)
    st.session_state.pop('pdf_preview_key', None)


with st.sidebar:
    st.subheader('Research workspace')
    if st.button('Refresh reports & indexes', width='stretch'):
        load_vector_store.clear()
        load_pdf.clear()
        list_reports.clear()
        clear_chat()
    try:
        reports = list_reports(S3_BUCKET, AWS_REGION, S3_PREFIX)
    except StorageError:
        st.error('Reports are unavailable. Check the configured bucket and AWS access.')
        st.stop()
    if not reports:
        st.info('Build a vector index first.')
        st.page_link('pages/4_vector_index.py', label='Build index')
        st.stop()
    selected = st.selectbox('Annual report', reports, format_func=readable_report_label)
    mode = st.radio('Answer mode', ['AI answer', 'Source excerpts'],
                    help='AI drafts receive citation and number checks, not full factual verification.')
    with st.expander('Search settings'):
        top_k = st.slider('Source blocks', 3, 10, 5)
        use_reranker = st.checkbox('Use CPU reranker', value=False,
            help='Downloads an additional model on first use. Adds latency and memory use.')
        min_similarity = st.slider('Minimum dense similarity', 0.0, 0.8, 0.15, 0.05,
            help='A search filter, not an accuracy percentage. Keyword matches can still be included.')
        st.caption('Search combines semantic similarity with BM25 keyword ranking.')
    if st.button('Clear conversation', width='stretch'):
        clear_chat()
    st.caption('Model: ' + (CHAT_MODEL_ID or LOCAL_CHAT_MODEL_ID))
    st.caption('Each question is searched independently. Include the year and metric in follow-ups.')

if st.session_state.get('selected_vector_key') != selected.key:
    st.session_state.selected_vector_key = selected.key
    clear_chat()
st.session_state.setdefault('messages', [])

try:
    index, chunks, metadata, keyword_index = load_vector_store(S3_BUCKET, AWS_REGION, S3_PREFIX, selected.key)
except (StorageError, ValueError, RuntimeError):
    st.error('Unable to load this index. Check storage access and rebuild if its metadata is incompatible.')
    st.stop()

identity = (selected.key, metadata.get('document_id'), index.ntotal, metadata.get('schema_version'))
if st.session_state.get('loaded_report_identity') != identity:
    clear_chat()
    st.session_state.loaded_report_identity = identity

c1, c2, c3 = st.columns(3)
c1.metric('Company', metadata.get('company') or 'Not specified')
c2.metric('Financial year', metadata.get('financial_year') or 'Not specified')
c3.metric('Searchable passages', index.ntotal)
if metadata.get('schema_version', 1) < 2:
    st.warning('Legacy index: excerpts may end mid-paragraph. Reprocess the PDF, regenerate chunks, '
               'and rebuild the index for complete source blocks and highlighting.')
st.caption('Citations use physical PDF pages; printed page labels may differ. Always verify figures against the original page.')


def show_sources(results, message_number):
    with st.expander(f'Source evidence · {len(results)} blocks', expanded=True):
        if not results:
            st.info('No source evidence was retrieved for this question.')
            return

        selector_key = f'selected-source-{message_number}'
        available_ids = [result['evidence_id'] for result in results]
        if st.session_state.get(selector_key) not in available_ids:
            st.session_state[selector_key] = available_ids[0]

        st.caption(
            'Select a source page below. One evidence paragraph is shown at a '
            'time so that its report and page citation remain clear.'
        )
        source_columns = st.columns(min(len(results), 5))
        for position, result in enumerate(results):
            evidence_id = result['evidence_id']
            page = result.get('page_number', '?')
            selected_now = st.session_state[selector_key] == evidence_id
            if source_columns[position % len(source_columns)].button(
                f'{evidence_id} · Page {page}',
                key=f'pick-source-{message_number}-{evidence_id}',
                type='primary' if selected_now else 'secondary',
                width='stretch',
            ):
                st.session_state[selector_key] = evidence_id
                st.session_state.pop('pdf_preview_key', None)

        selected_result = next(
            result
            for result in results
            if result['evidence_id'] == st.session_state[selector_key]
        )
        evidence_id = selected_result['evidence_id']
        page = selected_result.get('page_number', '?')
        source_file = selected_result.get('source_file', 'Report')
        financial_year = selected_result.get('financial_year') or 'Year not specified'

        st.markdown(f'#### {evidence_id} · PDF page {page}')
        st.caption(f'{source_file} · {financial_year}')
        parent = selected_result.get(
            'paragraph_text',
            selected_result.get('text', ''),
        )
        matched = (
            selected_result.get('text', '')
            if parent != selected_result.get('text')
            else ''
        )
        show_excerpt(parent, matched)

        label = f'{evidence_id} · PDF page {page} — Open original'
        if st.button(
            label,
            key=f'source-{message_number}-{evidence_id}',
            width='stretch',
        ):
            st.session_state.active_evidence = selected_result

        with st.expander('Search details'):
            detail1, detail2, detail3 = st.columns(3)
            detail1.metric(
                'Semantic similarity',
                f"{selected_result.get('similarity_score', 0):.3f}",
            )
            detail2.metric(
                'Keyword score',
                f"{selected_result.get('keyword_score', 0):.3f}",
            )
            rerank_score = selected_result.get('rerank_score')
            detail3.metric(
                'Reranker score',
                f'{rerank_score:.3f}' if rerank_score is not None else 'Not used',
            )
            st.caption(
                'Ranking scores help order search results. They are not '
                'confidence or factual-accuracy percentages.'
            )


def show_financial_visualization(question, results, chart_key):
    """Render only evidence-grounded charts containing comparable values."""
    if not results:
        return

    try:
        spec = build_visualization_spec(question, results)
    except (TypeError, ValueError):
        spec = None

    if spec is None:
        points = extract_financial_data(results)
        if len(points) == 1:
            point = points[0]
            st.markdown('#### Key financial figure')
            metric_column, source_column = st.columns([1, 2])
            metric_column.metric(point.label, point.display_value)
            source_column.caption(
                f'Source: {point.source_file} · PDF page {point.page_number}'
            )
        return

    with st.expander('Financial visualization', expanded=True):
        metric_points = spec.points[:4]
        metric_columns = st.columns(len(metric_points))
        for column, point in zip(metric_columns, metric_points):
            column.metric(point.label, point.display_value)
            column.caption(f'{point.citation} · {point.source_file}')

        figure = create_plotly_figure(spec)
        st.plotly_chart(figure, width='stretch', key=chart_key)

        with st.expander('View chart data and sources'):
            st.dataframe(
                visualization_rows(spec),
                width='stretch',
                hide_index=True,
            )
            st.caption(
                'Every plotted value was extracted from retrieved report evidence. '
                'Verify complex tables against the original PDF page.'
            )


conversation, reference = st.columns([1.15, 1], gap='large')
with conversation:
    st.subheader('Report conversation')
    st.markdown('#### Ask your own question')
    st.caption(
        'Type a question about a metric, business segment, financial year, '
        'comparison, or risk in the selected report.'
    )
    question = st.chat_input(
        'Type your financial-report question here…',
        key='manual-report-question',
    )

    suggested = None
    if not st.session_state.messages:
        st.write('Or start with one of these suggested questions:')
        for sample in ['What does the report say about net profit?',
                       'Which business segments are discussed?',
                       'What are the main risks described?']:
            if st.button(sample, key=sample, width='stretch'):
                suggested = sample
    for n, message in enumerate(st.session_state.messages):
        avatar = '👤' if message['role'] == 'user' else '🤖'
        with st.chat_message(message['role'], avatar=avatar):
            st.markdown(message['content'])
            if message.get('evidence') and message.get('question'):
                show_financial_visualization(
                    message['question'],
                    message['evidence'],
                    f'history-chart-{n}',
                )
            if message.get('evidence'):
                show_sources(message['evidence'], n)
    question = question or suggested
    if question:
        st.session_state.messages.append({'role': 'user', 'content': question})
        with st.chat_message('user', avatar='👤'):
            st.markdown(question)
        with st.chat_message('assistant', avatar='🤖'):
            try:
                with st.spinner('Finding relevant passages…'):
                    candidates = min(max(top_k * 5, 25), len(chunks))
                    dense = search_faiss_index(index, chunks, question, max(candidates, 1))
                    lexical = keyword_index.search(question, candidates)
                    results = fuse_results(chunks, dense, lexical,
                                           candidates if use_reranker else top_k, min_similarity)
                    if use_reranker:
                        try:
                            results = rerank_results(question, results, top_k)
                        except (ImportError, OSError, RuntimeError, ValueError):
                            st.warning('The reranker is unavailable; showing hybrid-search results.')
                            results = results[:top_k]
                    results = [dict(result, evidence_id=f'E{i}') for i, result in enumerate(results, 1)]
                with st.spinner('Preparing an evidence-grounded response…'):
                    if mode == 'Source excerpts':
                        answer = source_excerpt_answer(results)
                    else:
                        try:
                            if CHAT_MODEL_ID:
                                answer = generate_grounded_answer(question, results, CHAT_MODEL_ID, AWS_REGION)
                            else:
                                answer = generate_local_answer(question, results, LOCAL_CHAT_MODEL_ID)
                        except GenerationError:
                            answer = source_excerpt_answer(results, 'The answer model is unavailable. The retrieved evidence is still available.')
                st.markdown(answer)
                message_number = len(st.session_state.messages)
                if results:
                    show_financial_visualization(
                        question,
                        results,
                        f'current-chart-{message_number}',
                    )
                    show_sources(results, message_number)
                    st.session_state.active_evidence = results[0]
                else:
                    st.session_state.pop('active_evidence', None)
                st.session_state.messages.append({
                    'role': 'assistant',
                    'content': answer,
                    'evidence': results,
                    'question': question,
                })
            except (ImportError, StorageError, ValueError, RuntimeError, OSError):
                error_message = 'Search could not complete. Check the embedding model installation and index, then try again.'
                st.error(error_message)
                st.session_state.messages.append({'role': 'assistant', 'content': error_message})

with reference:
    st.subheader('Original PDF reference')
    active = st.session_state.get('active_evidence')
    if not active:
        st.info('Ask a question, then open a source card to inspect the original PDF page.')
    else:
        st.caption(f"{active['evidence_id']} · {active.get('source_file')} · PDF page {active.get('page_number')}")
        # Load the original only on explicit request to avoid downloading large
        # reports for every chat turn. Changing the selected source clears preview.
        preview_key = f"{selected.key}:{active.get('page_number')}:{active.get('paragraph_id', active.get('chunk_id'))}"
        if st.button('Show original page', key='show-page'):
            st.session_state.pdf_preview_key = preview_key
        if st.session_state.get('pdf_preview_key') == preview_key:
            try:
                raw_key = metadata.get('storage', {}).get('raw_s3_key')
                if not raw_key:
                    base = selected.key.rsplit('/vector-store/', 1)[0]
                    source = metadata.get('source_file')
                    if not source or '/vector-store/' not in selected.key:
                        raise ValueError('The original PDF location is missing. Re-upload and reindex this report.')
                    raw_key = base + '/raw/' + PurePosixPath(source).name
                with st.spinner('Opening the cited PDF page…'):
                    pdf_bytes = load_pdf(S3_BUCKET, AWS_REGION, S3_PREFIX, raw_key)
                    boxes = [active['bbox']] if active.get('bbox') else []
                    png = render_evidence_page(pdf_bytes, int(active['page_number']), boxes, active.get('pdf_sha256'))
                st.image(png, width='stretch')
                st.caption('Highlighted area is the retrieved source block, not a verification of the generated answer.'
                           if boxes else 'This older index has no highlight coordinates.')
                if not active.get('pdf_sha256'):
                    st.warning('Legacy source: PDF identity cannot be verified. Reprocess and rebuild before relying on it.')
                st.download_button('Download original report', pdf_bytes,
                                   file_name=PurePosixPath(active.get('source_file', 'report.pdf')).name,
                                   mime='application/pdf')
            except StorageError:
                st.warning('The original PDF is unavailable. Check its S3 location/access or upload it again. Text evidence remains available.')
            except (ValueError, RuntimeError, OSError) as error:
                st.warning(str(error))
        st.caption('For complex tables or columns, use the original page. Text extraction does not reconstruct table cells.')

st.caption('Research aid, not verified financial advice. Citation/number checks do not establish that a claim is supported.')
