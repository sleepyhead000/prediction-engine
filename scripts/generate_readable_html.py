"""Generate screenshots of MHTML exam pages for human labeling.

Usage:
    python scripts/generate_screenshots.py [--output-dir ground_truth/screenshots]

Extracts the full HTML (with CSS) from each MHTML and saves as standalone
HTML files that render correctly with Bijoy fonts. Also generates PNG
screenshots if playwright is available.
"""
from __future__ import annotations

import argparse
import quopri
import re
import sys
from pathlib import Path


def extract_full_mhtml(filepath: Path) -> str:
    """Extract the complete HTML part from an MHTML file, preserving CSS."""
    raw = filepath.read_bytes()

    # Find HTML section
    boundary = b"Content-Type: text/html"
    pos = 0
    html_bytes = b""

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
        if b"questionBlock" in section or b"questionText" in section:
            html_bytes = section
            break
        pos = idx + 1

    if not html_bytes:
        return ""

    # Decode quoted-printable
    decoded = quopri.decodestring(html_bytes).decode("utf-8", errors="replace")

    # Extract CSS from cid: stylesheet links
    # Find all CSS content-type sections
    css_parts = []
    css_boundary = b"Content-Type: text/css"
    pos = 0
    while True:
        idx = raw.find(css_boundary, pos)
        if idx == -1:
            break
        header_end = raw.find(b"\r\n\r\n", idx)
        if header_end == -1:
            pos = idx + 1
            continue
        content_start = header_end + 4
        # Find end of this part (next boundary or end)
        next_part = raw.find(b"\r\n------", content_start)
        if next_part == -1:
            next_part = raw.find(b"\n------", content_start)
        if next_part == -1:
            css_section = raw[content_start:]
        else:
            css_section = raw[content_start:next_part]

        try:
            css_text = quopri.decodestring(css_section).decode("utf-8", errors="replace")
            css_parts.append(css_text)
        except Exception:
            pass
        pos = idx + 1

    # Replace cid: CSS links with inline <style>
    combined_css = "\n".join(css_parts)
    if combined_css:
        # Remove all cid: link tags and replace with inline style
        decoded = re.sub(
            r'<link[^>]*href="cid:[^"]*"[^>]*/?\s*>',
            "",
            decoded,
        )
        # Inject combined CSS before </head>
        if "</head>" in decoded:
            decoded = decoded.replace(
                "</head>",
                f"<style>\n{combined_css}\n</style>\n</head>",
            )
        else:
            decoded = f"<style>\n{combined_css}\n</style>\n" + decoded

    # Also handle cid: image references - replace with empty alt
    decoded = re.sub(r'src="cid:[^"]*"', 'src=""', decoded)

    return decoded


def save_standalone_html(html: str, output_path: Path, title: str = "") -> None:
    """Wrap HTML in a standalone file if it isn't already."""
    if "<!DOCTYPE" not in html and "<html" not in html:
        html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<title>{title}</title>
<style>
body {{ font-family: 'SutonnyMJ', 'Bijoy', 'Kalpurush', sans-serif; margin: 20px; }}
</style>
</head>
<body>
{html}
</body>
</html>"""
    output_path.write_text(html, encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Generate readable HTML from MHTML files")
    parser.add_argument(
        "--output-dir", "-o",
        default="ground_truth/screenshots",
        help="Output directory",
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

    for i, f in enumerate(mhtml_files):
        print(f"  Processing {f.name}...", end=" ", flush=True)
        html = extract_full_mhtml(f)
        if not html:
            print("(no HTML found)")
            continue

        out_file = output_dir / f"{i:03d}_{f.stem}.html"
        save_standalone_html(html, out_file, title=f.name)
        print(f"-> {out_file.name} ({len(html)} bytes)")

    print(f"\nGenerated {len(mhtml_files)} HTML files in {output_dir}/")
    print("Open these in a browser - they should render with Bijoy fonts.")
    print("If fonts don't render, install SutonnyMJ font on your system.")


if __name__ == "__main__":
    main()
