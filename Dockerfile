FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1
ENV HF_HOME=/opt/huggingface

RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Install CPU-only PyTorch to prevent large CUDA packages being downloaded.
RUN python -m pip install --upgrade pip setuptools wheel \
    && python -m pip install \
       --index-url https://download.pytorch.org/whl/cpu \
       torch \
    && python -m pip install -r requirements.txt

# Cache the RAG models during the image build so the first question does not
# need to download them on EC2.
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')" \
    && python -c "from transformers import AutoModelForSeq2SeqLM, AutoTokenizer; model='google/flan-t5-small'; AutoTokenizer.from_pretrained(model); AutoModelForSeq2SeqLM.from_pretrained(model)"

COPY . .

EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8501/_stcore/health')" || exit 1

CMD ["python", "-m", "streamlit", "run", "app.py", "--server.address=0.0.0.0", "--server.port=8501", "--server.headless=true", "--server.fileWatcherType=none", "--browser.gatherUsageStats=false"]
