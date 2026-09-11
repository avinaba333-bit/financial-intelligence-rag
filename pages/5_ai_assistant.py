from pathlib import PurePosixPath
import streamlit as st

from backend.embedding_service import DEFAULT_MODEL, deserialize_faiss_index, search_faiss_index
from backend.financial_visualization_service import (
    build_visualization_spec,
    create_plotly_figure,
    extract_financial_data,
    visualization_rows,
)
from backend.multi_document_service import merge_report_results, selected_report_scope
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
from backend.ui import (apply_style, hero, readable_report_label,
                        show_excerpt, sidebar_report_card)
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
apply_style('assistant')
hero('Ask the filing. Trace the answer.',
     'One focused answer, its original PDF evidence, and current web context when the question looks forward.')

if not S3_BUCKET:
    st.info('Configure S3_BUCKET, upload a report, and build its vector index to start chatting.')
    st.page_link('pages/1_upload_reports.py', label='Upload financial reports', icon='📄')
    st.stop()


@st.cache_resource(show_spinner=False, ttl=300, max_entries=12)
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
    raw_pdf_key = metadata.get('storage', {}).get('raw_s3_key')
    chunks = [
        dict(
            chunk,
            company=chunk.get('company') or metadata.get('company'),
            financial_year=chunk.get('financial_year') or metadata.get('financial_year'),
            source_file=chunk.get('source_file') or metadata.get('source_file'),
            document_id=chunk.get('document_id') or metadata.get('document_id'),
            vector_metadata_key=metadata_key,
            raw_s3_key=raw_pdf_key,
        )
        for chunk in chunks
    ]
    return index, chunks, metadata, KeywordIndex(chunks)


@st.cache_data(show_spinner=False, ttl=300, max_entries=12)
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
    selected_reports = st.multiselect(
        'Annual reports',
        reports,
        default=reports[:1],
        format_func=readable_report_label,
        max_selections=5,
        help='Select one report for focused Q&A or several reports for company/year comparisons.',
    )
    if not selected_reports:
        st.info('Select at least one indexed annual report.')
        st.stop()
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

selected_vector_keys = tuple(report.key for report in selected_reports)
if st.session_state.get('selected_vector_keys') != selected_vector_keys:
    st.session_state.selected_vector_keys = selected_vector_keys
    clear_chat()
st.session_state.setdefault('messages', [])

try:
    loaded_reports = []
    for report in selected_reports:
        index, chunks, metadata, keyword_index = load_vector_store(
            S3_BUCKET, AWS_REGION, S3_PREFIX, report.key
        )
        loaded_reports.append({
            'document': report,
            'index': index,
            'chunks': chunks,
            'metadata': metadata,
            'keyword_index': keyword_index,
        })
except (StorageError, ValueError, RuntimeError):
    st.error('Unable to load one of the selected indexes. Check storage access and rebuild incompatible reports.')
    st.stop()

identity = tuple(
    (
        item['document'].key,
        item['metadata'].get('document_id'),
        item['index'].ntotal,
        item['metadata'].get('schema_version'),
    )
    for item in loaded_reports
)
if st.session_state.get('loaded_report_identity') != identity:
    clear_chat()
    st.session_state.loaded_report_identity = identity

metadata_items = [item['metadata'] for item in loaded_reports]
companies, financial_years = selected_report_scope(metadata_items)
company_scope = ' and '.join(companies) or 'selected companies'
year_scope = ' / '.join(financial_years)
total_passages = sum(item['index'].ntotal for item in loaded_reports)

if len(loaded_reports) == 1:
    active_report = loaded_reports[0]
    page_count = len({
        chunk.get('page_number') for chunk in active_report['chunks']
        if chunk.get('page_number')
    })
    sidebar_report_card(
        active_report['metadata'].get('company'),
        active_report['metadata'].get('financial_year'),
        active_report['metadata'].get('source_file'),
        page_count,
        active_report['index'].ntotal,
    )
else:
    st.sidebar.markdown('#### Selected report set')
    for item in loaded_reports:
        report_metadata = item['metadata']
        st.sidebar.caption(
            f"✓ {report_metadata.get('company') or 'Unknown company'} · "
            f"FY {report_metadata.get('financial_year') or 'unknown'} · "
            f"{item['index'].ntotal} passages"
        )

c1, c2, c3 = st.columns(3)
c1.metric('Selected reports', len(loaded_reports))
c2.metric('Companies', len(companies) or '—')
c3.metric('Searchable passages', total_passages)
if companies or financial_years:
    st.caption(
        f"Research scope: {', '.join(companies) or 'company not specified'} · "
        f"FY {', '.join(financial_years) or 'not specified'}"
    )
if any(item['metadata'].get('schema_version', 1) < 2 for item in loaded_reports):
    st.warning('Legacy index: excerpts may end mid-paragraph. Reprocess the PDF, regenerate chunks, '
               'and rebuild the index for complete source blocks and highlighting.')
st.caption('Citations use physical PDF pages; printed page labels may differ. Always verify figures against the original page.')


def _raw_pdf_key(evidence):
    raw_key = evidence.get('raw_s3_key')
    if raw_key:
        return raw_key
    metadata_key = evidence.get('vector_metadata_key', '')
    source = evidence.get('source_file')
    if not source or '/vector-store/' not in metadata_key:
        raise ValueError('The original PDF location is missing. Re-upload and reindex this report.')
    base = metadata_key.rsplit('/vector-store/', 1)[0]
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
        company = result.get('company') or 'Report'
        if source_columns[position % len(source_columns)].button(
            f'{evidence_id} · {company} · p.{page}',
            key=f'pick-source-{message_number}-{evidence_id}',
            type='primary' if st.session_state[selector_key] == evidence_id else 'secondary',
            width='stretch',
        ):
            st.session_state[selector_key] = evidence_id

    active = next(result for result in results
                  if result['evidence_id'] == st.session_state[selector_key])
    try:
        with st.spinner('Opening cited PDF page…'):
            pdf_bytes = load_pdf(S3_BUCKET, AWS_REGION, S3_PREFIX, _raw_pdf_key(active))
            boxes = [active['bbox']] if active.get('bbox') else []
            png = render_evidence_page(
                pdf_bytes, int(active['page_number']), boxes, active.get('pdf_sha256')
            )
        st.image(
            png,
            caption=(
                f"{active.get('company') or 'Company not specified'} · "
                f"FY {active.get('financial_year') or 'not specified'} · "
                f"{active.get('source_file', 'Report')} · PDF page {active.get('page_number')}"
            ),
            width='stretch',
        )
        score = active.get('rerank_score', active.get('retrieval_score'))
        if score is not None:
            st.caption(f'Relevance ranking score: {float(score):.4f} · use for ordering, not factual confidence.')
        st.markdown('**Complete supporting paragraph**')
        show_excerpt(
            active.get('context_text', active.get('paragraph_text', active.get('text', ''))),
            active.get('text', ''),
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
    st.subheader(
        'Ask across selected reports' if len(loaded_reports) > 1
        else 'Ask about this company'
    )
    question = st.chat_input(
        'Ask a report comparison, growth, investment or future outlook question…',
        key='manual-report-question',
    )

    suggested = None
    if not st.session_state.messages:
        st.write('Or start with one of these suggested questions:')
        if len(loaded_reports) > 1:
            samples = [
                'Compare the reported net profit across the selected reports. Cite every company and year.',
                'Compare revenue growth across the selected reports using only compatible figures.',
                'Summarise the main company-specific opportunities and risks in the selected reports.',
                'Which requested comparison is not supported by enough evidence in these reports?',
            ]
        else:
            active_metadata = loaded_reports[0]['metadata']
            company_name = active_metadata.get('company') or 'the company'
            report_year = active_metadata.get('financial_year') or 'the report year'
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
                    year_scope or None,
                    web_mode,
                )
                with st.spinner('Finding relevant passages…'):
                    report_results = []
                    for item in loaded_reports:
                        report_chunks = item['chunks']
                        candidates = min(max(top_k * 5, 25), len(report_chunks))
                        dense = search_faiss_index(
                            item['index'], report_chunks, question, max(candidates, 1)
                        )
                        lexical = item['keyword_index'].search(question, candidates)
                        report_results.append(
                            fuse_results(
                                report_chunks,
                                dense,
                                lexical,
                                candidates,
                                min_similarity,
                            )
                        )

                    candidate_limit = max(1, min(
                        max(top_k * 5, 25),
                        sum(len(results) for results in report_results),
                    ))
                    results = merge_report_results(
                        report_results,
                        candidate_limit if use_reranker else top_k,
                    )
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
                        year_scope or None,
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
                                company_scope,
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
