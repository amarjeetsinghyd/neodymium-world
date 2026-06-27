# recompile_html.py — Incremental Static Site Generator
# Overhaul: only rebuilds articles whose .md is newer than their .html,
# dropped python-frontmatter in favour of inline YAML parsing,
# dropped markdown library (Article Body already HTML from Gemini).

import os
import json
import sys
import yaml
import logging
from datetime import datetime, timezone
from jinja2 import Environment, FileSystemLoader, select_autoescape

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    stream=sys.stdout,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

ARTICLES_DIR = 'content/articles'
OUTPUT_DIR = 'articles'
SITE_URL = 'https://neodymium.world'

# Jinja2 env — loaded once, reused for all renders
env = Environment(
    loader=FileSystemLoader('templates'),
    autoescape=select_autoescape(['html', 'xml'])
)

# ---------------------------------------------------------------------------
# Lightweight YAML frontmatter parser
# Replaces python-frontmatter to avoid its regex overhead
# ---------------------------------------------------------------------------
def parse_md(filepath: str) -> tuple[dict, str]:
    """Parse ---frontmatter--- + body from a .md file.
    Returns (metadata_dict, body_string)."""
    with open(filepath, 'r', encoding='utf-8') as f:
        raw = f.read()
    if not raw.startswith('---'):
        return {}, raw
    parts = raw.split('---', 2)
    if len(parts) < 3:
        return {}, raw
    try:
        meta = yaml.safe_load(parts[1]) or {}
    except yaml.YAMLError as e:
        logging.warning(f"YAML parse error in {filepath}: {e}")
        meta = {}
    return meta, parts[2].strip()

# ---------------------------------------------------------------------------
# Date parsing — inline, no email.utils import
# ---------------------------------------------------------------------------
def parse_date(val) -> datetime:
    if not val:
        return datetime.min.replace(tzinfo=timezone.utc)
    if isinstance(val, datetime):
        return val if val.tzinfo else val.replace(tzinfo=timezone.utc)
    s = str(val).strip()
    for fmt in ('%a, %d %b %Y %H:%M:%S %z', '%Y-%m-%dT%H:%M:%S%z',
                '%Y-%m-%dT%H:%M:%SZ', '%Y-%m-%d'):
        try:
            return datetime.strptime(s, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return datetime.min.replace(tzinfo=timezone.utc)

# ---------------------------------------------------------------------------
# Load all articles — metadata only (body only loaded when rebuilding HTML)
# ---------------------------------------------------------------------------
def load_articles() -> list[dict]:
    articles = []
    if not os.path.exists(ARTICLES_DIR):
        logging.warning(f"{ARTICLES_DIR} does not exist yet.")
        return articles
    for filename in sorted(os.listdir(ARTICLES_DIR)):
        if not filename.endswith('.md'):
            continue
        filepath = os.path.join(ARTICLES_DIR, filename)
        try:
            meta, _ = parse_md(filepath)
        except Exception as e:
            logging.warning(f"Skipping {filename}: {e}")
            continue
        if meta.get('draft', False):
            continue
        # Normalize image URL to absolute
        raw_img = meta.get('image_url', '')
        if raw_img and not raw_img.startswith('http'):
            clean = raw_img.lstrip('./').lstrip('/')
            meta['image_url'] = f"{SITE_URL}/{clean}"
        # Ensure article_url is set
        if not meta.get('article_url'):
            slug = meta.get('slug', filename.replace('.md', ''))
            meta['article_url'] = f'articles/{slug}.html'
        meta['_md_path'] = filepath
        meta['published_dt'] = parse_date(meta.get('published_at'))
        articles.append(meta)
    articles.sort(key=lambda a: a['published_dt'], reverse=True)
    return articles

# ---------------------------------------------------------------------------
# Incremental article HTML builder
# Only rebuilds if .md is newer than existing .html (mtime comparison)
# ---------------------------------------------------------------------------
def build_articles(articles: list[dict]) -> int:
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    template = env.get_template('article_template.html')
    rebuilt = 0
    skipped = 0
    current_date = datetime.now(timezone.utc).strftime('%Y-%m-%d')

    for item in articles:
        slug = item.get('slug') or item['article_url'].split('/')[-1].replace('.html', '')
        out_path = os.path.join(OUTPUT_DIR, f"{slug}.html")
        md_path = item['_md_path']

        # Skip if HTML already exists and is newer than the .md source
        if os.path.exists(out_path):
            if os.path.getmtime(out_path) >= os.path.getmtime(md_path):
                skipped += 1
                continue

        # Load body only when we actually need to rebuild
        try:
            _, body_html = parse_md(md_path)
        except Exception as e:
            logging.warning(f"Cannot read body for {slug}: {e}")
            continue

        try:
            rendered = template.render(
                article=item,
                body_html=body_html,
                current_date=current_date,
                site_url=SITE_URL
            )
            with open(out_path, 'w', encoding='utf-8') as f:
                f.write(rendered)
            rebuilt += 1
        except Exception as e:
            logging.warning(f"Template render failed for {slug}: {e}")
            continue

    logging.info(f"Articles: {rebuilt} rebuilt, {skipped} skipped (up-to-date).")
    return rebuilt

# ---------------------------------------------------------------------------
# Generate news_data.json — slim card metadata only, no body
# ---------------------------------------------------------------------------
FRONTEND_FIELDS = [
    'title', 'slug', 'category', 'seo_tags', 'image_url',
    'published_at', 'reading_time', 'article_url',
    'key_takeaways', 'seo_title', 'meta_description', 'social_hook'
]

def generate_news_data(articles: list[dict]):
    slim = [{k: v for k, v in a.items() if k in FRONTEND_FIELDS} for a in articles]
    # Serialize published_at as ISO string if it's a datetime object
    for s in slim:
        if isinstance(s.get('published_at'), datetime):
            s['published_at'] = s['published_at'].isoformat()
    with open('news_data.json', 'w', encoding='utf-8') as f:
        json.dump(slim, f, separators=(',', ':'))  # compact — no indent whitespace
    logging.info(f"news_data.json written: {len(slim)} articles.")

# ---------------------------------------------------------------------------
# Generate sitemap.xml
# ---------------------------------------------------------------------------
def generate_sitemap(articles: list[dict], current_date: str):
    try:
        tmpl = env.get_template('sitemap_template.xml')
        rendered = tmpl.render(articles=articles, current_date=current_date)
        with open('sitemap.xml', 'w', encoding='utf-8') as f:
            f.write(rendered)
        logging.info("sitemap.xml written.")
    except Exception as e:
        logging.error(f"Sitemap generation failed: {e}")

# ---------------------------------------------------------------------------
# Generate rss.xml
# ---------------------------------------------------------------------------
def generate_rss(articles: list[dict], current_date: str):
    try:
        tmpl = env.get_template('rss_template.xml')
        rendered = tmpl.render(articles=articles[:20], current_date=current_date)
        with open('rss.xml', 'w', encoding='utf-8') as f:
            f.write(rendered)
        logging.info("rss.xml written.")
    except Exception as e:
        logging.error(f"RSS generation failed: {e}")

# ---------------------------------------------------------------------------
# Generate archive.html
# ---------------------------------------------------------------------------
def generate_archive(articles: list[dict], current_date: str):
    try:
        tmpl = env.get_template('archive_template.html')
        rendered = tmpl.render(articles=articles, current_date=current_date)
        with open('archive.html', 'w', encoding='utf-8') as f:
            f.write(rendered)
        logging.info("archive.html written.")
    except Exception as e:
        logging.error(f"Archive generation failed: {e}")

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    current_date = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    articles = load_articles()
    logging.info(f"Loaded {len(articles)} published articles.")

    build_articles(articles)
    generate_news_data(articles)
    generate_sitemap(articles, current_date)
    generate_rss(articles, current_date)
    generate_archive(articles, current_date)

if __name__ == '__main__':
    main()
