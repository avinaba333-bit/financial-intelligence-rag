from backend.storage_service import S3Storage


def test_s3_key_structure():
    storage = object.__new__(S3Storage)
    storage.prefix = "financial-reports"
    assert storage.raw_key("hdfc-bank", "2025-26", "report.pdf") == (
        "financial-reports/hdfc-bank/2025-26/raw/report.pdf"
    )
    assert storage.processed_key("hdfc-bank", "2025-26", "report.pdf") == (
        "financial-reports/hdfc-bank/2025-26/processed/report.json"
    )
    assert storage.chunks_key("hdfc-bank", "2025-26", "report.pdf") == (
        "financial-reports/hdfc-bank/2025-26/chunks/report_chunks.json"
    )


def test_list_index_sources_includes_processed_reports_without_chunks(monkeypatch):
    storage = object.__new__(S3Storage)
    storage.prefix = "financial-reports"
    processed = [
        storage.processed_key("vodafone-idea", "2025-26", "annual-report.pdf"),
        storage.processed_key("wipro", "2025-26", "annual-report.pdf"),
    ]
    chunks = [storage.chunks_key("wipro", "2025-26", "annual-report.pdf")]

    from backend.storage_service import S3Document

    monkeypatch.setattr(
        storage,
        "list_processed_documents",
        lambda: [S3Document(key, f"S3: {key}") for key in processed],
    )
    monkeypatch.setattr(
        storage,
        "list_chunk_documents",
        lambda: [S3Document(key, f"S3 chunks: {key}") for key in chunks],
    )

    sources = storage.list_index_sources()

    assert [source.key for source in sources] == sorted([processed[0], chunks[0]])
    assert "generated automatically" in sources[0].label
