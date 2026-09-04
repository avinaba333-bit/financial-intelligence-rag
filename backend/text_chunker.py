"""Small search windows linked to complete, unmodified source blocks."""
import re
from typing import Any


def _windows(text: str, limit: int, overlap: int):
    start = 0
    while start < len(text):
        end = min(start + limit, len(text))
        if end < len(text):
            boundaries = list(re.finditer(r"(?<=[.!?])\s+|\n", text[start:end]))
            if boundaries and boundaries[-1].start() > limit // 3:
                end = start + boundaries[-1].start()
            else:
                boundary = text.rfind(" ", start + 1, end)
                if boundary > start:
                    end = boundary
                else:
                    # Keep a long token intact rather than break a financial figure.
                    boundary = re.search(r"\s", text[end:])
                    end = end + boundary.start() if boundary else len(text)
        yield start, end, text[start:end].strip()
        if end == len(text):
            break
        next_start = max(start + 1, end - overlap)
        while next_start < end and not text[next_start - 1].isspace():
            next_start += 1
        start = next_start
        while start < len(text) and text[start].isspace():
            start += 1


def chunk_document(pages: list[dict[str, Any]], chunk_size: int = 1000,
                   overlap: int = 200) -> list[dict[str, Any]]:
    if chunk_size <= 0 or overlap < 0 or overlap >= chunk_size:
        raise ValueError("Require chunk_size > 0 and 0 <= overlap < chunk_size.")
    chunks = []
    for page in pages:
        paragraphs = page.get("paragraphs") or [
            {"paragraph_id": f"p{page.get('page_number')}-legacy-{i}", "text": text}
            for i, text in enumerate(re.split(r"\n\s*\n", page.get("text", "")))
            if text.strip()
        ]
        for paragraph in paragraphs:
            parent = paragraph.get("text", "").strip()
            if not parent:
                continue
            for start, end, text in _windows(parent, chunk_size, overlap):
                if not text:
                    continue
                chunks.append({
                    "chunk_id": len(chunks) + 1,
                    "page_number": page.get("page_number"),
                    "page_label": page.get("page_label"),
                    "source_file": page.get("source_file", "unknown.pdf"),
                    "text": text, "character_count": len(text),
                    "paragraph_id": paragraph["paragraph_id"],
                    "paragraph_text": parent,
                    "bbox": paragraph.get("bbox"),
                    "start_offset": start, "end_offset": end,
                    "pdf_sha256": page.get("pdf_sha256"),
                    "extraction_version": page.get("extraction_version", 1),
                })
    return chunks
