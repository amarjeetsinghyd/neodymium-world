import json
import re

with open('news_data.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

# The data could be a dict with "articles" or just a list
articles = data.get("articles", []) if isinstance(data, dict) else data

for item in articles:
    if 'full_report' in item:
        for key, text in item['full_report'].items():
            if isinstance(text, str):
                # Replace literal asterisk bullets inside the HTML with proper line breaks and bullets
                # The text is already HTML, so it looks like <p>... \n    *   Properties: ...</p>
                # We will replace \n followed by spaces and * with <br><br>&bull;&nbsp;
                fixed_text = re.sub(r'\n\s*\*\s+', r'<br><br>&bull;&nbsp;', text)
                item['full_report'][key] = fixed_text

with open('news_data.json', 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=4)

print("Fixed existing bullets in news_data.json")
