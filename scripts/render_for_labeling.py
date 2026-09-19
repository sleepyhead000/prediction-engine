"""Render exam questions as browser-viewable HTML for human labeling.

Usage:
    python scripts/render_for_labeling.py [--output-dir ground_truth/labeling]

Generates one HTML file per exam with:
- Original page styling
- Question text with MathJax rendering
- Input fields for subject, concept_id, difficulty
- Pre-filled qids for easy copy-paste into labels_v1.jsonl
"""
from __future__ import annotations

import argparse
import json
import quopri
import re
import sys
from pathlib import Path

from lxml import html as lxml_html


HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="bn">
<head>
<meta charset="UTF-8">
<title>Labeling: {filename}</title>
<script>
MathJax = {{
  tex: {{ inlineMath: [['\\\\(', '\\\\)']] }},
  svg: {{ fontCache: 'global' }}
}};
</script>
<script src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-svg.js" async></script>
<style>
body {{ font-family: 'SolaimanLipi', 'Kalpurush', sans-serif; max-width: 900px; margin: 0 auto; padding: 20px; background: #fafafa; }}
.question {{ background: white; border: 1px solid #ddd; border-radius: 8px; padding: 20px; margin: 20px 0; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
.question-header {{ font-weight: bold; color: #333; margin-bottom: 10px; font-size: 1.1em; }}
.qid {{ font-family: monospace; font-size: 0.85em; color: #888; }}
.options {{ margin: 10px 0; padding-left: 20px; }}
.option {{ margin: 5px 0; }}
.option-label {{ font-weight: bold; color: #555; }}
.label-form {{ margin-top: 15px; padding: 15px; background: #f5f5f5; border-radius: 6px; }}
.label-form label {{ display: block; margin: 8px 0 4px; font-weight: bold; font-size: 0.9em; }}
.label-form input, .label-form select {{ width: 100%; padding: 6px; border: 1px solid #ccc; border-radius: 4px; box-sizing: border-box; }}
.label-form .row {{ display: flex; gap: 12px; }}
.label-form .row > div {{ flex: 1; }}
.copy-btn {{ background: #4CAF50; color: white; border: none; padding: 4px 12px; border-radius: 4px; cursor: pointer; font-size: 0.85em; margin-top: 10px; }}
.copy-btn:hover {{ background: #45a049; }}
h1 {{ color: #333; border-bottom: 2px solid #4CAF50; padding-bottom: 10px; }}
.raw-text {{ background: #fff3cd; padding: 8px; border-radius: 4px; font-size: 0.9em; margin: 5px 0; font-family: monospace; white-space: pre-wrap; word-break: break-all; }}
</style>
</head>
<body>
<h1>{filename}</h1>
<p>Exam kind: {exam_kind} | Subject: {subject} | Questions: {n_questions}</p>
{questions_html}
<script>
document.querySelectorAll('.copy-btn').forEach(btn => {{
  btn.addEventListener('click', () => {{
    navigator.clipboard.writeText(btn.dataset.qid);
    btn.textContent = 'Copied!';
    setTimeout(() => btn.textContent = 'Copy QID', 1500);
  }});
}});
</script>
</body>
</html>
"""

QUESTION_TEMPLATE = """\
<div class="question" id="q{q_index}">
  <div class="question-header">Question {q_index}</div>
  <div class="qid">QID: {qid} <button class="copy-btn" data-qid="{qid}">Copy QID</button></div>
  <div class="raw-text">{question_text}</div>
  <div class="options">
    {options_html}
  </div>
  <div class="label-form">
    <div class="row">
      <div>
        <label>Subject</label>
        <select name="subject">
          <option value="">-- select --</option>
          <option value="Physics">Physics</option>
          <option value="Chemistry">Chemistry</option>
          <option value="Math">Math</option>
        </select>
      </div>
      <div>
        <label>Difficulty (1-5)</label>
        <input type="number" name="difficulty" min="1" max="5" value="3">
      </div>
    </div>
    <label>Concept ID (e.g. phy.mech.lever_rider_balance)</label>
    <input type="text" name="concept_id" placeholder="subject.topic.specific_concept">
  </div>
</div>
"""


def decode_mhtml(filepath: Path) -> str:
    """Extract and decode the HTML body from an .mhtml file."""
    raw = filepath.read_bytes()
    boundary = b"Content-Type: text/html"
    pos = 0
    last_html = b""
    while True:
        idx = raw.find(boundary, pos)
        if idx == -1:
            break
        header_end = raw.find(b"\r\n\r\n", idx)
        if header_end == -1:
            pos = idx + 1
            continue
        content_start = header_end + 4
        next_boundary = raw.find(b"Content-Type:", content_start)
        section = raw[content_start:next_boundary] if next_boundary != -1 else raw[content_start:]
        if b"questionBlock" in section:
            return quopri.decodestring(section).decode("utf-8", errors="replace")
        last_html = section
        pos = idx + 1
    if last_html:
        return quopri.decodestring(last_html).decode("utf-8", errors="replace")
    return ""


def extract_questions(html_content: str, source_file: str) -> list[dict]:
    """Extract questions from HTML for labeling."""
    results = []
    try:
        tree = lxml_html.fromstring(html_content)
    except Exception:
        return results

    blocks = tree.xpath('//div[contains(@class, "questionBlock")]')
    for block in blocks:
        serial_el = block.xpath('.//div[@class="serial"]//span')
        q_num = 0
        if serial_el:
            m = re.search(r"(\d+)", serial_el[0].text_content())
            if m:
                q_num = int(m.group(1))

        # Get question text
        q_text_el = block.xpath('.//div[@class="questionText"]')
        q_text = q_text_el[0].text_content().strip() if q_text_el else ""

        # Get options
        options = []
        opt_divs = block.xpath('.//div[contains(@class, "questionOption")]')
        for opt_div in opt_divs:
            letter_el = opt_div.xpath('.//span[@class="input-group-text"]')
            letter = letter_el[0].text_content().strip() if letter_el else "?"
            # Get option text from questionTable
            table_el = opt_div.xpath('.//div[contains(@class, "questionTable")]')
            opt_text = table_el[0].text_content().strip() if table_el else ""
            options.append({"letter": letter, "text": opt_text})

        qid = f"sha1:{source_file}:q{q_num}"
        results.append({
            "q_index": q_num,
            "qid": qid,
            "question_text": q_text,
            "options": options,
        })
    return results


def determine_exam_kind(filename: str) -> str:
    """Infer exam kind from filename."""
    lower = filename.lower()
    if "weekly" in lower:
        return "weekly"
    if "mcq" in lower:
        return "daily_mcq"
    if "written" in lower:
        return "daily_written"
    return "unknown"


def determine_subject(filepath: str) -> str:
    """Infer subject from path."""
    lower = filepath.lower()
    if "physics" in lower or "p1" in lower or "p2" in lower:
        return "Physics"
    if "chemistry" in lower or "c1" in lower or "c2" in lower:
        return "Chemistry"
    if "math" in lower or "m1" in lower or "m2" in lower:
        return "Math"
    return "Unknown"


def main():
    parser = argparse.ArgumentParser(description="Render exam questions for human labeling")
    parser.add_argument(
        "--output-dir", "-o",
        default="ground_truth/labeling",
        help="Output directory for HTML files",
    )
    parser.add_argument(
        "sources",
        nargs="?",
        default="sources",
        help="Directory containing .mhtml files",
    )
    args = parser.parse_args()

    sources_dir = Path(args.sources)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    mhtml_files = sorted(sources_dir.rglob("*.mhtml"))
    if not mhtml_files:
        print(f"No .mhtml files found in {sources_dir}")
        sys.exit(1)

    queue = []
    for i, f in enumerate(mhtml_files):
        print(f"  Processing {f.name}...", end=" ", flush=True)
        html = decode_mhtml(f)
        if not html:
            print("(no HTML found)")
            continue

        questions = extract_questions(html, f.name)
        rel_path = str(f.relative_to(sources_dir))

        # Build question HTML
        q_html_parts = []
        for q in questions:
            options_html = ""
            for opt in q["options"]:
                options_html += f'<div class="option"><span class="option-label">{opt["letter"]})</span> {opt["text"]}</div>\n'

            q_html_parts.append(QUESTION_TEMPLATE.format(
                q_index=q["q_index"],
                qid=q["qid"],
                question_text=q["question_text"],
                options_html=options_html,
            ))

        exam_html = HTML_TEMPLATE.format(
            filename=f.name,
            exam_kind=determine_exam_kind(f.name),
            subject=determine_subject(rel_path),
            n_questions=len(questions),
            questions_html="\n".join(q_html_parts),
        )

        out_file = output_dir / f"exam_{i:03d}_{f.stem}.html"
        out_file.write_text(exam_html, encoding="utf-8")
        print(f"{len(questions)} questions -> {out_file.name}")

        for q in questions:
            queue.append({
                "qid": q["qid"],
                "source_file": rel_path,
                "q_index": q["q_index"],
                "subject": "",
                "concept_id": "",
                "difficulty_1_5": 3,
                "question_text_bn": "",
                "labelled_by": "",
                "labelled_at": "",
            })

    # Write labeling queue
    queue_file = output_dir / "labeling_queue.jsonl"
    with open(queue_file, "w", encoding="utf-8") as f:
        for item in queue:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")

    print(f"\nRendered {len(mhtml_files)} exams to {output_dir}/")
    print(f"Labeling queue: {queue_file} ({len(queue)} questions)")
    print("Open the HTML files in a browser to read questions, then fill in labels.")


if __name__ == "__main__":
    main()
