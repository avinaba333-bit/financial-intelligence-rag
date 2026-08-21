# 📊 AI-Powered Financial Intelligence Platform using Retrieval-Augmented Generation (RAG)

## 🎓 M.Tech Final Year Project

### Student
**Avinaba Ghosh**

---

# 📌 Project Overview

This project is an AI-powered Financial Intelligence Platform that analyzes annual financial reports using Retrieval-Augmented Generation (RAG).

Instead of simply answering questions from PDF documents, the system extracts financial insights, compares companies, analyzes trends, calculates financial ratios, identifies risks, and provides evidence-based responses with page citations.

The platform is designed using AWS cloud services and modern AI technologies.

---

# 🚀 Features

- Upload multiple Annual Reports (PDF)
- Extract text from financial reports
- Automatic Financial KPI extraction
- Financial Ratio Analysis
- AI-powered Question Answering
- Page-level citations
- Multi-company comparison
- Multi-year comparison
- Executive Summary Generation
- Business Segment Analysis
- Risk Analysis
- Interactive Dashboard
- AWS Cloud Deployment

---

# 🏗️ Project Architecture

```
User
   │
   ▼
Streamlit UI
   │
   ▼
PDF Upload
   │
   ▼
Amazon S3
   │
   ▼
Amazon Textract
   │
   ▼
Financial Text Extraction
   │
   ▼
Embedding Generation
(Amazon Bedrock)
   │
   ▼
Vector Database (FAISS)
   │
   ▼
Retrieval-Augmented Generation
   │
   ▼
Financial Insights & Dashboard
```

---

# 🛠️ Technology Stack

### Frontend

- Streamlit

### Backend

- Python

### AI / ML

- Amazon Bedrock
- Retrieval-Augmented Generation (RAG)
- FAISS

### AWS

- Amazon S3
- Amazon Textract
- Amazon Bedrock
- CloudWatch

### Libraries

- PyMuPDF
- Pandas
- NumPy
- Plotly
- Boto3

---

# 📁 Project Structure

```
financial-intelligence-rag/
│
├── backend/
├── pages/
├── data/
├── vector_store/
├── app.py
├── config.py
├── requirements.txt
├── README.md
└── .gitignore
```

---

# Current Progress

## Phase 1 ✅

- Python Environment Setup
- Streamlit Application
- PDF Upload
- Local PDF Processing
- JSON Generation

## Phase 2 🚧

- Text Chunking
- Embeddings
- Vector Database
- RAG Chatbot with Amazon Bedrock
- Evidence retrieval and page citations

## Phase 3 ⏳

- KPI Extraction
- Dashboard
- Charts
- Financial Ratios

## Phase 4 ⏳

- AWS Deployment
- Multi-Company Analysis
- Risk Analysis
- Executive Summary

---

# Future Enhancements

- Multi-Agent AI
- Voice Assistant
- Stock Market Integration
- Live Financial Data
- Cloud Deployment using AWS

---

# Author

**Avinaba Ghosh**

M.Tech (Data Science & AI)

Financial Intelligence Platform using AWS & Generative AI
