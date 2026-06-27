import sqlite3
import json
import os
import yaml

os.makedirs('content/articles', exist_ok=True)

conn = sqlite3.connect('neodymium.db')
cursor = conn.cursor()
cursor.execute("SELECT title, slug, article_url, original_link, image_url, published_at, added_at, reading_time, category, seo_tags, full_report FROM articles")
articles = cursor.fetchall()

for row in articles:
    title, slug, article_url, original_link, image_url, published_at, added_at, reading_time, category, seo_tags_json, full_report_json = row
    
    seo_tags = json.loads(seo_tags_json) if seo_tags_json else []
    try:
        report = json.loads(full_report_json) if full_report_json else {}
    except:
        report = {}

    key_takeaways = report.pop("Key Takeaways", [])
    faq = report.pop("FAQ", [])

    body_md = ""
    for section_name, section_content in report.items():
        if section_name in ["Key Takeaways", "FAQ", "executive_summary"]:
            continue
        formatted_name = section_name.replace('_', ' ').title()
        body_md += f"## {formatted_name}\n\n{section_content}\n\n"

    frontmatter = {
        "title": title,
        "slug": slug,
        "category": category,
        "seo_tags": seo_tags,
        "image_url": image_url,
        "original_link": original_link,
        "published_at": published_at,
        "added_at": added_at,
        "reading_time": reading_time,
    }
    
    if key_takeaways:
        frontmatter["key_takeaways"] = key_takeaways
    if faq:
        frontmatter["faq"] = faq

    md_content = f"---\n{yaml.dump(frontmatter, sort_keys=False, allow_unicode=True)}---\n\n{body_md}"
    
    with open(f"content/articles/{slug}.md", "w", encoding="utf-8") as f:
        f.write(md_content)

print(f"Migration complete! Migrated {len(articles)} articles.")
conn.close()
