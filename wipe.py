import os
import glob

# Delete all generated markdown articles
md_files = glob.glob('content/articles/*.md')
for f in md_files:
    if not f.endswith('template.md') and not f.endswith('trigger.md'):
        os.remove(f)

# Delete all compiled HTML articles
html_files = glob.glob('articles/*.html')
for f in html_files:
    os.remove(f)

# Clear deduplication so it can refetch the latest ones
if os.path.exists('content/seen_urls.json'):
    os.remove('content/seen_urls.json')

print("Wiped database completely.")
