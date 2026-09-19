"""Debug: check HTML parsing more carefully."""
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

html_parts = list(re.finditer(r'Content-Type: text/html.*?\r?\n\r?\n(.*?)(?=Content-Type:|\Z)', content, re.DOTALL))
html = html_parts[0].group(1)
decoded = decode_qp(html)

print(f'Decoded HTML length: {len(decoded)}')

# Check if the HTML has proper structure
# Look for <html>, <head>, <body> tags
print(f'Has <html>: {"<html" in decoded.lower()}')
print(f'Has <head>: {"<head" in decoded.lower()}')
print(f'Has <body>: {"<body" in decoded.lower()}')

# Try parsing just a small section around questionBlock
qb_idx = decoded.find('questionBlock')
if qb_idx >= 0:
    # Get a chunk around the first question
    start = max(0, qb_idx - 500)
    end = min(len(decoded), qb_idx + 2000)
    chunk = decoded[start:end]
    print(f'\n--- Chunk around questionBlock (chars {start}-{end}) ---')
    print(chunk[:1000])
    
    # Try parsing just this chunk
    soup_chunk = BeautifulSoup(chunk, 'html.parser')
    qblocks = soup_chunk.find_all('div', class_='questionBlock')
    print(f'\nquestionBlock in chunk: {len(qblocks)}')
    
    # Check if the issue is with the full HTML
    # Try parsing with lxml
    try:
        soup_lxml = BeautifulSoup(decoded, 'lxml')
        print(f'lxml parser: {len(soup_lxml.find_all("div"))} divs')
    except:
        print('lxml not available')
    
    # Try html5lib
    try:
        soup_h5 = BeautifulSoup(decoded, 'html5lib')
        print(f'html5lib parser: {len(soup_h5.find_all("div"))} divs')
    except:
        print('html5lib not available')
