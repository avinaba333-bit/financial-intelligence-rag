import json
import re
from pathlib import Path

import streamlit as st

from backend.pdf_processor import extract_pdf_pages


st.set_page_config(
    page_title="Upload Financial Reports",
    page_icon="📄",
    layout="wide",
)

st.title("Upload Financial Reports")

st.write(
    """
    Upload annual reports for local PDF processing.
    Extracted text will be stored page by page for later RAG processing.
    """
)


def clean_folder_name(value: str) -> str:
    """Create a safe folder name from user input."""

    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)

    return value.strip("-")


company_name = st.text_input(
    "Company name",
    placeholder="Example: HDFC Bank",
)

financial_year = st.text_input(
    "Financial year",
    placeholder="Example: 2025-26",
)

uploaded_files = st.file_uploader(
    "Select PDF annual reports",
    type=["pdf"],
    accept_multiple_files=True,
)

if uploaded_files:
    st.subheader("Selected Reports")

    for uploaded_file in uploaded_files:
        file_size_mb = uploaded_file.size / (1024 * 1024)

        st.write(
            f"**{uploaded_file.name}** — "
            f"{file_size_mb:.2f} MB"
        )

if st.button("Upload and Process", type="primary"):
    if not company_name.strip():
        st.error("Enter the company name.")

    elif not financial_year.strip():
        st.error("Enter the financial year.")

    elif not uploaded_files:
        st.error("Upload at least one PDF.")

    else:
        company_folder = clean_folder_name(company_name)
        year_folder = clean_folder_name(financial_year)

        raw_directory = (
            Path("data")
            / "raw"
            / company_folder
            / year_folder
        )

        processed_directory = (
            Path("data")
            / "processed"
            / company_folder
            / year_folder
        )

        raw_directory.mkdir(
            parents=True,
            exist_ok=True,
        )

        processed_directory.mkdir(
            parents=True,
            exist_ok=True,
        )

        for uploaded_file in uploaded_files:
            local_pdf_path = raw_directory / uploaded_file.name

            with open(local_pdf_path, "wb") as output_file:
                output_file.write(uploaded_file.getbuffer())

            try:
                pages = extract_pdf_pages(
                    str(local_pdf_path)
                )

                processed_file = (
                    processed_directory
                    / f"{local_pdf_path.stem}.json"
                )

                processed_data = {
                    "company": company_name.strip(),
                    "financial_year": financial_year.strip(),
                    "source_file": uploaded_file.name,
                    "total_pages": len(pages),
                    "pages": pages,
                }

                with open(
                    processed_file,
                    "w",
                    encoding="utf-8",
                ) as output_file:
                    json.dump(
                        processed_data,
                        output_file,
                        ensure_ascii=False,
                        indent=2,
                    )

                pages_with_text = sum(
                    1 for page in pages if page["text"]
                )

                st.success(
                    f"{uploaded_file.name} processed successfully."
                )

                st.write(
                    f"Total pages: **{len(pages)}**"
                )

                st.write(
                    f"Pages containing text: **{pages_with_text}**"
                )

                with st.expander(
                    f"Preview extracted text: {uploaded_file.name}"
                ):
                    preview_pages = pages[:3]

                    for page in preview_pages:
                        st.markdown(
                            f"### Page {page['page_number']}"
                        )

                        if page["text"]:
                            st.text(
                                page["text"][:2000]
                            )
                        else:
                            st.warning(
                                "No readable text detected on this page."
                            )

            except Exception as error:
                st.error(
                    f"Failed to process {uploaded_file.name}: "
                    f"{error}"
                )