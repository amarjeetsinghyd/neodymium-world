# post_to_discord.py — Lightweight Discord Notifier
# Overhaul: replaced python-frontmatter with inline YAML parser (same as recompile_html.py),
# uses posted_to_discord flag in frontmatter for O(1) skip logic.

import os
import sys
import re
import yaml
import json
import requests
import logging

logging.basicConfig(
    stream=sys.stdout,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

ARTICLES_DIR = 'content/articles'
SITE_URL = 'https://neodymium.world'

# ---------------------------------------------------------------------------
# Inline YAML frontmatter parser — no python-frontmatter dependency
# ---------------------------------------------------------------------------
def parse_md(filepath: str) -> tuple[dict, str]:
    with open(filepath, 'r', encoding='utf-8') as f:
        raw = f.read()
    if not raw.startswith('---'):
        return {}, raw
    parts = raw.split('---', 2)
    if len(parts) < 3:
        return {}, raw
    try:
        meta = yaml.safe_load(parts[1]) or {}
    except yaml.YAMLError:
        meta = {}
    return meta, parts[2].strip()

def write_frontmatter(filepath: str, meta: dict, body: str):
    """Write updated frontmatter back to .md file."""
    content = f"---\n{yaml.dump(meta, sort_keys=False, allow_unicode=True)}---\n\n{body}\n"
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

# ---------------------------------------------------------------------------
# Build Discord embed
# ---------------------------------------------------------------------------
def build_embed(meta: dict) -> dict:
    title = meta.get('title', 'New Intelligence Brief')
    slug = meta.get('slug', '')
    article_url = f"{SITE_URL}/articles/{slug}.html"
    category = meta.get('category', 'Intelligence')
    reading_time = meta.get('reading_time', 3)
    image_url = meta.get('image_url', '')

    # Description: prefer social_hook, then executive_summary, then fallback
    description = (
        meta.get('social_hook')
        or meta.get('executive_summary', '')
        or 'A new intelligence brief has been published.'
    )
    if len(description) > 280:
        description = description[:277] + '...'

    # Key takeaways as bullet fields
    takeaways = meta.get('key_takeaways', []) or []
    fields = [
        {'name': 'Category', 'value': category, 'inline': True},
        {'name': 'Read Time', 'value': f'{reading_time} min', 'inline': True},
    ]
    if takeaways:
        fields.append({
            'name': '⚡ Key Takeaway',
            'value': str(takeaways[0])[:100],
            'inline': False
        })

    embed = {
        'title': title[:256],
        'url': article_url,
        'description': description,
        'color': 0x5865F2,  # Discord blurple
        'fields': fields,
        'footer': {'text': 'Neodymium Intelligence • neodymium.world'}
    }
    # Only add image if URL is valid — empty string causes Discord 400
    if image_url and image_url.startswith('http'):
        embed['image'] = {'url': image_url}

    return embed

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def post_to_discord():
    webhook_url = os.environ.get('DISCORD_WEBHOOK_URL')
    if not webhook_url:
        logging.warning("DISCORD_WEBHOOK_URL not set. Skipping.")
        return

    if not os.path.exists(ARTICLES_DIR):
        logging.warning(f"{ARTICLES_DIR} not found.")
        return

    posted = 0
    for filename in sorted(os.listdir(ARTICLES_DIR)):
        if not filename.endswith('.md'):
            continue
        filepath = os.path.join(ARTICLES_DIR, filename)
        try:
            meta, body = parse_md(filepath)
        except Exception as e:
            logging.warning(f"Skipping {filename}: {e}")
            continue

        # Skip already posted
        if meta.get('posted_to_discord') is True:
            continue
        # Skip drafts
        if meta.get('draft', False):
            continue

        embed = build_embed(meta)
        payload = {'embeds': [embed]}

        try:
            resp = requests.post(webhook_url, json=payload, timeout=10)
            if resp.status_code == 429:  # Rate limited
                import time
                retry_after = resp.json().get('retry_after', 5)
                logging.warning(f"Discord rate limited. Waiting {retry_after}s...")
                time.sleep(retry_after + 0.5)
                resp = requests.post(webhook_url, json=payload, timeout=10)
            resp.raise_for_status()
            # Mark as posted in frontmatter
            meta['posted_to_discord'] = True
            write_frontmatter(filepath, meta, body)
            posted += 1
            logging.info(f"Posted to Discord: {meta.get('title', filename)[:60]}")
        except Exception as e:
            logging.error(f"Discord post failed for {filename}: {e}")

    logging.info(f"Discord: {posted} article(s) posted.")

if __name__ == '__main__':
    post_to_discord()
