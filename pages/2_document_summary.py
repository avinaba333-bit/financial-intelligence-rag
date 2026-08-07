import json
from pathlib import Path

import streamlit as st

from backend.storage_service import S3Storage, StorageError
from config import AWS_REGION, S3_BUCKET, S3_PREFIX


st.set_page_config(
    page_title="Document Summary",
    page_icon="📚",
    layout="wide",
)

st.title("Processed Financial Documents")

processed_directory = Path("data/processed")

json_files = sorted(processed_directory.rglob("*.json"))
document_options = [
    {"kind": "local", "value": path, "label": f"Local: {path}"}
    for path in json_files
]

if S3_BUCKET:
    try:
        storage = S3Storage(S3_BUCKET, AWS_REGION, S3_PREFIX)
        document_options.extend(
            {"kind": "s3", "value": item.key, "label": item.label}
            for item in storage.list_processed_documents()
        )
    except StorageError as error:
        st.warning(f"S3 documents are temporarily unavailable: {error}")

if not document_options:
    st.info(
        "No processed documents found. "
        "Upload and process a PDF first."
    )
    st.stop()

selected_option = st.selectbox(
    "Select a processed document",
    options=document_options,
    format_func=lambda option: option["label"],
)

try:
    if selected_option["kind"] == "s3":
        document = storage.download_json(selected_option["value"])
    else:
        with selected_option["value"].open("r", encoding="utf-8") as input_file:
            document = json.load(input_file)

except (OSError, json.JSONDecodeError, StorageError) as error:
    st.error(f"Unable to read the selected document: {error}")
    st.stop()

required_fields = {
    "company",
    "financial_year",
    "source_file",
    "total_pages",
    "pages",
}

missing_fields = required_fields.difference(document)

if missing_fields:
    st.error(
        "The processed document is missing required fields: "
        + ", ".join(sorted(missing_fields))
    )
    st.stop()

col1, col2, col3 = st.columns(3)

col1.metric(
    "Company",
    document["company"],
)

col2.metric(
    "Financial Year",
    document["financial_year"],
)

col3.metric(
    "Total Pages",
    document["total_pages"],
)

st.subheader("Source File")
st.write(document["source_file"])

pages_with_text = [
    page
    for page in document["pages"]
    if page.get("text", "").strip()
]

st.write(
    f"Pages containing readable text: "
    f"**{len(pages_with_text)}**"
)

page_numbers = [
    page["page_number"]
    for page in document["pages"]
]

selected_page = st.selectbox(
    "Select page number",
    options=page_numbers,
)

selected_page_data = next(
    page
    for page in document["pages"]
    if page["page_number"] == selected_page
)

st.subheader(
    f"Extracted Text — Page {selected_page}"
)

page_text = selected_page_data.get("text", "").strip()

if page_text:
    st.text_area(
        "Page content",
        value=page_text,
        height=500,
        disabled=True,
    )

    st.download_button(
        label="Download page text",
        data=page_text,
        file_name=f"page_{selected_page}.txt",
        mime="text/plain",
    )
else:
    st.warning(
        "No readable text was extracted from this page."
    )
