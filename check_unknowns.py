import json, sys
sys.stdout.reconfigure(encoding='utf-8')

data = json.load(open('classified_questions.json', 'r', encoding='utf-8'))

nonempty = []
for f_info in data:
    f = f_info.get('file', '')
    fname = f.split('\\')[-1]
    for q in f_info.get('questions', []):
        if q.get('topic') == 'Unknown' and q.get('question_text', '').strip():
            nonempty.append({
                'subject': q.get('subject', '?'),
                'num': q.get('question_number', 0),
                'file': fname,
                'text': q.get('question_text', '')[:200],
                'file_subject': f_info.get('subject', '?'),
            })

print(f'Non-empty Unknown topics: {len(nonempty)}')
for item in nonempty:
    print(f"  {item['subject']:12s} Q{item['num']:2d} | {item['file'][:45]:45s} | file_subj={item['file_subject']}")
    print(f"    Text: {item['text'][:120]}")
    print()
