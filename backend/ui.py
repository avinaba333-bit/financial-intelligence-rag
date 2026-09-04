"""Shared presentation helpers. Never interpret document text as HTML/Markdown."""

from html import escape
import re

import streamlit as st


BULLET_PATTERN = re.compile(r"^(?:[-•▪◦*]|\d+[.)])\s+")
SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9₹$])")


def apply_style():
    st.markdown('''<style>
    :root {
      --finsight-navy: #102b42;
      --finsight-teal: #137565;
      --finsight-teal-light: #32b49c;
      --finsight-soft: rgba(32,154,132,.10);
      --finsight-line: rgba(128,128,128,.22);
    }
    html, body, .stApp {
      font-family: Inter, ui-sans-serif, -apple-system, BlinkMacSystemFont,
        "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      -webkit-font-smoothing: antialiased;
      text-rendering: optimizeLegibility;
    }
    [data-testid="stAppViewContainer"] {background-image:
      radial-gradient(circle at 92% 4%, rgba(32,154,132,.055), transparent 24rem);}
    [data-testid="stHeader"] {background: transparent;}
    .block-container {
      width: min(100%, 1320px);
      max-width: 1320px;
      padding: clamp(1rem, 2.2vw, 2.25rem) clamp(1rem, 2.8vw, 2.75rem) 3rem;
    }
    h1, h2, h3 {letter-spacing: -.025em;}
    p, li, label, [data-testid="stCaptionContainer"] {line-height: 1.6;}
    .finsight-hero {
      position: relative;
      overflow: hidden;
      padding: clamp(1.35rem, 3vw, 2.25rem) clamp(1.25rem, 3.4vw, 2.7rem);
      border-radius: 22px;
      background: linear-gradient(120deg,var(--finsight-navy),#12495a 52%,var(--finsight-teal));
      box-shadow: 0 18px 45px rgba(5,30,43,.16);
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
      background: rgba(255,255,255,.08);
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
      color: #a4e2d0;
    }
    [data-testid="stSidebar"] {
      border-right: 1px solid var(--finsight-line);
      min-width: 330px;
      max-width: 330px;
    }
    [data-testid="stSidebar"] [data-testid="stVerticalBlock"] {gap: .82rem;}
    [data-testid="stSidebarNav"] ul {gap: .22rem;}
    [data-testid="stSidebarNav"] li {margin-bottom: .12rem;}
    [data-testid="stSidebarNav"] span {line-height: 1.45;}
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
      border-radius: 16px;
      background: color-mix(in srgb, var(--secondary-background-color) 72%, transparent);
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
      border-color: var(--finsight-teal-light);
      box-shadow: 0 8px 22px rgba(19,117,101,.12);
      transform: translateY(-1px);
    }
    [data-testid="stTextInputRootElement"],
    [data-testid="stTextAreaRootElement"],
    [data-baseweb="select"] > div,
    [data-testid="stFileUploaderDropzone"] {
      border-radius: 12px;
    }
    [data-testid="stExpander"] {
      border-color: var(--finsight-line);
      border-radius: 14px;
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
      border-radius: 16px;
      padding: .3rem .5rem;
      margin-bottom: .75rem;
      box-shadow: 0 5px 18px rgba(0,0,0,.035);
    }
    [data-testid="stChatInput"] {
      border: 1px solid rgba(32,154,132,.42);
      border-radius: 16px;
      box-shadow: 0 8px 26px rgba(19,117,101,.09);
    }
    [data-testid="stDataFrame"] {
      border: 1px solid var(--finsight-line);
      border-radius: 14px;
      overflow: hidden;
    }
    [data-testid="stPlotlyChart"] {
      width: 100%;
      min-width: 0;
    }
    .finsight-excerpt {overflow-wrap: anywhere; line-height: 1.75;
      border-left: 3px solid #209a84; padding: .9rem 1.05rem; margin: .5rem 0 1rem;
      background: var(--finsight-soft); border-radius: 0 12px 12px 0;}
    .finsight-excerpt p {margin: 0 0 .85rem; text-align: left;}
    .finsight-excerpt p:last-child {margin-bottom: 0;}
    .finsight-excerpt ul {margin: .2rem 0 .85rem; padding-left: 1.35rem;}
    .finsight-excerpt li {margin: .25rem 0;}
    .finsight-excerpt mark {background: #ffedaa; color: #192733; border-radius: 3px;
      padding: 0 .08rem;}
    @media (max-width: 900px) {
      .block-container {padding: 1rem 1rem 2.5rem;}
      [data-testid="stHorizontalBlock"] {gap: .8rem;}
      [data-testid="stMetric"] {min-height: 92px; padding: .8rem .9rem;}
    }
    @media (max-width: 640px) {
      [data-testid="stSidebar"] {min-width: min(88vw, 330px); max-width: min(88vw, 330px);}
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
