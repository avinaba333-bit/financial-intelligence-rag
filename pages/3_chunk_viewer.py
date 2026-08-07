import json
from pathlib import Path

import streamlit as st

from backend.chunk_service import (
    generate_and_save_chunks,
    generate_chunk_payload,
    save_chunk_payload,
)
from backend.storage_service import S3Storage, StorageError
from config import AWS_REGION, S3_BUCKET, S3_PREFIX


st.set_page_config(
    page_title="Chunk Viewer",
    page_icon="🧩",
    layout="wide",
)

st.title("Document Chunk Generator and Viewer")

st.write(
    """
    This page converts extracted annual-report text into overlapping,
    page-aware chunks for semantic search and RAG processing.
    """
)

processed_directory = Path("data/processed")

processed_files = sorted(
    processed_directory.rglob("*.json")
)

document_options = [
    {"kind": "local", "value": path, "label": f"Local: {path}"}
    for path in processed_files
]

if S3_BUCKET:
    try:
        storage = S3Storage(S3_BUCKET, AWS_REGION, S3_PREFIX)
        document_options.extend(
            {"kind": "s3", "value": item.key, "label": item.label}
            for item in storage.list_processed_documents()
        )
    except StorageError as error:
        st.warning(f"S3 documents are temporarily unavailable: {error}")

if not document_options:
    st.warning(
        "No processed JSON files were found. "
        "Upload and process a PDF first."
    )
    st.stop()

selected_option = st.selectbox(
    "Select processed financial report",
    options=document_options,
    format_func=lambda option: option["label"],
)

col1, col2 = st.columns(2)

with col1:
    chunk_size = st.number_input(
        "Chunk size",
        min_value=300,
        max_value=3000,
        value=1000,
        step=100,
    )

with col2:
    overlap = st.number_input(
        "Chunk overlap",
        min_value=0,
        max_value=500,
        value=200,
        step=50,
    )

if overlap >= chunk_size:
    st.error(
        "Chunk overlap must be smaller than chunk size."
    )
    st.stop()

if st.button(
    "Generate Chunks",
    type="primary",
):
    try:
        if selected_option["kind"] == "local":
            output_path, chunks = generate_and_save_chunks(
                processed_json_path=selected_option["value"],
                chunk_size=int(chunk_size),
                overlap=int(overlap),
            )
        else:
            document = storage.download_json(selected_option["value"])
            payload, chunks = generate_chunk_payload(
                document, int(chunk_size), int(overlap)
            )
            company = selected_option["value"].split("/")[-4]
            year = selected_option["value"].split("/")[-3]
            output_path = (
                Path("data/chunks") / company / year /
                f"{Path(document['source_file']).stem}_chunks.json"
            )
            save_chunk_payload(payload, output_path)
            chunk_key = storage.chunks_key(company, year, document["source_file"])
            storage.upload_json(payload, chunk_key)

        st.session_state["chunk_output_path"] = str(
            output_path
        )

        st.success(
            f"Generated {len(chunks)} chunks successfully."
        )

        st.write(
            f"Chunk file saved at: `{output_path}`"
        )

    except (OSError, ValueError, StorageError) as error:
        st.exception(error)

chunk_output_path = st.session_state.get(
    "chunk_output_path"
)

if chunk_output_path:
    chunk_file = Path(chunk_output_path)

    if chunk_file.exists():
        with chunk_file.open(
            "r",
            encoding="utf-8",
        ) as input_file:
            chunk_document = json.load(input_file)

        st.markdown("---")
        st.subheader("Chunk Summary")

        metric1, metric2, metric3 = st.columns(3)

        metric1.metric(
            "Total Chunks",
            chunk_document["total_chunks"],
        )

        metric2.metric(
            "Chunk Size",
            chunk_document["chunk_size"],
        )

        metric3.metric(
            "Overlap",
            chunk_document["overlap"],
        )

        chunks = chunk_document["chunks"]

        selected_chunk_id = st.selectbox(
            "Select chunk",
            options=[
                chunk["chunk_id"]
                for chunk in chunks
            ],
        )

        selected_chunk = next(
            chunk
            for chunk in chunks
            if chunk["chunk_id"] == selected_chunk_id
        )

        st.write(
            f"**Source:** {selected_chunk['source_file']}"
        )

        st.write(
            f"**Page:** {selected_chunk['page_number']}"
        )

        st.write(
            f"**Characters:** "
            f"{selected_chunk['character_count']}"
        )

        st.text_area(
            "Chunk content",
            value=selected_chunk["text"],
            height=400,
            disabled=True,
        )
