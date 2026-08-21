from pathlib import Path
from typing import Any

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

    with pymupdf.open(pdf_path) as document:
        for page_index, page in enumerate(document):
            text = page.get_text("text").strip()

            extracted_pages.append(
                {
                    "page_number": page_index + 1,
                    "source_file": path.name,
                    "text": text,
                }
            )

    return extracted_pages
