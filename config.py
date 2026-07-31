import os

from dotenv import load_dotenv


load_dotenv()

AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
S3_BUCKET = os.getenv("S3_BUCKET", "")
CHAT_MODEL_ID = os.getenv("CHAT_MODEL_ID", "")
EMBEDDING_MODEL_ID = os.getenv("EMBEDDING_MODEL_ID", "")