import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError


class StorageError(RuntimeError):
    """Raised when an S3 operation cannot be completed."""


@dataclass(frozen=True)
class S3Document:
    key: str
    label: str


class S3Storage:
    def __init__(self, bucket: str, region: str, prefix: str = "financial-reports"):
        if not bucket.strip():
            raise ValueError("S3_BUCKET is not configured.")
        self.bucket = bucket.strip()
        self.prefix = prefix.strip("/")
        self.client = boto3.client("s3", region_name=region)

    def _key(self, *parts: str) -> str:
        clean_parts = [part.strip("/") for part in parts if part.strip("/")]
        return "/".join([self.prefix, *clean_parts])

    def raw_key(self, company: str, year: str, filename: str) -> str:
        return self._key(company, year, "raw", Path(filename).name)

    def processed_key(self, company: str, year: str, filename: str) -> str:
        return self._key(company, year, "processed", f"{Path(filename).stem}.json")

    def chunks_key(self, company: str, year: str, filename: str) -> str:
        return self._key(company, year, "chunks", f"{Path(filename).stem}_chunks.json")

    def upload_bytes(self, data: bytes, key: str, content_type: str) -> str:
        try:
            self.client.put_object(
                Bucket=self.bucket,
                Key=key,
                Body=data,
                ContentType=content_type,
            )
        except (BotoCoreError, ClientError) as error:
            raise StorageError(f"Unable to upload s3://{self.bucket}/{key}: {error}") from error
        return f"s3://{self.bucket}/{key}"

    def upload_json(self, payload: dict[str, Any], key: str) -> str:
        body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        return self.upload_bytes(body, key, "application/json")

    def list_processed_documents(self) -> list[S3Document]:
        prefix = self._key("") + "/"
        paginator = self.client.get_paginator("list_objects_v2")
        documents: list[S3Document] = []
        try:
            for page in paginator.paginate(Bucket=self.bucket, Prefix=prefix):
                for item in page.get("Contents", []):
                    key = item["Key"]
                    if "/processed/" in key and key.endswith(".json"):
                        documents.append(S3Document(key=key, label=f"S3: {key}"))
        except (BotoCoreError, ClientError) as error:
            raise StorageError(f"Unable to list documents in {self.bucket}: {error}") from error
        return sorted(documents, key=lambda item: item.key)

    def download_json(self, key: str) -> dict[str, Any]:
        try:
            response = self.client.get_object(Bucket=self.bucket, Key=key)
            return json.loads(response["Body"].read().decode("utf-8"))
        except (BotoCoreError, ClientError, json.JSONDecodeError) as error:
            raise StorageError(f"Unable to read s3://{self.bucket}/{key}: {error}") from error

