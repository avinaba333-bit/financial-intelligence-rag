from pathlib import Path
from typing import Any
import hashlib

import pymupdf


def extract_pdf_pages(pdf_path: str) -> list[dict[str, Any]]:
    """
    Extract page-wise text from a PDF.

    Args:
        pdf_path: Local path of the PDF file.

    Returns:
        A list containing page number, text and source filename.
    """

    path = Path(pdf_path)

    if not path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    if path.suffix.lower() != ".pdf":
        raise ValueError("Only PDF files are supported.")

    extracted_pages: list[dict[str, Any]] = []
    pdf_sha256 = hashlib.sha256(path.read_bytes()).hexdigest()

    with pymupdf.open(pdf_path) as document:
        for page_index, page in enumerate(document):
            # Layout blocks approximate paragraphs; the PDF page is authoritative.
            paragraphs = [
                {"paragraph_id": f"p{page_index + 1}-b{block[5]}",
                 "text": block[4].strip(), "bbox": list(block[:4])}
                for block in page.get_text("blocks", sort=True)
                if block[6] == 0 and block[4].strip()
            ]
            text = "\n\n".join(block["text"] for block in paragraphs)

            extracted_pages.append(
                {
                    "page_number": page_index + 1,
                    "source_file": path.name,
                    "text": text,
                    "paragraphs": paragraphs,
                    "page_label": page.get_label() or str(page_index + 1),
                    "pdf_sha256": pdf_sha256,
                    "extraction_version": 2,
                }
            )

    return extracted_pages


def render_evidence_page(pdf_bytes: bytes, page_number: int,
                         boxes: list[list[float]] | None = None,
                         expected_sha256: str | None = None) -> bytes:
    """Render one physical PDF page; never modify the stored original."""
    if expected_sha256 and hashlib.sha256(pdf_bytes).hexdigest() != expected_sha256:
        raise ValueError("The PDF has changed since indexing. Reprocess and rebuild the index.")
    with pymupdf.open(stream=pdf_bytes, filetype="pdf") as document:
        if not 1 <= page_number <= len(document):
            raise ValueError("The cited page is outside this PDF.")
        page = document[page_number - 1]
        for box in boxes or []:
            rectangle = pymupdf.Rect(box) & page.rect
            if not rectangle.is_empty and not rectangle.is_infinite:
                annotation = page.add_rect_annot(rectangle)
                annotation.set_colors(stroke=(0.05, 0.6, 0.5), fill=(1, 0.88, 0.3))
                annotation.set_opacity(0.2)
                annotation.update()
        scale = min(1.7, 1600 / max(page.rect.width, page.rect.height))
        return page.get_pixmap(matrix=pymupdf.Matrix(scale, scale), alpha=False).tobytes("png")
