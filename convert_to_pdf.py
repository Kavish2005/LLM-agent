"""
Converts report.md + prompt_design.md to report.pdf in IEEE two-column format.
Run: python convert_to_pdf.py
"""

import markdown
import os
from weasyprint import HTML, CSS

BASE = os.path.dirname(os.path.abspath(__file__))
REPORT_MD      = os.path.join(BASE, "report.md")
PROMPT_DESIGN_MD = os.path.join(BASE, "prompt_design.md")
REPORT_PDF     = os.path.join(BASE, "report.pdf")

# ── IEEE-style CSS ──────────────────────────────────────────────────────────

IEEE_CSS = """
@page {
    size: A4;
    margin: 1.85cm 1.6cm 2.0cm 1.6cm;
    @bottom-center {
        content: counter(page);
        font-family: 'Times New Roman', Times, serif;
        font-size: 8pt;
        color: #555;
    }
}

/* ── Base typography ── */
body {
    font-family: 'Times New Roman', Times, serif;
    font-size: 9.5pt;
    line-height: 1.3;
    color: #000;
    text-align: justify;
    hyphens: auto;
}

/* ── Two-column body ── */
.two-col {
    column-count: 2;
    column-gap: 0.55cm;
    column-fill: balance;
}

/* ── Paper header (spans full width above columns) ── */
.paper-header {
    text-align: center;
    margin-bottom: 10pt;
}

.paper-header h1 {
    font-size: 18pt;
    font-weight: bold;
    line-height: 1.2;
    margin: 0 0 6pt 0;
    text-align: center;
    color: #000;
}

.authors {
    font-size: 10pt;
    font-style: italic;
    margin-bottom: 8pt;
    color: #222;
}

.abstract-block {
    margin: 0 1.2cm 0 1.2cm;
    font-size: 9pt;
    line-height: 1.3;
    text-align: justify;
    border-top: 1px solid #000;
    border-bottom: 1px solid #000;
    padding: 5pt 0;
}

.abstract-label {
    font-weight: bold;
    font-style: italic;
}

/* ── Section headings (Roman numeral style) ── */
h2 {
    font-size: 9.5pt;
    font-weight: bold;
    text-align: center;
    text-transform: uppercase;
    letter-spacing: 0.03em;
    margin: 8pt 0 3pt 0;
    page-break-after: avoid;
}

/* ── Subsection headings ── */
h3 {
    font-size: 9.5pt;
    font-weight: bold;
    font-style: italic;
    margin: 6pt 0 2pt 0;
    page-break-after: avoid;
}

/* ── Body paragraphs ── */
p {
    margin: 0 0 4pt 0;
    orphans: 3;
    widows: 3;
}

/* ── Table ── */
.table-caption {
    font-weight: bold;
    font-size: 8.5pt;
    text-align: center;
    margin: 6pt 0 2pt 0;
    letter-spacing: 0.04em;
}

table {
    width: 100%;
    border-collapse: collapse;
    font-size: 8pt;
    margin-bottom: 5pt;
}

th {
    background: #000;
    color: #fff;
    padding: 2pt 4pt;
    text-align: left;
    font-weight: bold;
}

td {
    padding: 2pt 4pt;
    border-bottom: 0.5px solid #ccc;
    vertical-align: top;
}

tr:nth-child(even) td {
    background: #f5f5f5;
}

/* ── Code blocks (for prompt design appendix) ── */
pre {
    font-family: 'Courier New', monospace;
    font-size: 7.5pt;
    line-height: 1.25;
    background: #f8f8f8;
    border-left: 2pt solid #555;
    padding: 4pt 6pt;
    margin: 3pt 0 5pt 0;
    white-space: pre-wrap;
    word-wrap: break-word;
}

code {
    font-family: 'Courier New', monospace;
    font-size: 8pt;
    background: #f0f0f0;
    padding: 0 2pt;
}

/* ── Horizontal rule (section divider) ── */
hr {
    border: none;
    border-top: 1px solid #000;
    margin: 8pt 0;
}

/* ── References ── */
ol, ul {
    margin: 0 0 4pt 0;
    padding-left: 16pt;
}

li {
    margin-bottom: 3pt;
    font-size: 9pt;
    line-height: 1.3;
}

/* ── Strong / em ── */
strong { font-weight: bold; }
em     { font-style: italic; }

/* ── Appendix page break ── */
.appendix-break {
    page-break-before: always;
}

/* ── Appendix headings ── */
.appendix-title {
    font-size: 14pt;
    font-weight: bold;
    text-align: center;
    margin-bottom: 8pt;
    column-span: all;
}
"""

# ── Markdown extensions ─────────────────────────────────────────────────────

MD_EXTENSIONS = ["extra", "sane_lists", "tables"]


def md_to_html(text: str) -> str:
    return markdown.markdown(text, extensions=MD_EXTENSIONS)


# ── Build combined HTML ─────────────────────────────────────────────────────

def build_html() -> str:
    report_md = open(REPORT_MD, encoding="utf-8").read()
    prompt_md = open(PROMPT_DESIGN_MD, encoding="utf-8").read()

    # Split report into header block and body (everything after the header div)
    # The header is wrapped in <div class="paper-header"> in the markdown
    report_html_raw = md_to_html(report_md)

    # Prompt design: skip the H1 title (we'll render our own appendix header)
    prompt_lines = prompt_md.split("\n")
    prompt_body_md = "\n".join(
        line for line in prompt_lines
        if not line.startswith("# Prompt Design Explanation")
    )
    prompt_html = md_to_html(prompt_body_md)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Investment Research Agent — IEEE Report</title>
</head>
<body>

<!-- ── Main report (header full-width, body two-column) ── -->
{report_html_raw}

<!-- ── Appendix: Prompt Design ── -->
<div class="appendix-break"></div>
<div class="appendix-title">Appendix: Prompt Design Explanation</div>
<div class="two-col">
{prompt_html}
</div>

</body>
</html>"""
    return html


# ── Post-process: wrap body content in two-col div ──────────────────────────

def wrap_body_in_columns(html: str) -> str:
    """
    Everything after </div> (closing the paper-header) and before the
    appendix break goes into a .two-col div.
    """
    HEADER_END = "</div>"   # last closing div of .paper-header
    APPENDIX_START = '<div class="appendix-break">'

    # Find the boundary after the paper-header block
    # The paper-header div is the first big block; its closing </div> ends the header
    # We look for the THIRD </div> (paper-header > authors > abstract-block each close)
    idx = 0
    for _ in range(3):
        idx = html.find(HEADER_END, idx) + len(HEADER_END)

    before_cols = html[:idx]
    rest = html[idx:]

    # Split rest at appendix break
    app_idx = rest.find(APPENDIX_START)
    if app_idx == -1:
        body_content = rest
        after_appendix_break = ""
    else:
        body_content = rest[:app_idx]
        after_appendix_break = rest[app_idx:]

    wrapped = (
        before_cols
        + '\n<div class="two-col">\n'
        + body_content
        + "\n</div>\n"
        + after_appendix_break
    )
    return wrapped


# ── Main ────────────────────────────────────────────────────────────────────

def convert():
    raw_html = build_html()
    final_html = wrap_body_in_columns(raw_html)

    HTML(string=final_html).write_pdf(
        REPORT_PDF,
        stylesheets=[CSS(string=IEEE_CSS)],
    )

    size_kb = os.path.getsize(REPORT_PDF) / 1024
    print(f"PDF written → {REPORT_PDF}  ({size_kb:.0f} KB)")


if __name__ == "__main__":
    convert()
