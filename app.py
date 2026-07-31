import streamlit as st


st.set_page_config(
    page_title="Financial Intelligence Platform",
    page_icon="📊",
    layout="wide",
)

st.title("AI-Powered Financial Intelligence Platform")

st.write(
    """
    This M.Tech project analyzes annual financial reports using
    Retrieval-Augmented Generation, financial analytics and AWS services.
    """
)

st.success("Application setup completed successfully.")

st.markdown("---")

st.header("Project Modules")

col1, col2, col3 = st.columns(3)

with col1:
    st.subheader("Document Processing")
    st.write("Upload and process annual financial reports.")

with col2:
    st.subheader("AI Assistant")
    st.write("Ask questions and receive answers with source pages.")

with col3:
    st.subheader("Financial Analytics")
    st.write("Analyze KPIs, ratios, risks and company performance.")

st.markdown("---")

st.subheader("Planned Capabilities")

st.write(
    """
    - Multi-document annual-report analysis
    - Financial KPI extraction
    - Revenue and profit trend visualization
    - Company and year comparison
    - Business-segment profit/loss analysis
    - Risk analysis
    - Evidence-based answers with page citations
    """
)