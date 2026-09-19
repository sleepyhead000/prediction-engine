"""Debug: test the updated parser logic."""
import re
from bs4 import BeautifulSoup

def decode_qp(text):
    text = re.sub(r'=\n', '', text)
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    def replace_hex(m):
        try: return chr(int(m.group(1), 16))
        except: return m.group(0)
    text = re.sub(r'=([0-9A-Fa-f]{2})', replace_hex, text)
    return text

with open(r'D:\Prediction engine\Physics\P1 MCQ 1.mhtml', 'rb') as f:
    raw = f.read()
content = raw.decode('utf-8', errors='replace')

# Find all HTML parts
html_parts = list(re.finditer(r'Content-Type: text/html.*?\r?\n\r?\n(.*?)(?=Content-Type:|\Z)', content, re.DOTALL))
print(f'Found {len(html_parts)} HTML parts')

for i, part in enumerate(html_parts):
    candidate = part.group(1)
    has_qb = 'questionBlock' in candidate
    has_q1 = 'Question 1' in candidate
    decoded = decode_qp(candidate)
    soup = BeautifulSoup(decoded, 'html.parser')
    qblocks = soup.find_all('div', class_='questionBlock')
    print(f'Part {i}: len={len(candidate)}, has_qb={has_qb}, has_q1={has_q1}, qblocks_after_decode={len(qblocks)}')
    if qblocks:
        # Show first question
        first_q = qblocks[0]
        serial = first_q.find('div', class_='serial')
        qtext = first_q.find('div', class_='questionText')
        print(f'  First question serial: {serial.get_text(strip=True) if serial else "NONE"}')
        print(f'  First question text preview: {qtext.get_text(strip=True)[:100] if qtext else "NONE"}')
