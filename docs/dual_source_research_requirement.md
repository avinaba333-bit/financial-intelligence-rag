# Dual-source financial research requirement

**Status:** Implemented on `feature/dual-source-research`

**Requested use case:** A guide asks a question whose answer may extend beyond
the uploaded annual report, such as “What will net profit be in FY 2028-29?”

## Problem statement

An annual report can support historical statements only for periods and facts
contained in that document. It cannot establish a future audited result. The
assistant must therefore avoid turning a current plan, analyst prediction, or
model output into a reported financial fact.

For current/future-looking questions, FinSight must return two independently
labelled research sections:

1. **Uploaded report evidence answer** — uses only the selected PDF/FAISS
   evidence, with `E` citations and original PDF pages.
2. **Current web research answer** — uses a live web search, with dated `W`
   citations and links. This section may describe investments, plans, guidance,
   targets, or outlook, but must not present an unavailable future result as an
   audited fact.

The two source sets must never be combined in one generation prompt or citation
namespace.

## Functional requirements

| ID | Requirement | Acceptance evidence |
| --- | --- | --- |
| DS-01 | Detect current/future intent from keywords and years later than the selected report period. | `plan_research()` unit tests cover latest, plan, investment, outlook, and FY 2028-29 against FY 2025-26. |
| DS-02 | Always retain the uploaded-report path as a separate answer. | Streamlit renders “Uploaded report evidence answer” before any web section. |
| DS-03 | Refuse to infer a future report result when the requested year is later than report coverage. | A deterministic insufficient-evidence answer is returned before model generation. |
| DS-04 | Search current web sources independently for routed questions. | `search_current_web()` receives company and question but no PDF chunks or `E` evidence. |
| DS-05 | Keep citations source-specific. | PDF passages use `E1…En`; web sources use `W1…Wn`. |
| DS-06 | Show the web search time and direct source links. | Each saved chat turn contains `searched_at`, title, domain, summary, and validated HTTP(S) URL. |
| DS-07 | Degrade safely when live search fails. | The report answer and evidence remain available while the web section shows a bounded error. |
| DS-08 | Let the researcher control web behaviour. | Sidebar modes are Automatic, Always include, and Off. |

## Source and safety rules

- Uploaded-report text is never sent to the web search provider.
- Web snippets are never supplied to the report answer generator.
- Explicit report years later than the selected report’s end year bypass
  generation and receive a deterministic refusal.
- Web answers are extractive and source-linked; FinSight does not calculate or
  forecast a missing future profit figure.
- Only `http` and `https` source links are retained. Duplicate URLs, empty
  snippets, and obvious share-price-prediction listings are removed.
- Regulatory/exchange, company-domain, investor-relations, and established-news
  results receive ranking preference. The original link remains available for
  verification.

## Primary acceptance scenario

**Given** a selected FY 2025-26 annual report

**When** the user asks “What will net profit be in FY 2028-29?”

**Then**:

- the report section states that the selected evidence is insufficient;
- the report section explicitly says it did not infer a future result;
- any retrieved PDF cards retain `E` citations and physical page references;
- automatic routing opens a distinct current-web section;
- web results use only `W` citations, links, and an access timestamp;
- plans or outlook may be displayed, but no 2028-29 profit is invented; and
- failure of the web provider does not remove the report response.

## Configuration

```env
WEB_SEARCH_ENABLED=true
WEB_SEARCH_REGION=in-en
WEB_SEARCH_BACKEND=auto
WEB_SEARCH_TIMEOUT_SECONDS=10
```

The current implementation uses the keyless `ddgs` metasearch package. Search
availability and result quality depend on upstream engines, so source links must
still be opened and verified before financial use.

## Verification commands

```bash
python -m compileall -q app.py config.py backend pages tests
python -m pytest -q
```

The automated suite verifies routing, range parsing, safe refusal, URL
validation, deduplication, provider failure isolation, citation namespaces, and
the two-section Streamlit workflow. It does not certify the truth of third-party
web content.
