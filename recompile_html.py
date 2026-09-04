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
from bs4 import BeautifulSoup
from jinja2 import Environment, FileSystemLoader, select_autoescape
import media_resolver

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
        if meta.get('draft', False) or not meta.get('title'):
            continue
        # Normalize image URL to absolute
        raw_img = meta.get('image_url', '')
        if raw_img and not raw_img.startswith('http'):
            clean = raw_img.lstrip('./').lstrip('/')
            meta['image_url'] = f"{SITE_URL}/{clean}"
        # Ensure slug and article_url are set
        slug = meta.get('slug') or filename.replace('.md', '')
        meta['slug'] = slug
        if not meta.get('article_url'):
            meta['article_url'] = f'articles/{slug}.html'
        meta['_md_path'] = filepath
        meta['published_dt'] = parse_date(meta.get('published_at'))
        if meta['published_dt'] != datetime.min.replace(tzinfo=timezone.utc):
            meta['display_date'] = meta['published_dt'].strftime('%b %d, %Y')
        else:
            meta['display_date'] = str(meta.get('published_at', ''))[:10]

        if type(meta.get('published_at')).__name__ == 'datetime':
            meta['published_at'] = meta['published_at'].isoformat()
        else:
            meta['published_at'] = str(meta.get('published_at', ''))

        # Ensure seo_tags is a list of tag strings rather than iterating over string chars
        tags = meta.get('seo_tags', [])
        if isinstance(tags, str):
            meta['seo_tags'] = [t.strip() for t in tags.split(',') if t.strip()]
        elif not isinstance(tags, list):
            meta['seo_tags'] = []
        articles.append(meta)
    articles.sort(key=lambda a: a['published_dt'], reverse=True)
    return articles

# ---------------------------------------------------------------------------
# Related & Recommended Articles Helper
# ---------------------------------------------------------------------------
def get_article_recommendations(target: dict, all_articles: list[dict], count: int = 3) -> tuple[list[dict], dict | None]:
    target_slug = target.get('slug')
    target_tags = set(t.lower().replace('#', '') for t in target.get('seo_tags', []))
    target_cat = target.get('category', '').lower()

    candidates = [a for a in all_articles if a.get('slug') != target_slug]
    if not candidates:
        return [], None

    def score(a):
        cand_tags = set(t.lower().replace('#', '') for t in a.get('seo_tags', []))
        overlap = len(target_tags.intersection(cand_tags))
        cat_match = 2 if a.get('category', '').lower() == target_cat else 0
        return overlap * 3 + cat_match

    candidates.sort(key=score, reverse=True)
    recommended = candidates[:count]
    inline_choice = candidates[0] if candidates else None
    return recommended, inline_choice

# ---------------------------------------------------------------------------
# In-Article Enhancement (Secondary Figure + Inline Also Read)
# ---------------------------------------------------------------------------
def enhance_body_html(body_html: str, inline_rel: dict | None, sec_img: dict | None) -> str:
    try:
        soup = BeautifulSoup(body_html, 'html.parser')
        h2s = soup.find_all('h2')

        # 1. Build inline "Also Read" widget
        card_tag = None
        if inline_rel and inline_rel.get('title'):
            card_html = (
                f'<div class="inline-related-card">'
                f'  <div style="flex:1;">'
                f'    <span style="font-size:0.75rem; text-transform:uppercase; letter-spacing:0.08em; font-weight:700; color:var(--accent-blue); display:block; margin-bottom:0.35rem;">&bull; Strategic Intelligence Analysis</span>'
                f'    <a href="../{inline_rel["article_url"]}" style="font-size:1.05rem; font-weight:600; color:var(--text-main); text-decoration:none; line-height:1.4; display:block;">{inline_rel["title"]} &rarr;</a>'
                f'  </div>'
                f'  <div style="font-size:0.85rem; color:var(--text-light); white-space:nowrap;">{inline_rel.get("reading_time", 6)} min read</div>'
                f'</div>'
            )
            card_tag = BeautifulSoup(card_html, 'html.parser').find('div')

        # 2. Build secondary in-article figure (only if article has no inline figure/img already)
        has_existing_img = bool(soup.find('img') or soup.find('figure'))
        fig_tag = None
        if sec_img and sec_img.get('url') and not has_existing_img:
            fig_html = (
                f'<figure class="article-inline-figure">'
                f'  <img src="{sec_img["url"]}" alt="{sec_img.get("title", "Strategic Asset")}" loading="lazy">'
                f'  <figcaption>{sec_img.get("caption", "")}</figcaption>'
                f'</figure>'
            )
            fig_tag = BeautifulSoup(fig_html, 'html.parser').find('figure')

        # 3. Position elements naturally between sections
        if len(h2s) >= 3:
            if card_tag:
                h2s[1].insert_before(card_tag)
            if fig_tag:
                h2s[2].insert_before(fig_tag)
        elif len(h2s) == 2:
            if card_tag:
                h2s[1].insert_before(card_tag)
            if fig_tag:
                h2s[1].insert_after(fig_tag)
        else:
            paras = soup.find_all('p')
            if len(paras) >= 3 and card_tag:
                paras[2].insert_after(card_tag)
            if len(paras) >= 6 and fig_tag:
                paras[5].insert_after(fig_tag)

        return str(soup)
    except Exception as e:
        logging.debug(f"Could not enhance body HTML: {e}")
        return body_html

# ---------------------------------------------------------------------------
# Incremental article HTML builder
# Rebuilds if .md is newer than existing .html, or if force=True
# ---------------------------------------------------------------------------
def build_articles(articles: list[dict], force: bool = False) -> int:
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    template = env.get_template('article_template.html')
    rebuilt = 0
    skipped = 0
    current_date = datetime.now(timezone.utc).strftime('%Y-%m-%d')

    for item in articles:
        slug = item.get('slug') or item['article_url'].split('/')[-1].replace('.html', '')
        out_path = os.path.join(OUTPUT_DIR, f"{slug}.html")
        md_path = item['_md_path']

        # Skip if HTML already exists and is newer than the .md source (unless force=True)
        if not force and os.path.exists(out_path):
            if os.path.getmtime(out_path) >= os.path.getmtime(md_path):
                skipped += 1
                continue

        # Load body only when we actually need to rebuild
        try:
            _, raw_body_html = parse_md(md_path)
        except Exception as e:
            logging.warning(f"Cannot read body for {slug}: {e}")
            continue

        # Resolve recommendations and secondary photography
        recommended, inline_choice = get_article_recommendations(item, articles, count=3)
        sec_img = media_resolver.resolve_secondary_image(
            item.get('title', ''),
            item.get('seo_tags', []),
            item.get('category', '')
        )

        enhanced_body = enhance_body_html(raw_body_html, inline_choice, sec_img)

        try:
            rendered = template.render(
                body_html=enhanced_body,
                current_date=current_date,
                site_url=SITE_URL,
                recommended_articles=recommended,
                **item
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
    force = '--force' in sys.argv
    current_date = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    articles = load_articles()
    logging.info(f"Loaded {len(articles)} published articles.")

    build_articles(articles, force=force)
    generate_news_data(articles)
    generate_sitemap(articles, current_date)
    generate_rss(articles, current_date)
    generate_archive(articles, current_date)

if __name__ == '__main__':
    main()
