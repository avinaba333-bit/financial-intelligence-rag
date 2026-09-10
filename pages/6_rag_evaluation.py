import json

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from backend.embedding_service import deserialize_faiss_index, search_faiss_index
from backend.evaluation_service import evaluate_question, summarise_results
from backend.storage_service import S3Storage, StorageError
from backend.ui import apply_style, hero, readable_report_label
from config import AWS_REGION, S3_BUCKET, S3_PREFIX


st.set_page_config(
    page_title="FinSight | RAG Quality Lab",
    page_icon="🧪",
    layout="wide",
)

apply_style()
hero(
    "RAG Quality Lab.",
    "Prove that FinSight retrieves the right financial evidence—not merely a similar paragraph.",
)

SAMPLE_BENCHMARK = [
    {"question": "What was the net profit for the financial year?", "expected_pages": "42"},
    {"question": "What was the total revenue for the financial year?", "expected_pages": "43"},
    {"question": "Which business segment contributed the highest revenue?", "expected_pages": "57"},
]


def parse_pages(value):
    """Accept comma-separated editor values or JSON page lists."""
    values = value if isinstance(value, list) else str(value or "").split(",")
    pages = [str(page).strip() for page in values if str(page).strip()]
    if not pages:
        raise ValueError("Every benchmark question needs at least one expected PDF page.")
    return pages


def validate_benchmark(items):
    if not isinstance(items, list) or not items:
        raise ValueError("Add at least one benchmark question.")
    benchmark = []
    for position, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"Benchmark item {position} must be an object.")
        question = str(item.get("question", "")).strip()
        if not question:
            raise ValueError(f"Benchmark item {position} has no question.")
        benchmark.append({
            "question": question,
            "expected_pages": parse_pages(item.get("expected_pages")),
        })
    return benchmark


def quality_score(summary):
    """Transparent retrieval score: recall 45%, rank 35%, precision 20%."""
    return round(100 * (
        .45 * summary["mean_recall_at_k"]
        + .35 * summary["mean_reciprocal_rank"]
        + .20 * summary["mean_precision_at_k"]
    ))


def score_label(score):
    if score >= 85:
        return "Strong"
    if score >= 70:
        return "Good"
    if score >= 50:
        return "Needs review"
    return "Weak"


def failure_reason(result):
    if result.reciprocal_rank > 0:
        return "Correct evidence retrieved"
    if not result.retrieved_pages:
        return "No passages were retrieved"
    return "Expected PDF page missing from Top-K results"


if not S3_BUCKET:
    st.error("S3_BUCKET is not configured.")
    st.stop()

storage = S3Storage(bucket=S3_BUCKET, region=AWS_REGION, prefix=S3_PREFIX)


@st.cache_resource(show_spinner=False)
def load_vector_store(metadata_key: str):
    metadata = storage.download_json(metadata_key)
    index_key = metadata.get("index_s3_key")
    if not index_key:
        raise ValueError("The vector metadata does not contain index_s3_key.")
    index = deserialize_faiss_index(storage.download_bytes(index_key))
    chunks = metadata.get("chunks", [])
    if index.ntotal != len(chunks):
        raise ValueError("FAISS index and metadata chunk counts do not match.")
    return index, chunks, metadata


try:
    vector_documents = storage.list_vector_metadata()
except StorageError as error:
    st.error(str(error))
    st.stop()

if not vector_documents:
    st.warning("No vector index was found. Build one on the Vector Index page first.")
    st.stop()

selected_document = st.selectbox(
    "Indexed annual report",
    options=vector_documents,
    format_func=readable_report_label,
)

if st.session_state.get("evaluation_report_key") != selected_document.key:
    st.session_state.evaluation_report_key = selected_document.key
    st.session_state.pop("evaluation_result", None)
    st.session_state.pop("evaluation_history", None)

try:
    index, chunks, metadata = load_vector_store(selected_document.key)
except (StorageError, ValueError, RuntimeError) as error:
    st.error(str(error))
    st.stop()

company = metadata.get("company") or "Selected company"
financial_year = metadata.get("financial_year") or "Year not specified"

status1, status2, status3, status4 = st.columns(4)
status1.metric("Company", company)
status2.metric("Financial year", financial_year)
status3.metric("Indexed passages", f"{index.ntotal:,}")
status4.metric("Index status", "● Ready")

st.markdown(
    '<div class="finsight-lab-steps"><span class="active">1 · Select report</span>'
    '<span>2 · Prepare benchmark</span><span>3 · Run experiment</span>'
    '<span>4 · Inspect failures</span></div>',
    unsafe_allow_html=True,
)

builder, configuration = st.columns([1.45, 1], gap="large")

with builder, st.container(border=True):
    st.subheader("Benchmark workspace")
    st.caption(
        "Build questions here or upload a labelled JSON benchmark. Replace the "
        "example page numbers with physical pages from the selected PDF."
    )
    build_tab, upload_tab = st.tabs(["Build questions", "Upload JSON"])

    with build_tab:
        edited = st.data_editor(
            pd.DataFrame(SAMPLE_BENCHMARK),
            column_config={
                "question": st.column_config.TextColumn("Financial question", width="large", required=True),
                "expected_pages": st.column_config.TextColumn(
                    "Expected PDF page(s)",
                    help="Use commas when more than one page is correct, for example: 42, 43",
                    required=True,
                ),
            },
            num_rows="dynamic",
            hide_index=True,
            width="stretch",
            key="benchmark-editor",
        )
        editor_items = edited.fillna("").to_dict("records")

    with upload_tab:
        benchmark_file = st.file_uploader(
            "Upload labelled benchmark",
            type=["json"],
            help="Each item must contain question and expected_pages.",
        )
        download_payload = [
            {"question": row["question"], "expected_pages": parse_pages(row["expected_pages"])}
            for row in SAMPLE_BENCHMARK
        ]
        st.download_button(
            "Download sample benchmark",
            json.dumps(download_payload, indent=2),
            file_name="finsight_benchmark_sample.json",
            mime="application/json",
            icon=":material/download:",
        )
        with st.expander("View required JSON format"):
            st.code(json.dumps(download_payload[:1], indent=2), language="json")

with configuration, st.container(border=True):
    st.subheader("Experiment settings")
    retrieval_method = st.selectbox(
        "Retrieval method",
        ["Semantic FAISS"],
        help="This evaluator currently measures the production FAISS retrieval path.",
    )
    top_k = st.select_slider("Retrieved passages (Top-K)", options=list(range(1, 11)), value=5)
    benchmark_source = st.radio(
        "Benchmark source",
        ["Question builder", "Uploaded JSON"],
        horizontal=True,
    )
    st.info(
        "The expected PDF page is treated as ground truth. FinSight measures "
        "whether that page appears and how highly it ranks."
    )
    run_evaluation = st.button(
        "Run RAG evaluation",
        type="primary",
        width="stretch",
        icon=":material/science:",
    )

if run_evaluation:
    try:
        if benchmark_source == "Uploaded JSON":
            if benchmark_file is None:
                raise ValueError("Upload a benchmark JSON file or select Question builder.")
            raw_benchmark = json.loads(benchmark_file.getvalue().decode("utf-8"))
        else:
            raw_benchmark = editor_items
        benchmark = validate_benchmark(raw_benchmark)

        def retrieve(question: str):
            return search_faiss_index(index=index, chunks=chunks, question=question, top_k=top_k)

        progress = st.progress(0, text="Retrieving evidence…")
        results = []
        for position, item in enumerate(benchmark, start=1):
            results.append(evaluate_question(
                question=item["question"],
                expected_pages=item["expected_pages"],
                retrieve=retrieve,
            ))
            progress.progress(
                position / len(benchmark),
                text=f"Comparing expected pages · {position}/{len(benchmark)}",
            )
        progress.empty()

        summary = summarise_results(results)
        hit_rate = sum(result.reciprocal_rank > 0 for result in results) / len(results)
        score = quality_score(summary)
        result_rows = [{
            "Status": "Pass" if result.reciprocal_rank > 0 else "Fail",
            "Question": result.question,
            "Expected pages": ", ".join(result.expected_pages),
            "Retrieved pages": ", ".join(result.retrieved_pages),
            f"Precision@{top_k}": result.precision_at_k,
            f"Recall@{top_k}": result.recall_at_k,
            "Reciprocal rank": result.reciprocal_rank,
            "Latency (ms)": round(result.latency_ms, 1),
            "Finding": failure_reason(result),
        } for result in results]

        evaluation_payload = {
            "vector_metadata_key": selected_document.key,
            "company": company,
            "financial_year": financial_year,
            "retrieval_method": retrieval_method,
            "top_k": top_k,
            "quality_score": score,
            "hit_rate": hit_rate,
            "summary": summary,
            "results": [result.to_dict() for result in results],
        }
        st.session_state.evaluation_result = {
            "score": score,
            "hit_rate": hit_rate,
            "summary": summary,
            "rows": result_rows,
            "payload": evaluation_payload,
            "top_k": top_k,
        }
        history = st.session_state.setdefault("evaluation_history", [])
        history.append({
            "Run": len(history) + 1,
            "Top-K": top_k,
            "Questions": len(results),
            "Hit rate": hit_rate,
            "Precision": summary["mean_precision_at_k"],
            "Recall": summary["mean_recall_at_k"],
            "MRR": summary["mean_reciprocal_rank"],
            "Latency (ms)": summary["mean_latency_ms"],
            "Quality score": score,
        })
    except (json.JSONDecodeError, StorageError, ValueError, RuntimeError, UnicodeDecodeError) as error:
        st.error(str(error))

evaluation = st.session_state.get("evaluation_result")
if not evaluation:
    st.markdown(
        '''<section class="finsight-lab-empty">
        <div class="finsight-lab-orbit"><b>Q</b><span>→</span><b>R</b><span>→</span><b>✓</b></div>
        <h3>Your evaluation canvas is ready.</h3>
        <p>Add benchmark questions, choose Top-K, and run the experiment to reveal retrieval quality and failures.</p>
        </section>''',
        unsafe_allow_html=True,
    )
    st.stop()

st.divider()
st.subheader("Experiment results")
score = evaluation["score"]
summary = evaluation["summary"]
top_k = evaluation["top_k"]

score_column, metric_area = st.columns([.72, 2.3], gap="large")
with score_column:
    st.markdown(
        f'''<section class="finsight-quality-score">
        <span>RAG quality score</span><strong>{score}</strong><b>/ 100 · {score_label(score)}</b>
        <small>45% Recall + 35% MRR + 20% Precision</small>
        </section>''',
        unsafe_allow_html=True,
    )
with metric_area:
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Hit rate", f'{evaluation["hit_rate"]:.1%}')
    m2.metric(f"Precision@{top_k}", f'{summary["mean_precision_at_k"]:.1%}')
    m3.metric(f"Recall@{top_k}", f'{summary["mean_recall_at_k"]:.1%}')
    m4.metric("Mean reciprocal rank", f'{summary["mean_reciprocal_rank"]:.3f}')
    st.caption(f'Mean retrieval latency: {summary["mean_latency_ms"]:.0f} ms')

rows = evaluation["rows"]
chart1, chart2 = st.columns([1.45, 1], gap="large")
with chart1, st.container(border=True):
    st.markdown("#### Question-level retrieval quality")
    labels = [f"Q{position}" for position in range(1, len(rows) + 1)]
    figure = go.Figure()
    figure.add_bar(name="Recall", x=labels, y=[row[f"Recall@{top_k}"] for row in rows], marker_color="#49d8b4")
    figure.add_bar(name="Reciprocal rank", x=labels, y=[row["Reciprocal rank"] for row in rows], marker_color="#f1b94f")
    figure.update_layout(barmode="group", yaxis_range=[0, 1], height=330, margin=dict(l=20, r=20, t=20, b=20))
    st.plotly_chart(figure, width="stretch")

with chart2, st.container(border=True):
    st.markdown("#### Pass / fail distribution")
    passed = sum(row["Status"] == "Pass" for row in rows)
    figure = go.Figure(go.Pie(
        labels=["Correct page found", "Needs investigation"],
        values=[passed, len(rows) - passed],
        hole=.68,
        marker_colors=["#49d8b4", "#f06d6d"],
    ))
    figure.update_layout(height=330, margin=dict(l=20, r=20, t=20, b=20), showlegend=True)
    st.plotly_chart(figure, width="stretch")

st.markdown("#### Question-level inspection")
st.dataframe(
    pd.DataFrame(rows),
    hide_index=True,
    width="stretch",
    column_config={
        "Status": st.column_config.TextColumn(width="small"),
        "Question": st.column_config.TextColumn(width="large"),
        f"Precision@{top_k}": st.column_config.NumberColumn(format="%.2f"),
        f"Recall@{top_k}": st.column_config.NumberColumn(format="%.2f"),
        "Reciprocal rank": st.column_config.NumberColumn(format="%.2f"),
    },
)

failed_rows = [row for row in rows if row["Status"] == "Fail"]
with st.expander(f"Failure analysis · {len(failed_rows)} questions", expanded=bool(failed_rows)):
    if not failed_rows:
        st.success("Every benchmark question retrieved an expected PDF page.")
    for row in failed_rows:
        st.markdown(f'**{row["Question"]}**')
        st.write(row["Finding"])
        st.caption(f'Expected: {row["Expected pages"]} · Retrieved: {row["Retrieved pages"]}')

history = st.session_state.get("evaluation_history", [])
if len(history) > 1:
    with st.expander(f"Compare experiment runs · {len(history)}"):
        st.dataframe(pd.DataFrame(history), hide_index=True, width="stretch")

st.download_button(
    "Download evaluation report",
    data=json.dumps(evaluation["payload"], indent=2),
    file_name="finsight_rag_evaluation.json",
    mime="application/json",
    icon=":material/download:",
)
