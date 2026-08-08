from functools import lru_cache
from typing import Any

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer


DEFAULT_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


@lru_cache(maxsize=1)
def get_embedding_model(
    model_name: str = DEFAULT_MODEL,
) -> SentenceTransformer:
    return SentenceTransformer(model_name)


def build_faiss_index(
    chunks: list[dict[str, Any]],
) -> tuple[faiss.Index, list[dict[str, Any]]]:
    valid_chunks = [
        chunk
        for chunk in chunks
        if chunk.get("text", "").strip()
    ]

    if not valid_chunks:
        raise ValueError("No text chunks are available for embedding.")

    texts = [chunk["text"] for chunk in valid_chunks]

    model = get_embedding_model()

    embeddings = model.encode(
        texts,
        batch_size=32,
        show_progress_bar=True,
        normalize_embeddings=True,
        convert_to_numpy=True,
    ).astype(np.float32)

    index = faiss.IndexFlatIP(embeddings.shape[1])
    index.add(embeddings)

    return index, valid_chunks


def search_faiss_index(
    index: faiss.Index,
    chunks: list[dict[str, Any]],
    question: str,
    top_k: int = 5,
) -> list[dict[str, Any]]:
    if not question.strip():
        raise ValueError("Question cannot be empty.")

    model = get_embedding_model()

    query_embedding = model.encode(
        [question],
        normalize_embeddings=True,
        convert_to_numpy=True,
    ).astype(np.float32)

    scores, indices = index.search(
        query_embedding,
        min(top_k, index.ntotal),
    )

    results = []

    for score, index_position in zip(scores[0], indices[0]):
        if index_position < 0:
            continue

        result = dict(chunks[index_position])
        result["similarity_score"] = float(score)
        results.append(result)

    return results


def serialize_faiss_index(index: faiss.Index) -> bytes:
    return faiss.serialize_index(index).tobytes()


def deserialize_faiss_index(data: bytes) -> faiss.Index:
    array = np.frombuffer(data, dtype=np.uint8)
    return faiss.deserialize_index(array)