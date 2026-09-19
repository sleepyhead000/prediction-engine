"""Debug: check decoded HTML structure."""
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

# Find questionBlock in decoded HTML
qb_idx = decoded.find('questionBlock')
print(f'questionBlock found at index: {qb_idx}')
if qb_idx >= 0:
    print(f'Context around questionBlock:')
    print(repr(decoded[qb_idx-50:qb_idx+100]))

# Check if class attributes are preserved
soup = BeautifulSoup(decoded, 'html.parser')
print(f'\nTotal divs: {len(soup.find_all("div"))}')

# Try finding by other means
all_divs = soup.find_all('div')
for d in all_divs[:5]:
    cls = d.get('class', [])
    print(f'div class={cls}, text={d.get_text(strip=True)[:50]}')

# Check if the issue is with =3D encoding in class names
print('\n--- Searching for class= in decoded HTML ---')
class_matches = re.findall(r'class=3D"([^"]+)"', decoded[:5000])
print(f'Found {len(class_matches)} class=3D matches (encoded not decoded)')
class_matches2 = re.findall(r'class="([^"]+)"', decoded[:5000])
print(f'Found {len(class_matches2)} class=" matches (decoded)')
