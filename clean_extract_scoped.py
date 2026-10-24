with open('extract_scoped.py', 'r', encoding='utf-8') as f:
    text = f.read()

cleaned = text.replace('\u2014', '--').replace('\u2192', '->').replace('\u2013', '-').replace('\u2022', '*')

header = 'import sys\nif hasattr(sys.stdout, "reconfigure"):\n    sys.stdout.reconfigure(encoding="utf-8", errors="replace")\n'
if 'sys.stdout.reconfigure' not in cleaned:
    cleaned = header + cleaned

with open('extract_scoped.py', 'w', encoding='utf-8') as f:
    f.write(cleaned)

print('Cleaned extract_scoped.py successfully')
