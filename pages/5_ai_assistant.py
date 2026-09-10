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
from backend.rag_service import (INSUFFICIENT, GenerationError,
                                 generate_grounded_answer, generate_local_answer,
                                 source_excerpt_answer)
from backend.research_planning_service import (
    WEB_AUTO,
    WEB_ALWAYS,
    WEB_MODES,
    WEB_OFF,
    document_scope_answer,
    plan_research,
)
from backend.retrieval_service import KeywordIndex, fuse_results, rerank_results
from backend.storage_service import S3Storage, StorageError
from backend.ui import apply_style, hero, readable_report_label
from backend.web_research_service import WebResearchError, search_current_web
from config import (
    AWS_REGION,
    CHAT_MODEL_ID,
    LOCAL_CHAT_MODEL_ID,
    S3_BUCKET,
    S3_PREFIX,
    WEB_SEARCH_ENABLED,
    WEB_SEARCH_BACKEND,
    WEB_SEARCH_REGION,
    WEB_SEARCH_TIMEOUT_SECONDS,
)

st.set_page_config(page_title='FinSight | Report assistant', page_icon='💬', layout='wide')
apply_style()
hero('Ask the filing. Trace the answer.',
     'One focused answer, its original PDF evidence, and current web context when the question looks forward.')

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
    available_web_modes = list(WEB_MODES) if WEB_SEARCH_ENABLED else [WEB_OFF]
    web_mode = st.selectbox(
        'Current web research',
        available_web_modes,
        index=available_web_modes.index(WEB_ALWAYS) if WEB_ALWAYS in available_web_modes else 0,
        help=(
            'Automatic mode adds a separate live-web section only for current, '
            'future, investment, plan, outlook, or post-report-year questions.'
        ),
    )
    if not WEB_SEARCH_ENABLED:
        st.caption('Live web research is disabled by configuration.')
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


def _raw_pdf_key():
    raw_key = metadata.get('storage', {}).get('raw_s3_key')
    if raw_key:
        return raw_key
    base = selected.key.rsplit('/vector-store/', 1)[0]
    source = metadata.get('source_file')
    if not source or '/vector-store/' not in selected.key:
        raise ValueError('The original PDF location is missing. Re-upload and reindex this report.')
    return base + '/raw/' + PurePosixPath(source).name


def show_sources(results, message_number):
    """Show an original cited PDF page only after an explicit click."""
    if not results:
        return
    visible_key = f'evidence-visible-{message_number}'
    label = 'Hide PDF evidence' if st.session_state.get(visible_key) else 'View PDF evidence'
    if st.button(label, key=f'toggle-evidence-{message_number}', icon='📄'):
        st.session_state[visible_key] = not st.session_state.get(visible_key, False)
    if not st.session_state.get(visible_key):
        return

    selector_key = f'selected-source-{message_number}'
    available_ids = [result['evidence_id'] for result in results]
    if st.session_state.get(selector_key) not in available_ids:
        st.session_state[selector_key] = available_ids[0]
    source_columns = st.columns(min(len(results), 5))
    for position, result in enumerate(results):
        evidence_id = result['evidence_id']
        page = result.get('page_number', '?')
        if source_columns[position % len(source_columns)].button(
            f'{evidence_id} · Page {page}',
            key=f'pick-source-{message_number}-{evidence_id}',
            type='primary' if st.session_state[selector_key] == evidence_id else 'secondary',
            width='stretch',
        ):
            st.session_state[selector_key] = evidence_id

    active = next(result for result in results
                  if result['evidence_id'] == st.session_state[selector_key])
    try:
        with st.spinner('Opening cited PDF page…'):
            pdf_bytes = load_pdf(S3_BUCKET, AWS_REGION, S3_PREFIX, _raw_pdf_key())
            boxes = [active['bbox']] if active.get('bbox') else []
            png = render_evidence_page(
                pdf_bytes, int(active['page_number']), boxes, active.get('pdf_sha256')
            )
        st.image(
            png,
            caption=f"{active.get('source_file', 'Report')} · PDF page {active.get('page_number')}",
            width='stretch',
        )
    except StorageError:
        st.warning('The original PDF is unavailable. Check its S3 location or upload it again.')
    except (ValueError, RuntimeError, OSError) as error:
        st.warning(str(error))


def show_financial_visualization(question, results, chart_key):
    """Render only evidence-grounded charts containing comparable values."""
    if not results:
        return

    try:
        spec = build_visualization_spec(question, results)
    except (TypeError, ValueError):
        spec = None

    if spec is None:
        # A standalone regex match is too ambiguous for a financial card: PDF
        # prose also contains page, note, section, date, and legal-reference
        # numbers.  Comparable series are rendered only after validation.
        return

    with st.expander('View financial chart', expanded=False):
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


def show_web_research(web_research, message_number, web_error=None):
    """Render web material in its own namespace and source section."""
    st.markdown('#### Latest web answer')
    if web_error:
        st.warning(web_error)
        return
    if not web_research:
        st.info('No web research result is available for this response.')
        return

    st.write(web_research.get('answer', ''))
    sources = web_research.get('sources', [])
    if not sources:
        return

    domains = list(dict.fromkeys(source.get('domain', '') for source in sources if source.get('domain')))
    if domains:
        st.caption('Sources: ' + ' · '.join(domains))
    visible_key = f'web-sources-visible-{message_number}'
    label = 'Hide website sources' if st.session_state.get(visible_key) else 'View website sources'
    if st.button(label, key=f'toggle-web-sources-{message_number}', icon='🔗'):
        st.session_state[visible_key] = not st.session_state.get(visible_key, False)
    if st.session_state.get(visible_key):
        for source in sources:
            st.link_button(
                f"{source.get('evidence_id', 'W?')} · {source.get('title') or source.get('domain') or 'Open source'}",
                source['url'],
                width='stretch',
            )


def show_assistant_response(message, message_number):
    """Keep report and web answers visibly separate on current and historic turns."""
    st.markdown('#### Report answer')
    st.markdown(message['content'])
    if message.get('evidence') and message.get('question'):
        show_financial_visualization(
            message['question'],
            message['evidence'],
            f'history-chart-{message_number}',
        )
    if message.get('evidence'):
        show_sources(message['evidence'], message_number)
    if message.get('web_research') or message.get('web_error'):
        show_web_research(message.get('web_research'), message_number, message.get('web_error'))


def show_message(message, position):
    avatar = '👤' if message['role'] == 'user' else '🤖'
    with st.chat_message(message['role'], avatar=avatar):
        if message['role'] == 'assistant':
            show_assistant_response(message, position)
        else:
            st.markdown(message['content'])


conversation = st.container()
with conversation:
    st.subheader('Ask about this company')
    question = st.chat_input(
        'Ask a report, growth, investment or future outlook question…',
        key='manual-report-question',
    )

    suggested = None
    if not st.session_state.messages:
        st.write('Or start with one of these suggested questions:')
        company_name = metadata.get('company') or 'the company'
        report_year = metadata.get('financial_year') or 'the report year'
        samples = [
            f'What was {company_name}\'s net profit in FY {report_year}?',
            f'Where is {company_name} investing for future growth?',
            f'How could {company_name} grow over the next three years?',
            f'What are {company_name}\'s biggest future opportunities and risks?',
        ]
        for sample in samples:
            if st.button(sample, key=sample, width='stretch'):
                suggested = sample
    question = question or suggested
    existing_messages = st.session_state.messages
    # While a new answer is being prepared, every older exchange belongs in
    # collapsed history. Otherwise keep only the most recent exchange visible.
    history_messages = existing_messages if question else existing_messages[:-2]
    latest_messages = [] if question else existing_messages[-2:]
    if history_messages:
        previous_count = sum(message['role'] == 'user' for message in history_messages)
        with st.expander(f'Previous questions · {previous_count}', expanded=False):
            for n, message in enumerate(history_messages):
                show_message(message, n)
    for n, message in enumerate(latest_messages, start=len(history_messages)):
        show_message(message, n)

    if question:
        st.session_state.messages.append({'role': 'user', 'content': question})
        with st.chat_message('user', avatar='👤'):
            st.markdown(question)
        with st.chat_message('assistant', avatar='🤖'):
            try:
                research_plan = plan_research(
                    question,
                    metadata.get('financial_year'),
                    web_mode,
                )
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
                    scope_answer = document_scope_answer(
                        research_plan,
                        metadata.get('financial_year'),
                        INSUFFICIENT,
                    )
                    if scope_answer:
                        answer = scope_answer
                    elif mode == 'Source excerpts':
                        answer = source_excerpt_answer(results)
                    else:
                        try:
                            if CHAT_MODEL_ID:
                                answer = generate_grounded_answer(question, results, CHAT_MODEL_ID, AWS_REGION)
                            else:
                                answer = generate_local_answer(question, results, LOCAL_CHAT_MODEL_ID)
                        except GenerationError:
                            answer = source_excerpt_answer(results, 'The answer model is unavailable. The retrieved evidence is still available.')

                web_research = None
                web_error = None
                if research_plan.include_web:
                    try:
                        with st.spinner('Searching current web sources separately…'):
                            web_research = search_current_web(
                                metadata.get('company') or 'selected company',
                                question,
                                region=WEB_SEARCH_REGION,
                                timeout=WEB_SEARCH_TIMEOUT_SECONDS,
                                backend=WEB_SEARCH_BACKEND,
                            ).to_dict()
                    except WebResearchError as error:
                        web_error = str(error)

                message_number = len(st.session_state.messages)
                response_message = {
                    'role': 'assistant',
                    'content': answer,
                    'evidence': results,
                    'question': question,
                    'research_plan': research_plan.to_dict(),
                    'web_research': web_research,
                    'web_error': web_error,
                }
                show_assistant_response(response_message, message_number)
                st.session_state.messages.append(response_message)
            except (ImportError, StorageError, ValueError, RuntimeError, OSError):
                error_message = 'Search could not complete. Check the embedding model installation and index, then try again.'
                st.error(error_message)
                st.session_state.messages.append({'role': 'assistant', 'content': error_message})

st.caption('Research aid—not financial advice. Verify important figures against the linked report or website.')
