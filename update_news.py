# update_news.py — Lightweight News Pipeline
# Overhaul: dropped trafilatura, O(1) deduplication via seen_urls.json,
# reduced sleep, BeautifulSoup used only for RSS summary fallback.

import feedparser
import json
import os
import re
import requests
import sys
import time
import yaml
import logging
from datetime import datetime, timezone
from urllib.parse import urlparse
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# Logging — stdout so GitHub Actions captures it; no file written
# ---------------------------------------------------------------------------
logging.basicConfig(
    stream=sys.stdout,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
SARVAM_API_KEY = os.environ.get("SARVAM_API_KEY")

ARTICLES_DIR = 'content/articles'
SEEN_URLS_FILE = 'content/seen_urls.json'
MAX_ARTICLES_PER_RUN = 5
MAX_CHARS = 6000
RATE_LIMIT_SLEEP = 8

if GEMINI_API_KEY:
    GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
else:
    GEMINI_URL = None

SARVAM_URL = "https://api.sarvam.ai/v1/chat/completions"

RSS_FEEDS = [
    {"region": "Western", "url": "https://breakingdefense.com/feed/"},
    {"region": "Western", "url": "https://techcrunch.com/category/artificial-intelligence/feed/"},
    {"region": "Western", "url": "https://www.wired.com/feed/category/tech/latest/rss"},
    {"region": "Western", "url": "https://venturebeat.com/category/ai/feed/"},
    {"region": "Western", "url": "https://www.technologyreview.com/feed/"},
    {"region": "Indian", "url": "http://www.indiandefensenews.in/feeds/posts/default?alt=rss"},
    {"region": "Indian", "url": "https://www.thehindu.com/sci-tech/technology/feeder/default.rss"},
    {"region": "Indian", "url": "https://yourstory.com/feed/"},
    {"region": "Indian", "url": "https://inc42.com/feed/"},
    {"region": "Indian", "url": "https://feeds.feedburner.com/ndtv-gadgets-360"},
    {"region": "Indian", "url": "https://www.firstpost.com/feed/rss/tech"},
    {"region": "Indian", "url": "https://indianexpress.com/section/india/feed/"},
]

# ---------------------------------------------------------------------------
# Seen-URL deduplication — loaded once at startup, O(1) lookup
# ---------------------------------------------------------------------------
def load_seen_urls() -> set:
    if os.path.exists(SEEN_URLS_FILE):
        try:
            with open(SEEN_URLS_FILE, 'r') as f:
                return set(json.load(f))
        except Exception:
            pass
    return set()

def save_seen_urls(seen: set):
    os.makedirs(os.path.dirname(SEEN_URLS_FILE), exist_ok=True)
    with open(SEEN_URLS_FILE, 'w') as f:
        json.dump(list(seen), f)

# ---------------------------------------------------------------------------
# Lightweight article text extraction — no trafilatura
# Uses requests + BeautifulSoup paragraph extraction only
# ---------------------------------------------------------------------------
REQUEST_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (compatible; Neodymium/1.0; +https://neodymium.world)'
}

def fetch_article_text(url: str, summary: str = '') -> str:
    """Fetch article text with a lightweight BS4 paragraph scrape.
    Falls back to RSS summary if the page fetch fails.
    Strictly time-boxed: 6s timeout, no retry."""
    try:
        resp = requests.get(url, headers=REQUEST_HEADERS, timeout=6)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, 'html.parser')
        # Remove nav, footer, scripts, ads
        for tag in soup(['script', 'style', 'nav', 'footer', 'aside', 'form']):
            tag.decompose()
        # Extract <article> or <main> content first, fall back to all <p>
        container = soup.find('article') or soup.find('main') or soup
        paragraphs = container.find_all('p')
        text = ' '.join(p.get_text(' ', strip=True) for p in paragraphs)
        if len(text.strip()) > 200:
            return text[:MAX_CHARS]
    except Exception as e:
        logging.warning(f"fetch_article_text failed for {url}: {e}")
    # Fallback: strip HTML from RSS summary
    if summary:
        clean = BeautifulSoup(summary, 'html.parser').get_text(' ', strip=True)
        return clean[:MAX_CHARS]
    return ''

# ---------------------------------------------------------------------------
# Image URL extraction — from RSS entry only, no full page scrape
# ---------------------------------------------------------------------------
def get_image_url(entry) -> str:
    # media:content
    for m in getattr(entry, 'media_content', []):
        u = m.get('url', '')
        if u.startswith('http') and any(u.lower().endswith(x) for x in ('.jpg','.jpeg','.png','.webp')):
            return u
    # enclosures
    for enc in getattr(entry, 'enclosures', []):
        u = enc.get('href', '') or enc.get('url', '')
        if u.startswith('http') and 'image' in enc.get('type', 'image'):
            return u
    # first <img> in summary
    summary_html = getattr(entry, 'summary', '')
    if summary_html:
        soup = BeautifulSoup(summary_html, 'html.parser')
        img = soup.find('img')
        if img and img.get('src', '').startswith('http'):
            return img['src']
    return ''

# ---------------------------------------------------------------------------
# Slug generation
# ---------------------------------------------------------------------------
def make_slug(title: str) -> str:
    base = re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-')[:80]
    suffix = str(int(datetime.now(timezone.utc).timestamp()))[-6:]
    return f"{base}-{suffix}"

# ---------------------------------------------------------------------------
# Sanitize filename
# ---------------------------------------------------------------------------
def sanitize_filename(name: str) -> str:
    return re.sub(r'[^a-z0-9._-]', '-', name.lower()).strip('-')

# ---------------------------------------------------------------------------
# Gemini rewrite
# ---------------------------------------------------------------------------
def rewrite_content(title: str, text: str, region: str) -> dict | None:
    if region == "Indian":
        identity = "Amarjeet Singh, Senior Analyst & Publisher at Neodymium World, specializing in Indian defense posture, Atmanirbhar Bharat, and South Asian geopolitics"
    else:
        identity = "Alexander Sterling, Global Defense & Tech Strategist, specializing in Western defense, NATO, and Silicon Valley tech shifts"

    prompt = f"""You are {identity}. You are writing an original, highly opinionated, and deeply analytical intelligence briefing based on the provided source material.

CRITICAL INSTRUCTION: Do NOT just rewrite or summarize the article. Google AdSense rejects simple rewrites as "Low value content." Instead, use the article only as a baseline to provide strategic forecasting, geopolitical implications, and market analysis.
ZERO-FILLER RULE: Eliminate all fluff, filler words (e.g., "In today's fast-paced world", "It is important to note"), and repetition. Every single sentence must introduce new analytical value. Use active voice and short paragraphs (max 3 sentences).

IMPORTANT: Return ONLY valid JSON, no markdown fences.

Required JSON fields:
- "Title": original, highly analytical headline under 80 chars
- "seo_title": under 60 chars, keyword-front-loaded
- "meta_description": under 155 chars, for search snippets
- "social_hook": under 280 chars, strong hook for Discord/Twitter
- "Category": one of [Intelligence, AI & Autonomy, Policy Watch, Space & Satellites, Cyber & EW, Defense Tech]
- "SEO Tags": comma-separated keywords string
- "Executive Summary": 3-sentence brief, authoritative tone, zero filler
- "Key Takeaways": list of exactly 4 concise strings
- "Article Body": full HTML body using <h2><p><ul><strong> tags. MUST INCLUDE specific <h2> sections titled "Expert Commentary" and "Strategic Forecasting". Write confidently from the first-person ("I project..."). Max 3 sentences per paragraph.
- "FAQ": list of 3 objects each with "question" and "answer" strings focusing on strategic significance
- "Reading Time": integer minutes

ARTICLE TITLE: {title}
ARTICLE TEXT: {text[:MAX_CHARS]}"""

    try:
        if region == "Indian" and SARVAM_API_KEY:
            headers = {"Content-Type": "application/json", "api-subscription-key": SARVAM_API_KEY}
            payload = {
                "model": "sarvam-m", # Using a safe model string for Sarvam
                "messages": [
                    {"role": "system", "content": "You are a JSON-generating expert analyst. ONLY output valid JSON. No markdown formatting."},
                    {"role": "user", "content": prompt}
                ]
            }
            resp = requests.post(SARVAM_URL, json=payload, headers=headers, timeout=30)
            resp.raise_for_status()
            raw = resp.json()['choices'][0]['message']['content']
        else:
            if not GEMINI_URL:
                logging.error("GEMINI_URL is not set.")
                return None
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.4, "maxOutputTokens": 2048, "responseMimeType": "application/json"}
            }
            resp = requests.post(GEMINI_URL, json=payload, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            candidates = data.get('candidates', [])
            if not candidates or candidates[0].get('finishReason') not in ('STOP', None, ''):
                logging.warning(f"Gemini blocked or empty for: {title}")
                return None
            raw = candidates[0]['content']['parts'][0]['text']

        # Strip accidental markdown fences
        raw = re.sub(r'^```json\s*|^```\s*|```$', '', raw.strip(), flags=re.MULTILINE)
        return json.loads(raw)
    except json.JSONDecodeError as e:
        logging.error(f"JSON parse error for '{title}': {e}")
        return None
    except Exception as e:
        logging.error(f"API error for '{title}': {e}")
        return None
        raw = candidates[0]['content']['parts'][0]['text']
        # Strip accidental markdown fences
        raw = re.sub(r'^```json\s*|^```\s*|```$', '', raw.strip(), flags=re.MULTILINE)
        return json.loads(raw)
    except json.JSONDecodeError as e:
        logging.error(f"Gemini JSON parse error for '{title}': {e}")
        return None
    except Exception as e:
        logging.error(f"Gemini API error for '{title}': {e}")
        return None

# ---------------------------------------------------------------------------
# Write article markdown
# ---------------------------------------------------------------------------
def write_article(slug: str, link: str, image_url: str,
                  published: str, full_report: dict):
    os.makedirs(ARTICLES_DIR, exist_ok=True)
    filepath = os.path.join(ARTICLES_DIR, f"{slug}.md")
    frontmatter = {
        'title':            full_report.get('Title', ''),
        'seo_title':        full_report.get('seo_title', '')[:60],
        'meta_description': full_report.get('meta_description', '')[:155],
        'social_hook':      full_report.get('social_hook', '')[:280],
        'slug':             slug,
        'category':         full_report.get('Category', 'Intelligence'),
        'seo_tags':         full_report.get('SEO Tags', ''),
        'image_url':        image_url,
        'source_url':       link,
        'published_at':     published,
        'reading_time':     full_report.get('Reading Time', 3),
        'executive_summary': full_report.get('Executive Summary', ''),
        'key_takeaways':    full_report.get('Key Takeaways', []),
        'faq':              full_report.get('FAQ', []),
        'article_url':      f'articles/{slug}.html',
        'draft':            False,
        'posted_to_discord': False,
    }
    body = full_report.get('Article Body', '')
    content = f"---\n{yaml.dump(frontmatter, sort_keys=False, allow_unicode=True)}---\n\n{body}\n"
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    logging.info(f"Written: {filepath}")

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    seen_urls = load_seen_urls()  # O(1) set lookup — replaces per-file scan
    processed = 0
    new_slugs = []

    for feed_info in RSS_FEEDS:
        feed_url = feed_info["url"]
        region = feed_info["region"]
        if processed >= MAX_ARTICLES_PER_RUN:
            break
        try:
            feed = feedparser.parse(feed_url)
        except Exception as e:
            logging.warning(f"Feed parse error {feed_url}: {e}")
            continue

        for entry in feed.entries:
            if processed >= MAX_ARTICLES_PER_RUN:
                break

            link = getattr(entry, 'link', '')
            if not link or link in seen_urls:
                continue

            title = getattr(entry, 'title', '').strip()
            if not title:
                continue

            summary = getattr(entry, 'summary', '')
            published = getattr(entry, 'published', datetime.now(timezone.utc).isoformat())
            image_url = get_image_url(entry)

            # Rate-limit pause before Gemini call (skip on first article)
            if processed > 0:
                time.sleep(RATE_LIMIT_SLEEP)

            # Fetch article text — lightweight, no trafilatura
            text = fetch_article_text(link, summary)
            if not text:
                logging.warning(f"No text extracted, skipping: {link}")
                seen_urls.add(link)  # Mark as seen so we don't retry
                continue

            full_report = rewrite_content(title, text, region)
            if not full_report:
                seen_urls.add(link)
                continue

            slug = make_slug(full_report.get('Title', title))
            write_article(slug, link, image_url, published, full_report)

            seen_urls.add(link)
            new_slugs.append(slug)
            processed += 1
            logging.info(f"[{processed}/{MAX_ARTICLES_PER_RUN}] Processed: {title[:60]}")

    save_seen_urls(seen_urls)
    logging.info(f"Done. {processed} new articles written.")
    return new_slugs

if __name__ == '__main__':
    main()
