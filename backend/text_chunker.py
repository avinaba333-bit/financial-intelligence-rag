from typing import Any


def chunk_document(
    pages: list[dict[str, Any]],
    chunk_size: int = 1000,
    overlap: int = 200,
) -> list[dict[str, Any]]:
    """
    Split page-wise financial-report text into overlapping chunks.

    Each chunk retains its source page and filename.
    """

    if chunk_size <= 0:
        raise ValueError("chunk_size must be greater than zero.")

    if overlap < 0:
        raise ValueError("overlap cannot be negative.")

    if overlap >= chunk_size:
        raise ValueError("overlap must be smaller than chunk_size.")

    chunks: list[dict[str, Any]] = []
    chunk_id = 1

    for page in pages:
        text = page.get("text", "").strip()

        if not text:
            continue

        start = 0

        while start < len(text):
            end = min(start + chunk_size, len(text))
            chunk_text = text[start:end].strip()

            if chunk_text:
                chunks.append(
                    {
                        "chunk_id": chunk_id,
                        "page_number": page.get("page_number"),
                        "source_file": page.get(
                            "source_file",
                            "unknown.pdf",
                        ),
                        "text": chunk_text,
                        "character_count": len(chunk_text),
                    }
                )

                chunk_id += 1

            if end >= len(text):
                break

            start = end - overlap

    return chunks