import os
import re

ARTICLE_DIR = "content/articles"

if not os.path.exists(ARTICLE_DIR):
    print(f"Directory {ARTICLE_DIR} does not exist.")
    exit()

deleted = 0
kept = 0

for filename in os.listdir(ARTICLE_DIR):
    if not filename.endswith(".md") or filename == "template.md" or filename == "trigger.md":
        continue
    
    filepath = os.path.join(ARTICLE_DIR, filename)
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()
    
    category_match = re.search(r"^category:\s*(.+)$", content, re.MULTILINE)
    if category_match:
        category = category_match.group(1).strip()
        if "defense" in category.lower() or "tech" in category.lower() or "artificial intelligence" in category.lower() or "ai" in category.lower():
            kept += 1
            continue
    
    # If not a match or no category, it's irrelevant political/general news
    os.remove(filepath)
    html_path = os.path.join("articles", filename.replace(".md", ".html"))
    if os.path.exists(html_path):
        os.remove(html_path)
    deleted += 1

print(f"Kept {kept} tech/defense articles.")
print(f"Deleted {deleted} non-tech articles.")
