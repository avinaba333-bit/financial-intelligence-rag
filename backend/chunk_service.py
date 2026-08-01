import json
from pathlib import Path
from typing import Any

from backend.text_chunker import chunk_document


def load_processed_document(
    json_path: Path,
) -> dict[str, Any]:
    if not json_path.exists():
        raise FileNotFoundError(
            f"Processed document not found: {json_path}"
        )

    with json_path.open(
        "r",
        encoding="utf-8",
    ) as input_file:
        return json.load(input_file)


def generate_and_save_chunks(
    processed_json_path: Path,
    chunk_size: int = 1000,
    overlap: int = 200,
) -> tuple[Path, list[dict[str, Any]]]:
    document = load_processed_document(
        processed_json_path
    )

    pages = document.get("pages", [])

    if not pages:
        raise ValueError(
            "The processed document does not contain pages."
        )

    chunks = chunk_document(
        pages=pages,
        chunk_size=chunk_size,
        overlap=overlap,
    )

    relative_path = processed_json_path.relative_to(
        Path("data/processed")
    )

    output_directory = (
        Path("data/chunks")
        / relative_path.parent
    )

    output_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_path = (
        output_directory
        / f"{processed_json_path.stem}_chunks.json"
    )

    output_data = {
        "company": document.get("company"),
        "financial_year": document.get("financial_year"),
        "source_file": document.get("source_file"),
        "chunk_size": chunk_size,
        "overlap": overlap,
        "total_chunks": len(chunks),
        "chunks": chunks,
    }

    with output_path.open(
        "w",
        encoding="utf-8",
    ) as output_file:
        json.dump(
            output_data,
            output_file,
            ensure_ascii=False,
            indent=2,
        )

    return output_path, chunks