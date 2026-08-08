import streamlit as st

from backend.embedding_service import (
    DEFAULT_MODEL,
    build_faiss_index,
    serialize_faiss_index,
)
from backend.storage_service import S3Storage, StorageError
from config import AWS_REGION, S3_BUCKET, S3_PREFIX


st.set_page_config(
    page_title="Vector Index Builder",
    page_icon="🔎",
    layout="wide",
)

st.title("Financial Report Vector Index Builder")

st.write(
    """
    Generate semantic embeddings from document chunks and create a
    FAISS vector index for retrieval-augmented generation.
    """
)

if not S3_BUCKET:
    st.error("S3_BUCKET is not configured.")
    st.stop()

storage = S3Storage(
    bucket=S3_BUCKET,
    region=AWS_REGION,
    prefix=S3_PREFIX,
)

try:
    chunk_documents = storage.list_chunk_documents()
except StorageError as error:
    st.error(str(error))
    st.stop()

if not chunk_documents:
    st.warning(
        "No S3 chunk files were found. Generate chunks first."
    )
    st.stop()

selected_document = st.selectbox(
    "Select an S3 chunk document",
    options=chunk_documents,
    format_func=lambda item: item.label,
)

st.info(
    f"Embedding model: `{DEFAULT_MODEL}` — "
    "384-dimensional normalized vectors"
)

if st.button(
    "Build FAISS Vector Index",
    type="primary",
):
    try:
        with st.spinner(
            "Generating embeddings and building the FAISS index..."
        ):
            chunk_payload = storage.download_json(
                selected_document.key
            )

            chunks = chunk_payload.get("chunks", [])

            index, indexed_chunks = build_faiss_index(chunks)

            key_parts = selected_document.key.split("/")

            company = key_parts[-4]
            financial_year = key_parts[-3]
            chunk_filename = key_parts[-1]

            index_key = storage.vector_index_key(
                company,
                financial_year,
                chunk_filename,
            )

            metadata_key = storage.vector_metadata_key(
                company,
                financial_year,
                chunk_filename,
            )

            index_bytes = serialize_faiss_index(index)

            metadata = {
                "company": chunk_payload.get("company"),
                "financial_year": chunk_payload.get(
                    "financial_year"
                ),
                "source_file": chunk_payload.get("source_file"),
                "source_chunk_key": selected_document.key,
                "embedding_model": DEFAULT_MODEL,
                "embedding_dimension": index.d,
                "total_vectors": index.ntotal,
                "index_s3_key": index_key,
                "chunks": indexed_chunks,
            }

            index_uri = storage.upload_bytes(
                index_bytes,
                index_key,
                "application/octet-stream",
            )

            metadata_uri = storage.upload_json(
                metadata,
                metadata_key,
            )

        st.success(
            f"Created an index containing "
            f"{index.ntotal} vectors."
        )

        metric1, metric2 = st.columns(2)

        metric1.metric(
            "Indexed chunks",
            index.ntotal,
        )

        metric2.metric(
            "Vector dimensions",
            index.d,
        )

        st.write(f"FAISS index: `{index_uri}`")
        st.write(f"Metadata: `{metadata_uri}`")

    except (StorageError, ValueError, RuntimeError) as error:
        st.exception(error)