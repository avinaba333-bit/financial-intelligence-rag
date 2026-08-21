import streamlit as st

from backend.embedding_service import (
    deserialize_faiss_index,
    search_faiss_index,
)
from backend.rag_service import (
    GenerationError,
    generate_grounded_answer,
    generate_local_answer,
)
from backend.storage_service import S3Storage, StorageError
from config import (
    AWS_REGION,
    CHAT_MODEL_ID,
    LOCAL_CHAT_MODEL_ID,
    S3_BUCKET,
    S3_PREFIX,
)


st.set_page_config(
    page_title="FinSight RAG Assistant",
    page_icon="💬",
    layout="wide",
)

st.title("FinSight RAG Assistant")
st.write(
    "Ask questions about a selected annual report and receive answers "
    "grounded in retrieved evidence with page citations."
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
        raise ValueError(
            "FAISS index and metadata chunk counts do not match. "
            "Please rebuild the vector index."
        )

    return index, chunks, metadata


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

top_k = st.slider(
    "Evidence chunks to retrieve",
    min_value=3,
    max_value=10,
    value=5,
)

if st.session_state.get("selected_vector_key") != selected_document.key:
    st.session_state.selected_vector_key = selected_document.key
    st.session_state.messages = []

if "messages" not in st.session_state:
    st.session_state.messages = []

try:
    index, chunks, metadata = load_vector_store(selected_document.key)
except (StorageError, ValueError, RuntimeError) as error:
    st.error(str(error))
    st.stop()

caption_parts = [
    str(metadata.get("company") or "Unknown company"),
    str(metadata.get("financial_year") or "Unknown year"),
    f"{index.ntotal} indexed chunks",
]
st.caption(" • ".join(caption_parts))

if CHAT_MODEL_ID:
    st.info(f"Generation mode: Amazon Bedrock (`{CHAT_MODEL_ID}`)")
else:
    st.info(
        f"Generation mode: Local CPU model (`{LOCAL_CHAT_MODEL_ID}`). "
        "The first answer may take longer while the model is downloaded."
    )

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if message.get("evidence"):
            with st.expander("View retrieved evidence"):
                for result in message["evidence"]:
                    st.markdown(
                        f"**Page {result.get('page_number', 'unknown')} · "
                        f"Similarity {result.get('similarity_score', 0):.3f}**"
                    )
                    st.write(result.get("text", ""))

question = st.chat_input("Ask a question about this financial report")

if question:
    st.session_state.messages.append(
        {"role": "user", "content": question}
    )

    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        try:
            with st.spinner("Retrieving evidence and generating the answer..."):
                results = search_faiss_index(
                    index=index,
                    chunks=chunks,
                    question=question,
                    top_k=top_k,
                )
                if CHAT_MODEL_ID:
                    answer = generate_grounded_answer(
                        question=question,
                        results=results,
                        model_id=CHAT_MODEL_ID,
                        region=AWS_REGION,
                    )
                else:
                    answer = generate_local_answer(
                        question=question,
                        results=results,
                        model_id=LOCAL_CHAT_MODEL_ID,
                    )

            st.markdown(answer)

            with st.expander("View retrieved evidence"):
                for result in results:
                    st.markdown(
                        f"**Page {result.get('page_number', 'unknown')} · "
                        f"Similarity {result.get('similarity_score', 0):.3f}**"
                    )
                    st.write(result.get("text", ""))

            st.session_state.messages.append(
                {
                    "role": "assistant",
                    "content": answer,
                    "evidence": results,
                }
            )
        except (GenerationError, StorageError, ValueError, RuntimeError) as error:
            st.error(str(error))
