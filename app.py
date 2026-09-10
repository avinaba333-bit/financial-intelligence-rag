import streamlit as st

from backend.ui import apply_style, hero


st.set_page_config(
    page_title='FinSight | Financial research',
    page_icon='📊',
    layout='wide',
    initial_sidebar_state='expanded',
)


def home_page():
    apply_style('home')
    hero(
        'Evidence before opinion.',
        'A financial research desk that turns annual reports into concise, '
        'source-linked answers you can verify.',
    )

    st.page_link(
        'pages/5_ai_assistant.py',
        label='Open report assistant',
        icon='💬',
    )

    st.subheader('Your research pipeline')
    for column, title, description, page in zip(
        st.columns(3),
        ['01 · Add reports', '02 · Prepare evidence', '03 · Ask & verify'],
        [
            'Upload PDFs with the company and financial year. Preserve the '
            'original document.',
            'Generate source-linked chunks and build a searchable vector index.',
            'Search the report, read complete source blocks, and inspect '
            'highlighted PDF pages.',
        ],
        [
            'pages/1_upload_reports.py',
            'pages/3_chunk_viewer.py',
            'pages/5_ai_assistant.py',
        ],
    ):
        with column, st.container(border=True):
            st.subheader(title)
            st.write(description)
            st.page_link(page, label='Open workspace →')

    st.divider()
    traceable, limits = st.columns(2)
    with traceable:
        st.subheader('Designed for traceable research')
        st.write(
            'Hybrid semantic and keyword search, source cards, original-page '
            'previews, and conservative citation and number checks on AI drafts.'
        )
    with limits:
        st.subheader('Know the limits')
        st.write(
            'The assistant searches one selected report at a time. Complex '
            'tables require visual verification. Automated KPI calculations '
            'and cross-report analytics are future work.'
        )

    st.caption(
        'FinSight · AI-Powered Financial Document Analysis using RAG · '
        'M.Tech project'
    )


home = st.Page(home_page, title='Home', icon=':material/home:', default=True)
upload = st.Page('pages/1_upload_reports.py', title='Upload reports', icon=':material/upload_file:')
summary = st.Page('pages/2_document_summary.py', title='Document summary', icon=':material/description:')
chunks = st.Page('pages/3_chunk_viewer.py', title='Chunk viewer', icon=':material/view_cozy:')
vectors = st.Page('pages/4_vector_index.py', title='Vector index', icon=':material/hub:')
assistant = st.Page('pages/5_ai_assistant.py', title='AI assistant', icon=':material/auto_awesome:')
evaluation = st.Page('pages/6_rag_evaluation.py', title='RAG evaluation', icon=':material/monitoring:')

pages = {
    'Overview': [
        home,
    ],
    'Document workspace': [
        upload, summary, chunks, vectors,
    ],
    'Financial research': [
        assistant, evaluation,
    ],
}

# The branded navigation is rendered by ``apply_style`` inside every selected
# page. Hiding Streamlit's built-in navigation prevents a second plain menu
# from appearing above it in production.
navigation = st.navigation(pages, position='hidden')
navigation.run()
