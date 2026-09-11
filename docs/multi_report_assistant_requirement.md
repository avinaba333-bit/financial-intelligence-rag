# Multi-report assistant requirement

## Objective

Let a user ask one evidence-grounded question across several indexed annual
reports while preserving the company, financial year, source PDF, physical page,
and supporting paragraph for every answer citation.

## User workflow

1. Open **AI Assistant**.
2. Select one report for focused Q&A or up to five reports for comparison.
3. Ask a question that names the metric and, where useful, the companies or years.
4. Read the concise report answer and its `E` citations.
5. Select an evidence button to open the matching original PDF page.
6. Verify the highlighted source block and complete supporting paragraph.

## Retrieval contract

- Every selected report keeps its own FAISS index and BM25 keyword index.
- Dense and lexical retrieval run separately for each report.
- Per-report results are fused and deduplicated before cross-report merging.
- The cross-report merge considers the first relevant result from each report
  before filling remaining slots by retrieval quality.
- Optional CrossEncoder reranking operates on the combined candidate set.
- Global evidence IDs are assigned only after the final result set is selected.

## Grounding and provenance rules

- Every chunk carries `document_id`, `company`, `financial_year`, `source_file`,
  `page_number`, vector-metadata key, and original-PDF key.
- A comparison must not combine different companies, years, totals, segments,
  currencies, or units into an unlabeled figure.
- A comparison fallback presents one exact evidence sentence per available
  report, labelled with company and financial year.
- Unsupported questions retain the existing insufficient-evidence response.
- Web material remains in the independent `W` citation namespace and never
  enters the uploaded-report RAG prompt.

## Evidence-viewer rules

- Each `E` button identifies its company and physical PDF page.
- Selecting a button loads that evidence item's own PDF rather than a global
  active-report PDF.
- The rendered page highlights the stored bounding box when available.
- The UI also displays the complete supporting paragraph with the search window
  highlighted, plus the retrieval score labelled as ranking—not confidence.

## Acceptance scenarios

### Cross-company question

Given indexed reports for Example Bank FY 2025-26 and Example Motors FY 2024-25,
when the user asks to compare reported net profit, the evidence set contains both
document identities and the answer/evidence controls retain both company-year
labels.

### Source navigation

When the user selects an evidence citation belonging to the second report, the
viewer opens the second report's original PDF page and displays its complete
supporting paragraph.

### Selection change

When the selected report set changes, the prior conversation and evidence state
are cleared so an answer cannot appear under the wrong research scope.

## Verification

```bash
python -m compileall -q app.py config.py backend pages tests
python -m pytest -q
```

The automated tests cover deterministic scope labels, cross-report result
balancing, deduplication, company/year-aware extractive comparison, selection
changes, and source-specific evidence controls.
