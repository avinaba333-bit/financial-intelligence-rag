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
