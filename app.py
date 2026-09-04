import streamlit as st

from backend.ui import apply_style, hero


st.set_page_config(
    page_title='FinSight | Financial research',
    page_icon='📊',
    layout='wide',
    initial_sidebar_state='expanded',
)


def home_page():
    apply_style()
    hero(
        'Financial research, with the evidence.',
        'Turn annual reports into searchable knowledge. Read the answer, '
        'inspect the source, and verify the original page.',
    )

    st.page_link(
        'pages/5_ai_assistant.py',
        label='Open report assistant',
        icon='💬',
    )

    st.subheader('From annual report to cited answer')
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


pages = {
    'Overview': [
        st.Page(
            home_page,
            title='Home',
            icon='🏠',
            default=True,
        ),
    ],
    'Document workspace': [
        st.Page(
            'pages/1_upload_reports.py',
            title='Upload reports',
            icon='📤',
        ),
        st.Page(
            'pages/2_document_summary.py',
            title='Document summary',
            icon='📑',
        ),
        st.Page(
            'pages/3_chunk_viewer.py',
            title='Chunk viewer',
            icon='🧩',
        ),
        st.Page(
            'pages/4_vector_index.py',
            title='Vector index',
            icon='🔍',
        ),
    ],
    'Financial research': [
        st.Page(
            'pages/5_ai_assistant.py',
            title='AI assistant',
            icon='💬',
        ),
        st.Page(
            'pages/6_rag_evaluation.py',
            title='RAG evaluation',
            icon='📊',
        ),
    ],
}

navigation = st.navigation(pages, position='sidebar', expanded=True)
navigation.run()
