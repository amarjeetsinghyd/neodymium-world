import json
import re

with open('news_data.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

articles = data.get("articles", []) if isinstance(data, dict) else data

for item in articles:
    if 'full_report' in item:
        for key, text in item['full_report'].items():
            if isinstance(text, str):
                fixed_text = re.sub(r'\n\s*\*\s+', r'<br><br>&bull;&nbsp;', text)
                item['full_report'][key] = fixed_text

with open('news_data.json', 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=4)

print("Fixed existing bullets in news_data.json")
