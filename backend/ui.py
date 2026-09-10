"""Shared presentation helpers. Never interpret document text as HTML/Markdown."""

from html import escape
import re

import streamlit as st


BULLET_PATTERN = re.compile(r"^(?:[-•▪◦*]|\d+[.)])\s+")
SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9₹$])")


def apply_style():
    st.markdown('''<style>
    :root {
      --finsight-ink: #07151c;
      --finsight-navy: #0b2531;
      --finsight-teal: #0f8d75;
      --finsight-mint: #49d8b4;
      --finsight-gold: #f1b94f;
      --finsight-soft: rgba(73,216,180,.09);
      --finsight-line: rgba(126,174,166,.22);
      --finsight-shadow: 0 18px 55px rgba(2,16,22,.14);
    }
    html, body, .stApp {
      font-family: Inter, ui-sans-serif, -apple-system, BlinkMacSystemFont,
        "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      -webkit-font-smoothing: antialiased;
      text-rendering: optimizeLegibility;
    }
    [data-testid="stAppViewContainer"] {
      background-image:
        radial-gradient(circle at 94% 2%, rgba(73,216,180,.085), transparent 27rem),
        linear-gradient(rgba(73,216,180,.018) 1px, transparent 1px),
        linear-gradient(90deg, rgba(73,216,180,.018) 1px, transparent 1px);
      background-size: auto, 38px 38px, 38px 38px;
    }
    [data-testid="stHeader"] {background: transparent;}
    .block-container {
      width: min(100%, 1180px);
      max-width: 1180px;
      padding: clamp(1rem, 2.2vw, 2.15rem) clamp(1rem, 2.8vw, 2.5rem) 4rem;
    }
    h1, h2, h3 {letter-spacing: -.035em;}
    h2 {font-weight: 720;}
    h3 {font-weight: 680;}
    p, li, label, [data-testid="stCaptionContainer"] {line-height: 1.6;}
    .finsight-hero {
      position: relative;
      overflow: hidden;
      padding: clamp(1.35rem, 3vw, 2.25rem) clamp(1.25rem, 3.4vw, 2.7rem);
      border: 1px solid rgba(127,240,210,.18);
      border-radius: 26px;
      background:
        linear-gradient(rgba(73,216,180,.055) 1px, transparent 1px),
        linear-gradient(90deg, rgba(73,216,180,.055) 1px, transparent 1px),
        linear-gradient(120deg,var(--finsight-ink),#0b3440 56%,#0f735f);
      background-size: 30px 30px, 30px 30px, auto;
      box-shadow: 0 24px 65px rgba(3,25,33,.24);
      color: #fff;
      margin-bottom: clamp(1.25rem, 2.5vw, 2rem);
    }
    .finsight-hero::after {
      content: "";
      position: absolute;
      width: 18rem;
      height: 18rem;
      right: -6rem;
      top: -9rem;
      border-radius: 50%;
      border: 1px solid rgba(255,255,255,.16);
      background: rgba(73,216,180,.08);
      pointer-events: none;
    }
    .finsight-hero h1 {
      color: #fff;
      padding: .38rem 0 .45rem;
      margin: 0;
      font-size: clamp(1.75rem, 3.5vw, 2.65rem);
      line-height: 1.08;
      max-width: 900px;
    }
    .finsight-hero p {
      color: #e2f3ef;
      margin: 0;
      max-width: 820px;
      font-size: clamp(.93rem, 1.35vw, 1.06rem);
    }
    .finsight-kicker {
      font-size: .75rem;
      font-weight: 700;
      letter-spacing: .16em;
      color: var(--finsight-gold);
    }
    [data-testid="stSidebar"] {
      border-right: 1px solid var(--finsight-line);
      min-width: 310px;
      max-width: 310px;
      background:
        linear-gradient(180deg, rgba(73,216,180,.055), transparent 15rem),
        color-mix(in srgb, var(--secondary-background-color) 96%, var(--finsight-ink));
    }
    [data-testid="stSidebar"]::before {
      content: "◈  FINSIGHT  /  RESEARCH DESK";
      display: block;
      margin: 1.4rem 1.15rem .35rem;
      color: var(--finsight-mint);
      font-size: .72rem;
      font-weight: 800;
      letter-spacing: .14em;
    }
    [data-testid="stSidebar"] [data-testid="stVerticalBlock"] {gap: .82rem;}
    [data-testid="stSidebarNav"] ul {gap: .22rem;}
    [data-testid="stSidebarNav"] li {margin-bottom: .18rem;}
    [data-testid="stSidebarNav"] span {
      line-height: 1.45;
      font-size: .88rem;
      font-weight: 640;
      letter-spacing: .005em;
    }
    [data-testid="stSidebarNav"] [data-testid="stNavSectionHeader"] {
      color: color-mix(in srgb, var(--text-color) 58%, transparent);
      font-size: .67rem;
      font-weight: 800;
      letter-spacing: .12em;
      text-transform: uppercase;
    }
    [data-testid="stSidebarNav"] a {
      border: 1px solid transparent;
      border-radius: 10px;
      transition: background .16s ease, border-color .16s ease, transform .16s ease;
    }
    [data-testid="stSidebarNav"] a:hover {
      border-color: var(--finsight-line);
      background: var(--finsight-soft);
      transform: translateX(2px);
    }
    [data-testid="stSidebarCollapseButton"] [data-testid="stIconMaterial"],
    [data-testid="stSidebarCollapsedControl"] [data-testid="stIconMaterial"] {
      display: none !important;
    }
    [data-testid="stSidebarCollapseButton"] button::after {
      content: "‹";
      display: inline-block;
      font-family: Arial, sans-serif;
      font-size: 1.8rem;
      font-weight: 400;
      line-height: 1;
    }
    [data-testid="stSidebarCollapsedControl"] button::after {
      content: "›";
      display: inline-block;
      font-family: Arial, sans-serif;
      font-size: 1.8rem;
      font-weight: 400;
      line-height: 1;
    }
    [data-testid="stMetric"] {
      min-height: 105px;
      padding: 1rem 1.05rem;
      border: 1px solid var(--finsight-line);
      border-radius: 18px;
      background:
        linear-gradient(135deg, var(--finsight-soft), transparent 56%),
        color-mix(in srgb, var(--secondary-background-color) 86%, transparent);
      box-shadow: 0 12px 34px rgba(3,25,33,.055);
      position: relative;
      overflow: hidden;
    }
    [data-testid="stMetric"]::before {
      content: "";
      position: absolute;
      inset: 0 auto 0 0;
      width: 3px;
      background: linear-gradient(var(--finsight-mint), var(--finsight-gold));
    }
    [data-testid="stMetricLabel"] {font-weight: 650; opacity: .78;}
    [data-testid="stMetricValue"] {letter-spacing: -.035em;}
    [data-testid="stButton"] > button,
    [data-testid="stDownloadButton"] > button,
    [data-testid="stFormSubmitButton"] > button {
      min-height: 2.75rem;
      border-radius: 12px;
      border-color: var(--finsight-line);
      font-weight: 650;
      transition: transform .15s ease, border-color .15s ease, box-shadow .15s ease;
    }
    [data-testid="stButton"] > button:hover,
    [data-testid="stDownloadButton"] > button:hover,
    [data-testid="stFormSubmitButton"] > button:hover {
      border-color: var(--finsight-mint);
      box-shadow: 0 8px 22px rgba(19,117,101,.12);
      transform: translateY(-1px);
    }
    [data-testid="stButton"] > button[kind="primary"],
    [data-testid="stFormSubmitButton"] > button[kind="primary"] {
      color: #041713;
      border: 0;
      background: linear-gradient(110deg, var(--finsight-mint), #9aefd9);
      box-shadow: 0 10px 28px rgba(73,216,180,.18);
    }
    [data-testid="stTextInputRootElement"],
    [data-testid="stTextAreaRootElement"],
    [data-baseweb="select"] > div,
    [data-testid="stFileUploaderDropzone"] {
      border-radius: 12px;
    }
    [data-testid="stExpander"] {
      border-color: var(--finsight-line);
      border-radius: 16px;
      overflow: hidden;
    }
    [data-testid="stExpander"] summary [data-testid="stIconMaterial"] {
      display: none !important;
    }
    [data-testid="stExpander"] summary::before {
      content: "›";
      display: inline-block;
      flex: 0 0 auto;
      margin-right: .45rem;
      font-family: Arial, sans-serif;
      font-size: 1.35rem;
      line-height: 1;
      transition: transform .15s ease;
    }
    [data-testid="stExpander"] details[open] > summary::before {
      transform: rotate(90deg);
    }
    [data-testid="stAlert"] {border-radius: 14px;}
    [data-testid="stChatMessage"] {
      border: 1px solid var(--finsight-line);
      border-radius: 20px;
      padding: .55rem .75rem;
      margin-bottom: .9rem;
      background: color-mix(in srgb, var(--secondary-background-color) 84%, transparent);
      box-shadow: var(--finsight-shadow);
      overflow: hidden;
    }
    [data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarAssistant"]) {
      border-left: 4px solid var(--finsight-mint);
      background:
        linear-gradient(120deg, rgba(73,216,180,.09), transparent 45%),
        color-mix(in srgb, var(--secondary-background-color) 88%, transparent);
    }
    [data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) {
      border-left: 4px solid var(--finsight-gold);
    }
    [data-testid="stChatInput"] {
      border: 1px solid rgba(73,216,180,.5);
      border-radius: 18px;
      background: color-mix(in srgb, var(--secondary-background-color) 90%, transparent);
      box-shadow: 0 12px 36px rgba(15,141,117,.13);
    }
    [data-testid="stChatInput"]:focus-within {box-shadow: 0 0 0 3px rgba(73,216,180,.1), 0 15px 40px rgba(15,141,117,.16);}
    [data-testid="stDataFrame"] {
      border: 1px solid var(--finsight-line);
      border-radius: 14px;
      overflow: hidden;
    }
    [data-testid="stPlotlyChart"] {
      width: 100%;
      min-width: 0;
    }
    [data-testid="stVerticalBlockBorderWrapper"] {
      border-color: var(--finsight-line) !important;
      border-radius: 20px !important;
      background: linear-gradient(140deg, var(--finsight-soft), transparent 60%);
      box-shadow: 0 14px 38px rgba(3,25,33,.06);
    }
    hr {border-color: var(--finsight-line) !important;}
    a {text-underline-offset: 3px;}
    .finsight-excerpt {overflow-wrap: anywhere; line-height: 1.75;
      border-left: 3px solid #209a84; padding: .9rem 1.05rem; margin: .5rem 0 1rem;
      background: var(--finsight-soft); border-radius: 0 12px 12px 0;}
    .finsight-excerpt p {margin: 0 0 .85rem; text-align: left;}
    .finsight-excerpt p:last-child {margin-bottom: 0;}
    .finsight-excerpt ul {margin: .2rem 0 .85rem; padding-left: 1.35rem;}
    .finsight-excerpt li {margin: .25rem 0;}
    .finsight-excerpt mark {background: #ffedaa; color: #192733; border-radius: 3px;
      padding: 0 .08rem;}
    .finsight-report-card {
      position: relative;
      overflow: hidden;
      margin: 1rem 0 .4rem;
      padding: 1rem;
      border: 1px solid var(--finsight-line);
      border-radius: 18px;
      background:
        radial-gradient(circle at 90% 8%, rgba(241,185,79,.14), transparent 7rem),
        linear-gradient(145deg, rgba(73,216,180,.10), rgba(7,21,28,.08));
      box-shadow: 0 15px 38px rgba(2,16,22,.11);
    }
    .finsight-report-art {display: block; width: 100%; height: 118px; margin-bottom: .8rem;}
    .finsight-report-eyebrow {
      color: var(--finsight-mint);
      font-size: .65rem;
      font-weight: 800;
      letter-spacing: .12em;
      text-transform: uppercase;
    }
    .finsight-report-card h4 {font-size: 1rem; margin: .3rem 0 .2rem; line-height: 1.25;}
    .finsight-report-file {
      margin: 0 0 .75rem;
      color: color-mix(in srgb, var(--text-color) 66%, transparent);
      font-size: .72rem;
      line-height: 1.4;
      overflow-wrap: anywhere;
    }
    .finsight-report-meta {display: flex; gap: .45rem; flex-wrap: wrap;}
    .finsight-report-meta span {
      padding: .28rem .48rem;
      border: 1px solid var(--finsight-line);
      border-radius: 999px;
      background: rgba(73,216,180,.07);
      font-size: .67rem;
      font-weight: 700;
    }
    @media (max-width: 900px) {
      .block-container {padding: 1rem 1rem 2.5rem;}
      [data-testid="stHorizontalBlock"] {gap: .8rem;}
      [data-testid="stMetric"] {min-height: 92px; padding: .8rem .9rem;}
    }
    @media (max-width: 640px) {
      [data-testid="stSidebar"] {min-width: min(88vw, 310px); max-width: min(88vw, 310px);}
      .block-container {padding: .75rem .75rem 2.25rem;}
      .finsight-hero {border-radius: 17px; margin-bottom: 1rem;}
      .finsight-hero::after {width: 12rem; height: 12rem; right: -5rem; top: -6rem;}
      [data-testid="stMetric"] {min-height: auto;}
      [data-testid="stChatMessage"] {border-radius: 13px; padding: .15rem .25rem;}
      .finsight-excerpt {padding: .75rem .85rem; line-height: 1.65;}
      [data-testid="stButton"] > button,
      [data-testid="stDownloadButton"] > button,
      [data-testid="stFormSubmitButton"] > button {min-height: 2.9rem; width: 100%;}
    }
    @media (prefers-reduced-motion: reduce) {
      [data-testid="stButton"] > button,
      [data-testid="stDownloadButton"] > button,
      [data-testid="stFormSubmitButton"] > button {transition: none;}
    }
    </style>''', unsafe_allow_html=True)


def hero(title, subtitle):
    st.markdown(f'<section class="finsight-hero"><div class="finsight-kicker">FINSIGHT / FINANCIAL RESEARCH</div>'
                f'<h1>{escape(title)}</h1><p>{escape(subtitle)}</p></section>', unsafe_allow_html=True)


def sidebar_report_card(company, financial_year, source_file, page_count, passage_count):
    """Add a compact visual identity card for the active annual report."""
    safe_company = escape(str(company or 'Selected company'))
    safe_year = escape(str(financial_year or 'Year not specified'))
    safe_file = escape(str(source_file or 'Annual report PDF'))
    safe_pages = escape(str(page_count or '—'))
    safe_passages = escape(str(passage_count or '—'))
    st.sidebar.markdown(
        f'''<section class="finsight-report-card">
        <svg class="finsight-report-art" viewBox="0 0 260 118" role="img"
             aria-label="Annual report with financial chart">
          <defs>
            <linearGradient id="reportSheet" x1="0" y1="0" x2="1" y2="1">
              <stop offset="0" stop-color="#123846"/><stop offset="1" stop-color="#0a2029"/>
            </linearGradient>
            <linearGradient id="chartLine" x1="0" y1="0" x2="1" y2="0">
              <stop offset="0" stop-color="#49d8b4"/><stop offset="1" stop-color="#f1b94f"/>
            </linearGradient>
          </defs>
          <rect x="43" y="8" width="126" height="100" rx="10" fill="url(#reportSheet)"
                stroke="#3a756f"/>
          <path d="M145 8v24h24" fill="#173f49" stroke="#3a756f"/>
          <rect x="58" y="27" width="51" height="5" rx="2.5" fill="#49d8b4" opacity=".8"/>
          <rect x="58" y="39" width="82" height="3" rx="1.5" fill="#76918f" opacity=".55"/>
          <rect x="58" y="47" width="68" height="3" rx="1.5" fill="#76918f" opacity=".42"/>
          <rect x="58" y="72" width="12" height="20" rx="3" fill="#1c7466"/>
          <rect x="77" y="62" width="12" height="30" rx="3" fill="#2a9f88"/>
          <rect x="96" y="51" width="12" height="41" rx="3" fill="#49d8b4"/>
          <circle cx="184" cy="70" r="32" fill="#0b2630" stroke="#34665f"/>
          <path d="M166 82l12-15 10 7 16-22" fill="none" stroke="url(#chartLine)"
                stroke-width="4" stroke-linecap="round" stroke-linejoin="round"/>
          <circle cx="204" cy="52" r="4" fill="#f1b94f"/>
        </svg>
        <div class="finsight-report-eyebrow">Active annual report</div>
        <h4>{safe_company}</h4>
        <p class="finsight-report-file">{safe_file}</p>
        <div class="finsight-report-meta">
          <span>FY {safe_year}</span><span>{safe_pages} pages</span><span>{safe_passages} passages</span>
        </div>
        </section>''',
        unsafe_allow_html=True,
    )


def _join_pdf_lines(lines):
    """Join visual PDF lines without joining real bullets or blank paragraphs."""
    paragraphs = []
    current = []

    def flush():
        if current:
            paragraphs.append(' '.join(current).strip())
            current.clear()

    for raw_line in lines:
        line = re.sub(r"\s+", " ", raw_line).strip()
        if not line:
            flush()
            continue
        if BULLET_PATTERN.match(line):
            flush()
            paragraphs.append(line)
            continue

        if current and current[-1].endswith('-') and line[:1].islower():
            current[-1] = current[-1][:-1] + line
        else:
            current.append(line)

    flush()
    return paragraphs


def _split_long_paragraph(paragraph, target_length=520):
    """Split long evidence into sentence groups while keeping sentences intact."""
    if len(paragraph) <= target_length or BULLET_PATTERN.match(paragraph):
        return [paragraph]

    sentences = SENTENCE_BOUNDARY.split(paragraph)
    if len(sentences) == 1:
        return [
            paragraph[start:start + target_length].strip()
            for start in range(0, len(paragraph), target_length)
            if paragraph[start:start + target_length].strip()
        ]

    groups = []
    current = []
    current_length = 0
    for sentence in sentences:
        added_length = len(sentence) + (1 if current else 0)
        if current and current_length + added_length > target_length:
            groups.append(' '.join(current))
            current = []
            current_length = 0
        current.append(sentence)
        current_length += added_length
    if current:
        groups.append(' '.join(current))
    return groups


def format_excerpt_text(text):
    """Convert PDF-style line breaks into readable paragraphs and list items."""
    cleaned = str(text or '').replace('\r\n', '\n').replace('\r', '\n')
    blocks = []
    for paragraph in _join_pdf_lines(cleaned.split('\n')):
        blocks.extend(_split_long_paragraph(paragraph))
    return blocks


def _normalise_match_text(text):
    blocks = format_excerpt_text(text)
    return ' '.join(BULLET_PATTERN.sub('', block) for block in blocks).strip()


def _highlight(content, matched_text):
    """Escape untrusted PDF text before adding one controlled mark element."""
    if not matched_text:
        return escape(content)

    normalised_match = _normalise_match_text(matched_text)
    start = content.casefold().find(normalised_match.casefold())
    if start < 0:
        return escape(content)

    end = start + len(normalised_match)
    return escape(content[:start]) + '<mark>' + escape(content[start:end]) + '</mark>' + escape(content[end:])


def excerpt_html(text, matched_text=''):
    blocks = format_excerpt_text(text)
    if not blocks:
        return '<div class="finsight-excerpt"><p>No readable text was extracted.</p></div>'

    rendered = []
    bullet_items = []

    def flush_bullets():
        if bullet_items:
            rendered.append('<ul>' + ''.join(f'<li>{item}</li>' for item in bullet_items) + '</ul>')
            bullet_items.clear()

    for block in blocks:
        if BULLET_PATTERN.match(block):
            bullet_text = BULLET_PATTERN.sub('', block, count=1)
            bullet_items.append(_highlight(bullet_text, matched_text))
        else:
            flush_bullets()
            rendered.append(f'<p>{_highlight(block, matched_text)}</p>')
    flush_bullets()

    return '<div class="finsight-excerpt">' + ''.join(rendered) + '</div>'


def show_excerpt(text, matched_text=''):
    st.markdown(excerpt_html(text, matched_text), unsafe_allow_html=True)


def readable_report_label(item):
    parts = item.key.split('/')
    name = parts[-1].removesuffix('_metadata.json')
    if len(parts) >= 4:
        return f'{parts[-4].replace("-", " ").title()} · {parts[-3]} · {name}'
    return name
