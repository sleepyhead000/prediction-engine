"""Parse Udvash mhtml and PDF exam files into structured question data."""
import base64
import json
import os
import quopri
import re
from pathlib import Path
from bs4 import BeautifulSoup

LOCALAI_URL = os.getenv("LOCALAI_URL", "http://localhost:8000/v1/chat/completions")
LOCALAI_MODEL = os.getenv("LOCALAI_MODEL", "gpt-4o")

# Import the working Bijoy decoder
import sys
sys.path.insert(0, os.path.dirname(__file__))
from bijoy_decoder import decode_bijoy

def extract_bengali_from_html(html):
    """Extract and decode Bengali text from HTML with SutonnyMJ class spans."""
    # Find Bengali class spans (pt-000001*)
    bengali_spans = re.findall(
        r'<span[^>]*class="pt-000001[^"]*"[^>]*>([^<]+)</span>', html
    )
    if not bengali_spans:
        return html

    # Filter to only ASCII characters (Bijoy encoding)
    decoded_parts = []
    for span in bengali_spans:
        bijoy_chars = [c for c in span if ord(c) < 128]
        bijoy_text = ''.join(bijoy_chars)
        if bijoy_text.strip():
            decoded_parts.append(decode_bijoy(bijoy_text))

    return ' '.join(decoded_parts)


def detect_subject_from_questions(questions):
    """Detect subject from question content using keywords."""
    all_text = ' '.join(q.get('question_text', '') for q in questions).lower()
    return _classify_text_subject(all_text)


def detect_subject_from_question(text):
    """Detect subject from a single question's text."""
    return _classify_text_subject(text.lower())


def _classify_text_subject(text):
    """Classify text as Physics, Chemistry, or Math based on keywords."""
    physics_kw = ['force', 'velocity', 'acceleration', 'momentum', 'energy', 'power',
                  'circuit', 'current', 'voltage', 'resistance', 'magnetic', 'optics',
                  'photon', 'atom', 'nucleus', 'বল', 'বেগ', 'ত্বরণ', 'শক্তি',
                  'ক্ষমতা', 'বর্তনী', 'ধারা', 'চৌম্বক', 'আয়না', 'পরমাণু',
                  'kinetic', 'potential', 'work', 'friction', 'gravity', 'wave',
                  'pressure', 'temperature', 'heat', 'thermodynamics', 'entropy']
    chemistry_kw = ['mole', 'atomic', 'bond', 'reaction', 'equilibrium', 'acid', 'base',
                    'organic', 'element', 'compound', 'oxidation', 'reduction',
                    'মোল', 'পরমাণু', 'বন্ধন', 'বিক্রিয়া', 'সাম্যাবস্থা', 'অম্ল', 'ক্ষার',
                    'gas', 'liquid', 'solid', 'crystal', 'solution', 'electrode',
                    'catalyst', 'kinetics', 'haloalkane', 'hydrocarbon', 'polymer']
    math_kw = ['function', 'equation', 'integral', 'derivative', 'matrix', 'vector',
               'probability', 'statistics', 'trigonometry', 'geometry',
               'ফাংশন', 'সমীকরণ', 'যোগজীকরণ', 'অবকলন', 'ম্যাট্রিক্স', 'ভেক্টর',
               'sin', 'cos', 'tan', 'limit', 'continuity', 'differentiability',
               'permutation', 'combination', 'binomial', 'sequence', 'series',
               'circle', 'ellipse', 'parabola', 'hyperbola', 'coordinate']

    scores = {
        'Physics': sum(1 for kw in physics_kw if kw in text),
        'Chemistry': sum(1 for kw in chemistry_kw if kw in text),
        'Math': sum(1 for kw in math_kw if kw in text),
    }

    best = max(scores, key=scores.get)
    if scores[best] > 0:
        return best
    return 'Unknown'


def decode_quoted_printable(raw_bytes: bytes) -> str:
    """Decode quoted-printable bytes to UTF-8 string."""
    try:
        decoded = quopri.decodestring(raw_bytes)
        return decoded.decode("utf-8", errors="replace")
    except Exception:
        # Fallback
        text = raw_bytes.decode("latin-1", errors="replace")
        text = re.sub(r"=\n", "", text)
        def replace_hex(m):
            try:
                return chr(int(m.group(1), 16))
            except ValueError:
                return m.group(0)
        text = re.sub(r"=([0-9A-Fa-f]{2})", replace_hex, text)
        return text


def parse_mhtml(filepath: str) -> dict:
    """Parse a single mhtml file and extract questions."""
    with open(filepath, "rb") as f:
        raw = f.read()

    # Try to decode
    try:
        content = raw.decode("utf-8", errors="replace")
    except Exception:
        content = raw.decode("latin-1", errors="replace")

    # Find the HTML part with question content — work with raw bytes
    # Find all Content-Type: text/html boundaries in the raw bytes
    boundary = b"Content-Type: text/html"
    html_sections = []
    pos = 0
    while True:
        idx = raw.find(boundary, pos)
        if idx == -1:
            break
        # Find the end of headers (double newline)
        header_end = raw.find(b"\r\n\r\n", idx)
        if header_end == -1:
            header_end = raw.find(b"\n\n", idx)
        if header_end == -1:
            pos = idx + 1
            continue
        content_start = header_end + 4
        # Find next Content-Type boundary or end of file
        next_boundary = raw.find(b"Content-Type:", content_start)
        if next_boundary == -1:
            section = raw[content_start:]
        else:
            section = raw[content_start:next_boundary]
        html_sections.append(section)
        pos = idx + 1

    if not html_sections:
        return {"file": filepath, "questions": [], "error": "No HTML content found"}

    # Pick the section with question content
    html = b""
    for section in html_sections:
        if b"questionBlock" in section or b"Question 1" in section:
            html = section
            break
    if not html:
        html = html_sections[-1]

    # Decode quoted-printable from raw bytes
    html = decode_quoted_printable(html)

    # Extract metadata from the HTML
    set_info = ""
    set_match = re.search(r"Master Set:\s*(\d+)", html)
    if set_match:
        set_info = f"Master Set: {set_match.group(1)}"

    # Determine subject and exam type from filename
    fname = os.path.basename(filepath)
    subject = "Unknown"
    exam_type = "Unknown"
    set_num = 0

    if "Physics" in filepath or fname.upper().startswith("P"):
        subject = "Physics"
    elif "Chemistry" in filepath or fname.upper().startswith("C"):
        subject = "Chemistry"
    elif "Math" in filepath or fname.upper().startswith("M"):
        subject = "Math"

    if "MCQ" in fname or "mcq" in fname.lower():
        exam_type = "MCQ"
    elif "written" in fname.lower() or "WRITTEN" in fname:
        exam_type = "Written"
    elif "weekly" in fname.lower():
        exam_type = "Weekly"

    if set_match:
        set_num = int(set_match.group(1))

    # Extract questions using regex on decoded HTML
    questions = extract_questions_regex(html)

    # For weekly/mixed files, detect subject per question
    if exam_type == "Weekly":
        for q in questions:
            q["subject"] = detect_subject_from_question(q.get("question_text", ""))
            q["exam_type"] = exam_type
            q["set_number"] = set_num
            q["source_file"] = os.path.basename(filepath)
        # Set file-level subject to dominant subject among questions
        if questions:
            subject_counts = {}
            for q in questions:
                s = q.get("subject", "Unknown")
                if s != "Unknown":
                    subject_counts[s] = subject_counts.get(s, 0) + 1
            if subject_counts:
                subject = max(subject_counts, key=subject_counts.get)
    else:
        # For subject-specific files, use filename detection
        if subject == "Unknown" and questions:
            subject = detect_subject_from_questions(questions)
        # Written exam files are always subject-specific from filename
        if exam_type == "Written" and subject == "Unknown":
            # Try harder to detect from filename patterns
            if fname.upper().startswith("P") or "physics" in fname.lower():
                subject = "Physics"
            elif fname.upper().startswith("C") or "chemistry" in fname.lower():
                subject = "Chemistry"
            elif fname.upper().startswith("M") or "math" in fname.lower():
                subject = "Math"
        for q in questions:
            q["subject"] = subject
            q["exam_type"] = exam_type
            q["set_number"] = set_num
            q["source_file"] = os.path.basename(filepath)

    return {
        "file": filepath,
        "set_info": set_info,
        "subject": subject,
        "exam_type": exam_type,
        "set_number": set_num,
        "question_count": len(questions),
        "questions": questions,
    }


def parse_pdf(filepath: str) -> dict:
    """Parse a PDF exam file — renders pages to images, sends to LocalAI for extraction."""
    import pymupdf

    fname = os.path.basename(filepath)
    subject = "Unknown"
    exam_type = "Unknown"
    set_num = 0

    # Quick check if LocalAI is available
    try:
        import requests
        requests.get(LOCALAI_URL.replace('/v1/chat/completions', '/health'), timeout=2)
    except Exception:
        return {"file": filepath, "questions": [], "error": "LocalAI not available for PDF extraction", "question_count": 0}

    # Detect subject from filename
    if "Physics" in filepath or fname.upper().startswith("P"):
        subject = "Physics"
    elif "Chemistry" in filepath or fname.upper().startswith("C"):
        subject = "Chemistry"
    elif "Math" in filepath or fname.upper().startswith("M"):
        subject = "Math"

    # Detect exam type from filename/path
    if "diff" in fname.lower():
        exam_type = "Diff Set"
    elif "bank" in filepath.lower():
        exam_type = "Question Bank"
    elif "weekly" in fname.lower():
        exam_type = "Weekly"
    elif "MCQ" in fname:
        exam_type = "MCQ"
    elif "written" in fname.lower():
        exam_type = "Written"

    # Extract set number from filename
    set_match = re.search(r"(\d+)", fname)
    if set_match:
        set_num = int(set_match.group(1))

    try:
        doc = pymupdf.open(filepath)
    except Exception as e:
        return {"file": filepath, "questions": [], "error": f"Cannot open PDF: {e}"}

    all_questions = []
    pages_processed = 0

    for page_num in range(len(doc)):
        page = doc[page_num]

        # Render page to image
        pix = page.get_pixmap(dpi=200)
        img_bytes = pix.tobytes("png")
        img_b64 = base64.b64encode(img_bytes).decode("ascii")

        # Send to LocalAI for extraction
        questions = extract_questions_from_image(img_b64, subject, page_num + 1)
        all_questions.extend(questions)
        pages_processed += 1

    doc.close()

    # Add metadata to each question
    for q in all_questions:
        q["subject"] = subject
        q["exam_type"] = exam_type
        q["set_number"] = set_num
        q["source_file"] = fname

    return {
        "file": filepath,
        "set_info": f"PDF {pages_processed} pages",
        "subject": subject,
        "exam_type": exam_type,
        "set_number": set_num,
        "question_count": len(all_questions),
        "questions": all_questions,
    }


def extract_questions_from_image(img_b64: str, subject: str, page_num: int) -> list[dict]:
    """Send an image to LocalAI and extract questions from it."""
    import requests

    prompt = (
        "You are an exam question extractor for {subject} exams.\n"
        "This is page {page_num} of a PDF exam paper.\n"
        "\n"
        "IMPORTANT: The text is in Bengali. Extract the text EXACTLY as written.\n"
        "Preserve all Bengali characters. Math expressions stay as-is.\n"
        "\n"
        "Extract ALL questions from this image. For each question, return:\n"
        "- question_number: the question number (1, 2, 3, etc.)\n"
        "- question_text: the full question text in the ORIGINAL LANGUAGE\n"
        "- options: array of objects with letter and text (only for MCQ)\n"
        "- has_options: true if it's a multiple choice question\n"
        "\n"
        "Return ONLY a JSON array of questions. No other text.\n"
        "If you cannot read a question clearly, include it with your best attempt.\n"
        "If there are no questions on this page, return an empty array [].\n"
    ).format(subject=subject, page_num=page_num)

    try:
        resp = requests.post(
            LOCALAI_URL,
            json={
                "model": LOCALAI_MODEL,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:image/png;base64,{img_b64}"},
                            },
                        ],
                    }
                ],
                "temperature": 0.1,
                "max_tokens": 4000,
            },
            timeout=30,
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]

        # Extract JSON from response
        json_match = re.search(r"\[.*\]", content, re.DOTALL)
        if json_match:
            questions = json.loads(json_match.group())
            # Normalize format
            for q in questions:
                if "options" not in q:
                    q["options"] = []
                if "has_options" not in q:
                    q["has_options"] = len(q["options"]) > 0
            return questions
    except Exception:
        pass

    return []


def extract_questions_regex(html: str) -> list[dict]:
    """Extract questions using regex since html.parser fails on large malformed HTML."""
    questions = []

    # Split by questionBlock markers
    blocks = re.split(r'<div class="row questionBlock">', html)

    for block in blocks[1:]:  # Skip first (before first question)
        q = {}

        # Extract question number
        serial_match = re.search(r'<span>Question\s+(\d+)\s*</span>', block)
        q["question_number"] = int(serial_match.group(1)) if serial_match else 0

        # Extract question text - get everything between questionText div and next major div
        q_text_match = re.search(
            r'<div class="questionText"[^>]*>(.*?)</div>\s*(?:</div>\s*)*(?:<div class="row questionOptions">|$)',
            block, re.DOTALL
        )
        if q_text_match:
            raw_text = q_text_match.group(1)
            q["question_text"] = html_to_text(raw_text)
        else:
            # Fallback: try simpler pattern
            q_text_match = re.search(
                r'<div class="questionText"[^>]*>(.*?)</div>',
                block, re.DOTALL
            )
            if q_text_match:
                raw_text = q_text_match.group(1)
                q["question_text"] = html_to_text(raw_text)
            else:
                q["question_text"] = ""

        # Extract options
        options = []
        opt_pattern = re.compile(
            r'<span class="input-group-text">([A-D])</span>.*?'
            r'<div class="[^"]*questionTable[^"]*">(.*?)</div>',
            re.DOTALL
        )
        for m in opt_pattern.finditer(block):
            letter = m.group(1)
            opt_html = m.group(2)
            opt_text = html_to_text(opt_html)
            options.append({"letter": letter, "text": opt_text})

        q["options"] = options

        # Lenient fallback: if has_options but empty options, try simpler pattern
        if not options:
            lenient_pattern = re.compile(
                r'<span[^>]*>\s*([A-D])\s*</span>.*?<div[^>]*>(.*?)</div>',
                re.DOTALL
            )
            for m in lenient_pattern.finditer(block):
                letter = m.group(1)
                if letter in ('A', 'B', 'C', 'D'):
                    opt_html = m.group(2)
                    opt_text = html_to_text(opt_html)
                    if opt_text.strip():
                        options.append({"letter": letter, "text": opt_text})
            if options:
                q["options"] = options

        questions.append(q)

    return questions


def html_to_text(html_str: str) -> str:
    """Convert HTML snippet to plain text, extracting MathJax and decoding Bengali."""
    parts = []

    # Extract MathJax math from mjx-assistive-mml (contains readable MathML)
    for m in re.finditer(r'<mjx-assistive-mml[^>]*>(.*?)</mjx-assistive-mml>', html_str, re.DOTALL):
        math_ml = m.group(1)
        math_text = mathml_to_text_simple(math_ml)
        if math_text:
            # Replace the entire mjx-container with the math text
            html_str = html_str.replace(m.group(0), f" [math:{math_text}] ")

    # First extract Bengali text from SutonnyMJ class spans
    bengali_spans = re.findall(
        r'<span[^>]*class="pt-000001[^"]*"[^>]*>([^<]+)</span>', html_str
    )

    # Remove HTML tags
    text = re.sub(r'<[^>]+>', ' ', html_str)
    # Decode HTML entities
    text = text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    text = text.replace("&nbsp;", " ").replace("&#39;", "'").replace("&quot;", '"')
    # Clean up whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    # Remove stray = at line ends (QP artifacts)
    text = re.sub(r'=\s*$', '', text, flags=re.MULTILINE)

    # Now decode Bijoy Bengali text
    # Filter to only ASCII characters for Bijoy decoding
    bijoy_chars = [c for c in text if ord(c) < 128]
    bijoy_text = ''.join(bijoy_chars)

    # Decode Bijoy
    decoded = decode_bijoy(bijoy_text)

    return decoded


def mathml_to_text_simple(mathml: str) -> str:
    """Simple MathML to text conversion."""
    parts = []
    # Extract mn (numbers), mi (identifiers), mo (operators)
    for tag in ["mn", "mi", "mo"]:
        for m in re.finditer(rf'<{tag}[^>]*>(.*?)</{tag}>', mathml, re.DOTALL):
            val = re.sub(r'<[^>]+>', '', m.group(1)).strip()
            if val:
                parts.append(val)

    # Handle msup (superscripts)
    for m in re.finditer(r'<msup[^>]*>(.*?)</msup>', mathml, re.DOTALL):
        inner = m.group(1)
        base = re.search(r'<mn[^>]*>(.*?)</mn>', inner)
        sup = re.search(r'<mo[^>]*>(.*?)</mo>', inner) or re.search(r'<mn[^>]*>(.*?)</mn>', inner)
        if base and sup:
            b = re.sub(r'<[^>]+>', '', base.group(1)).strip()
            s = re.sub(r'<[^>]+>', '', sup.group(1)).strip()
            parts.append(f"{b}^{s}")

    # Handle msqrt (square roots)
    for m in re.finditer(r'<msqrt[^>]*>(.*?)</msqrt>', mathml, re.DOTALL):
        inner = m.group(1)
        val = re.search(r'<mn[^>]*>(.*?)</mn>', inner) or re.search(r'<mi[^>]*>(.*?)</mi>', inner)
        if val:
            v = re.sub(r'<[^>]+>', '', val.group(1)).strip()
            parts.append(f"sqrt({v})")

    return " ".join(parts)


def parse_all_exams(base_dir: str) -> list[dict]:
    """Parse all mhtml and PDF files in the directory tree."""
    results = []
    base = Path(base_dir)

    for mhtml in base.rglob("*.mhtml"):
        try:
            result = parse_mhtml(str(mhtml))
            results.append(result)
        except Exception as e:
            results.append({"file": str(mhtml), "error": str(e), "questions": []})

    for pdf in base.rglob("*.pdf"):
        try:
            result = parse_pdf(str(pdf))
            results.append(result)
        except Exception as e:
            results.append({"file": str(pdf), "error": str(e), "questions": []})

    return results


def save_parsed(data: list[dict], output_path: str):
    """Save parsed data to JSON."""
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    import sys

    base = sys.argv[1] if len(sys.argv) > 1 else "."
    print(f"Parsing exams from: {base}")

    results = parse_all_exams(base)

    total_q = sum(r.get("question_count", 0) for r in results)
    print(f"Parsed {len(results)} files, {total_q} questions total")

    for r in results:
        if r.get("error"):
            print(f"  ERROR: {r['file']}: {r['error']}")
        else:
            print(f"  {r['subject']} {r['exam_type']} Set {r['set_number']}: {r['question_count']} questions")

    output = os.path.join(base, "parsed_questions.json")
    save_parsed(results, output)
    print(f"\nSaved to: {output}")
