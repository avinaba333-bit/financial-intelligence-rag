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
WEB_SEARCH_ENABLED = os.getenv("WEB_SEARCH_ENABLED", "true").lower() in {
    "1", "true", "yes"
}
WEB_SEARCH_REGION = os.getenv("WEB_SEARCH_REGION", "in-en")
WEB_SEARCH_BACKEND = os.getenv(
    "WEB_SEARCH_BACKEND",
    "auto",
)
try:
    WEB_SEARCH_TIMEOUT_SECONDS = max(3, int(os.getenv("WEB_SEARCH_TIMEOUT_SECONDS", "10")))
except ValueError:
    WEB_SEARCH_TIMEOUT_SECONDS = 10
