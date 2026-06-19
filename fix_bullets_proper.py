import json
import re

with open('news_data.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

articles = data.get("articles", []) if isinstance(data, dict) else data

for item in articles:
    if 'full_report' in item:
        for key, text in item['full_report'].items():
            if isinstance(text, str):
                # Revert previous hack
                text = text.replace('<br><br>&bull;&nbsp;', '\n* ')
                
                # We want to find blocks of text that have \n* and convert them to <ul><li>...</li></ul>
                # A block is one or more lines starting with \n* 
                
                def replace_list(match):
                    list_content = match.group(0)
                    # Convert each \n* item into <li>item</li>
                    items = re.split(r'\n\*\s+', list_content)[1:] # [1:] because first split is empty
                    li_html = "".join([f"<li>{item.strip()}</li>" for item in items])
                    return f"<ul>{li_html}</ul>"

                # Match a sequence of \n* lines
                # (?:\n\*\s+.*)+ matches multiple lines starting with \n*
                # We use a non-greedy .*? and lookahead for either \n* or end of paragraph
                text = re.sub(r'(?:\n\*\s+.*?)+(?=\n|</p>|$)', replace_list, text, flags=re.DOTALL)
                
                item['full_report'][key] = text

with open('news_data.json', 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=4)

print("Fixed existing bullets in news_data.json to use proper ul/li HTML tags")
