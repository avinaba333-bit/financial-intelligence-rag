import json

import pandas as pd
import streamlit as st

from backend.embedding_service import deserialize_faiss_index, search_faiss_index
from backend.evaluation_service import evaluate_question, summarise_results
from backend.storage_service import S3Storage, StorageError
from config import AWS_REGION, S3_BUCKET, S3_PREFIX


st.set_page_config(
    page_title="FinSight RAG Evaluation",
    page_icon="📈",
    layout="wide",
)

st.title("RAG Evaluation")
st.write(
    "Measure retrieval precision, recall, ranking quality and latency using "
    "a labelled set of financial-report questions."
)

if not S3_BUCKET:
    st.error("S3_BUCKET is not configured.")
    st.stop()

storage = S3Storage(
    bucket=S3_BUCKET,
    region=AWS_REGION,
    prefix=S3_PREFIX,
)


@st.cache_resource(show_spinner=False)
def load_vector_store(metadata_key: str):
    metadata = storage.download_json(metadata_key)
    index_key = metadata.get("index_s3_key")

    if not index_key:
        raise ValueError("The vector metadata does not contain index_s3_key.")

    index = deserialize_faiss_index(storage.download_bytes(index_key))
    chunks = metadata.get("chunks", [])

    if index.ntotal != len(chunks):
        raise ValueError("FAISS index and metadata chunk counts do not match.")

    return index, chunks


try:
    vector_documents = storage.list_vector_metadata()
except StorageError as error:
    st.error(str(error))
    st.stop()

if not vector_documents:
    st.warning("No vector index was found. Build one on the Vector Index page first.")
    st.stop()

selected_document = st.selectbox(
    "Select an indexed annual report",
    options=vector_documents,
    format_func=lambda item: item.label,
)

top_k = st.slider("Retrieved chunks (k)", min_value=1, max_value=10, value=5)

st.markdown("#### Benchmark format")
st.code(
    '[\n  {"question": "What was net profit?", "expected_pages": [42]}\n]',
    language="json",
)

benchmark_file = st.file_uploader(
    "Upload a labelled benchmark JSON file",
    type=["json"],
)

if benchmark_file and st.button("Run Evaluation", type="primary"):
    try:
        benchmark = json.load(benchmark_file)
        if not isinstance(benchmark, list) or not benchmark:
            raise ValueError("The benchmark must be a non-empty JSON list.")

        for position, item in enumerate(benchmark, start=1):
            if not isinstance(item, dict):
                raise ValueError(f"Benchmark item {position} must be an object.")
            if not str(item.get("question", "")).strip():
                raise ValueError(f"Benchmark item {position} has no question.")
            if not isinstance(item.get("expected_pages"), list):
                raise ValueError(
                    f"Benchmark item {position} must contain expected_pages as a list."
                )

        index, chunks = load_vector_store(selected_document.key)

        def retrieve(question: str):
            return search_faiss_index(
                index=index,
                chunks=chunks,
                question=question,
                top_k=top_k,
            )

        with st.spinner("Evaluating benchmark questions..."):
            results = [
                evaluate_question(
                    question=item["question"].strip(),
                    expected_pages=item["expected_pages"],
                    retrieve=retrieve,
                )
                for item in benchmark
            ]

        summary = summarise_results(results)
        columns = st.columns(5)
        columns[0].metric("Questions", summary["questions"])
        columns[1].metric(
            f"Precision@{top_k}",
            f'{summary["mean_precision_at_k"]:.1%}',
        )
        columns[2].metric(
            f"Recall@{top_k}",
            f'{summary["mean_recall_at_k"]:.1%}',
        )
        columns[3].metric(
            "Mean reciprocal rank",
            f'{summary["mean_reciprocal_rank"]:.3f}',
        )
        columns[4].metric(
            "Mean latency",
            f'{summary["mean_latency_ms"]:.0f} ms',
        )

        result_rows = [result.to_dict() for result in results]
        st.dataframe(pd.DataFrame(result_rows), use_container_width=True)

        payload = {
            "vector_metadata_key": selected_document.key,
            "top_k": top_k,
            "summary": summary,
            "results": result_rows,
        }
        st.download_button(
            "Download Evaluation Results",
            data=json.dumps(payload, indent=2),
            file_name="rag_evaluation_results.json",
            mime="application/json",
        )
    except (json.JSONDecodeError, StorageError, ValueError, RuntimeError) as error:
        st.error(str(error))
