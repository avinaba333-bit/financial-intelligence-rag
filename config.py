import os

from dotenv import load_dotenv


load_dotenv()

AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
S3_BUCKET = os.getenv("S3_BUCKET", "")
S3_PREFIX = os.getenv("S3_PREFIX", "financial-reports")
S3_ENABLED = os.getenv("S3_ENABLED", "false").lower() in {"1", "true", "yes"}
CHAT_MODEL_ID = os.getenv("CHAT_MODEL_ID", "")
EMBEDDING_MODEL_ID = os.getenv("EMBEDDING_MODEL_ID", "")
LOCAL_CHAT_MODEL_ID = os.getenv(
    "LOCAL_CHAT_MODEL_ID",
    "google/flan-t5-small",
)
