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
    def __init__(
        self,
        bucket: str,
        region: str,
        prefix: str = "financial-reports",
    ):
        if not bucket.strip():
            raise ValueError("S3_BUCKET is not configured.")

        self.bucket = bucket.strip()
        self.prefix = prefix.strip("/")
        self.client = boto3.client(
            "s3",
            region_name=region,
        )

    def _key(self, *parts: str) -> str:
        clean_parts = [
            part.strip("/")
            for part in parts
            if part.strip("/")
        ]
        return "/".join([self.prefix, *clean_parts])

    def raw_key(
        self,
        company: str,
        year: str,
        filename: str,
    ) -> str:
        return self._key(
            company,
            year,
            "raw",
            Path(filename).name,
        )

    def processed_key(
        self,
        company: str,
        year: str,
        filename: str,
    ) -> str:
        return self._key(
            company,
            year,
            "processed",
            f"{Path(filename).stem}.json",
        )

    def chunks_key(
        self,
        company: str,
        year: str,
        filename: str,
    ) -> str:
        return self._key(
            company,
            year,
            "chunks",
            f"{Path(filename).stem}_chunks.json",
        )

    def vector_index_key(
        self,
        company: str,
        year: str,
        filename: str,
    ) -> str:
        stem = Path(filename).stem.replace("_chunks", "")
        return self._key(
            company,
            year,
            "vector-store",
            f"{stem}.faiss",
        )

    def vector_metadata_key(
        self,
        company: str,
        year: str,
        filename: str,
    ) -> str:
        stem = Path(filename).stem.replace("_chunks", "")
        return self._key(
            company,
            year,
            "vector-store",
            f"{stem}_metadata.json",
        )

    def upload_bytes(
        self,
        data: bytes,
        key: str,
        content_type: str,
    ) -> str:
        try:
            self.client.put_object(
                Bucket=self.bucket,
                Key=key,
                Body=data,
                ContentType=content_type,
            )
        except (BotoCoreError, ClientError) as error:
            raise StorageError(
                f"Unable to upload s3://{self.bucket}/{key}: {error}"
            ) from error

        return f"s3://{self.bucket}/{key}"

    def upload_json(
        self,
        payload: dict[str, Any],
        key: str,
    ) -> str:
        body = json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
        ).encode("utf-8")

        return self.upload_bytes(
            body,
            key,
            "application/json",
        )

    def list_processed_documents(self) -> list[S3Document]:
        prefix = self._key("") + "/"
        paginator = self.client.get_paginator("list_objects_v2")
        documents: list[S3Document] = []

        try:
            for page in paginator.paginate(
                Bucket=self.bucket,
                Prefix=prefix,
            ):
                for item in page.get("Contents", []):
                    key = item["Key"]

                    if "/processed/" in key and key.endswith(".json"):
                        documents.append(
                            S3Document(
                                key=key,
                                label=f"S3: {key}",
                            )
                        )
        except (BotoCoreError, ClientError) as error:
            raise StorageError(
                f"Unable to list documents in {self.bucket}: {error}"
            ) from error

        return sorted(
            documents,
            key=lambda item: item.key,
        )

    def list_chunk_documents(self) -> list[S3Document]:
        prefix = self._key("") + "/"
        paginator = self.client.get_paginator("list_objects_v2")
        documents: list[S3Document] = []

        try:
            for page in paginator.paginate(
                Bucket=self.bucket,
                Prefix=prefix,
            ):
                for item in page.get("Contents", []):
                    key = item["Key"]

                    if (
                        "/chunks/" in key
                        and key.endswith("_chunks.json")
                    ):
                        documents.append(
                            S3Document(
                                key=key,
                                label=f"S3 chunks: {key}",
                            )
                        )
        except (BotoCoreError, ClientError) as error:
            raise StorageError(
                f"Unable to list chunk files in {self.bucket}: {error}"
            ) from error

        return sorted(
            documents,
            key=lambda item: item.key,
        )

    def list_index_sources(self) -> list[S3Document]:
        """List reports that can be indexed, preferring existing chunk files.

        A newly uploaded report initially has only a ``processed`` JSON object.
        Keeping those objects in this list lets the vector-index page generate
        chunks on demand instead of hiding the report until the user visits the
        chunk viewer first.
        """
        processed_documents = self.list_processed_documents()
        chunk_documents = self.list_chunk_documents()
        chunk_keys = {document.key for document in chunk_documents}
        sources = list(chunk_documents)

        for document in processed_documents:
            processed_path = Path(document.key)
            expected_chunk_key = str(
                processed_path.parent.parent
                / "chunks"
                / f"{processed_path.stem}_chunks.json"
            )
            if expected_chunk_key not in chunk_keys:
                sources.append(
                    S3Document(
                        key=document.key,
                        label=f"S3 processed report (chunks generated automatically): {document.key}",
                    )
                )

        return sorted(sources, key=lambda item: item.key)

    def list_vector_metadata(self) -> list[S3Document]:
        """List metadata files for FAISS indexes stored in S3."""
        prefix = self._key("") + "/"
        paginator = self.client.get_paginator("list_objects_v2")
        documents: list[S3Document] = []

        try:
            for page in paginator.paginate(
                Bucket=self.bucket,
                Prefix=prefix,
            ):
                for item in page.get("Contents", []):
                    key = item["Key"]

                    if (
                        "/vector-store/" in key
                        and key.endswith("_metadata.json")
                    ):
                        documents.append(
                            S3Document(
                                key=key,
                                label=f"Vector index: {key}",
                            )
                        )
        except (BotoCoreError, ClientError) as error:
            raise StorageError(
                f"Unable to list vector indexes in {self.bucket}: {error}"
            ) from error

        return sorted(documents, key=lambda item: item.key)

    def download_json(
        self,
        key: str,
    ) -> dict[str, Any]:
        try:
            response = self.client.get_object(
                Bucket=self.bucket,
                Key=key,
            )
            return json.loads(
                response["Body"].read().decode("utf-8")
            )
        except (
            BotoCoreError,
            ClientError,
            json.JSONDecodeError,
        ) as error:
            raise StorageError(
                f"Unable to read s3://{self.bucket}/{key}: {error}"
            ) from error

    def download_bytes(
        self,
        key: str,
    ) -> bytes:
        try:
            response = self.client.get_object(
                Bucket=self.bucket,
                Key=key,
            )
            return response["Body"].read()
        except (BotoCoreError, ClientError) as error:
            raise StorageError(
                f"Unable to read s3://{self.bucket}/{key}: {error}"
            ) from error
