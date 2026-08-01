from typing import List, Dict


def chunk_document(
    pages: List[Dict],
    chunk_size: int = 800,
    overlap: int = 100,
):
    """
    Split page text into overlapping chunks.
    """

    chunks = []

    for page in pages:

        text = page["text"].strip()

        if not text:
            continue

        start = 0

        while start < len(text):

            end = start + chunk_size

            chunk = text[start:end]

            chunks.append(
                {
                    "page_number": page["page_number"],
                    "text": chunk,
                    "source_file": page["source_file"],
                }
            )

            start += chunk_size - overlap

    return chunks