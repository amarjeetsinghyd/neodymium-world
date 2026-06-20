import json
import re

def fix():
    with open('news_data.json', 'r', encoding='utf-8') as f:
        data = json.load(f)

    def process_pre_code(match):
        content = match.group(1)
        # Split by lines that start with '* ' or '- ' (ignoring leading spaces)
        parts = re.split(r'\n\s*[\*\-]\s+', '\n' + content)
        
        html = "<ul>\n"
        for part in parts:
            if not part.strip(): continue
            html += f"<li>{part.strip()}</li>\n"
        html += "</ul>"
        return html

    for item in data.get('articles', []):
        if 'full_report' in item:
            for key, text in item['full_report'].items():
                if isinstance(text, str):
                    # Find <pre><code>...</code></pre>
                    new_text = re.sub(r'<pre><code>(.*?)</code></pre>', process_pre_code, text, flags=re.DOTALL)
                    item['full_report'][key] = new_text

    with open('news_data.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4)
        
    print("Fixed <pre><code> blocks in news_data.json")

if __name__ == '__main__':
    fix()
