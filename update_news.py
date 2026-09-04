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
import media_resolver

# ---------------------------------------------------------------------------
# Logging — stdout so GitHub Actions captures it; no file written
# ---------------------------------------------------------------------------
logging.basicConfig(
    stream=sys.stdout,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# ---------------------------------------------------------------------------
# Config & Models
# Primary: gemini-2.5-pro for think-tank grade writing & complex strategic reasoning
# Fallback: gemini-2.5-flash for resilience & rate limits
# ---------------------------------------------------------------------------
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
SARVAM_API_KEY = os.environ.get("SARVAM_API_KEY")
GEMINI_PRIMARY_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-pro")
GEMINI_FALLBACK_MODEL = "gemini-2.5-flash"

ARTICLES_DIR = 'content/articles'
SEEN_URLS_FILE = 'content/seen_urls.json'
MAX_ARTICLES_PER_RUN = 2  # High-impact curated stories (1-2 per run)
MAX_CHARS = 8000
RATE_LIMIT_SLEEP = 10

SARVAM_URL = "https://api.sarvam.ai/v1/chat/completions"

# Curated high-signal feeds: Frontier AI, Research Newsrooms, Defense, Space & Geopolitics
RSS_FEEDS = [
    # Frontier AI & Research Newsrooms (Captures GPT/Astra, Gemini, Claude launches)
    {"region": "Western", "url": "https://openai.com/news/rss.xml"},
    {"region": "Western", "url": "https://deepmind.google/blog/rss.xml"},
    {"region": "Western", "url": "https://feeds.arstechnica.com/arstechnica/technology-lab"},
    {"region": "Western", "url": "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml"},
    {"region": "Western", "url": "https://www.technologyreview.com/feed/"},
    {"region": "Western", "url": "https://venturebeat.com/category/ai/feed/"},

    # Premier Global Defense, Aerospace & Space Doctrine
    {"region": "Western", "url": "https://www.defenseone.com/rss/all/"},
    {"region": "Western", "url": "https://breakingdefense.com/feed/"},
    {"region": "Western", "url": "https://defensescoop.com/feed/"},
    {"region": "Western", "url": "https://www.c4isrnet.com/arc/outboundfeeds/rss/"},
    {"region": "Western", "url": "https://spacenews.com/feed/"},

    # Indian Defense, Aerospace, Border Security & Strategic Tech
    {"region": "Indian", "url": "http://www.indiandefensenews.in/feeds/posts/default?alt=rss"},
    {"region": "Indian", "url": "https://idrw.org/feed/"},
    {"region": "Indian", "url": "https://theprint.in/category/defence/feed/"},
    {"region": "Indian", "url": "https://www.thehindu.com/sci-tech/technology/feeder/default.rss"},
]

# Anti-Spam & Irrelevant Topic Filter
IRRELEVANT_KEYWORDS = [
    'deal', 'deals', 'discount', 'discounts', 'sale', 'flipkart', 'amazon deal',
    'coupon', 'coupons', 'cashback', 'earbuds', 'earphones', 'headphone',
    'headphones', 'smartwatch', 'case cover', 'power bank', 'powerbank',
    'unboxing', 'first look', 'smartphones under', 'phones under',
    'fashion', 'clothing', 'beauty', 'skincare', 'makeup', 'dating app',
    'food delivery', 'zomato', 'swiggy', 'blinkit', 'zepto', 'quick commerce',
    'movie review', 'box office', 'trailer release', 'cricket', 'ipl',
    'horoscope', 'recipe', 'bollywood', 'hollywood', 'celebrity'
]

def is_relevant_topic(title: str, summary: str = '') -> bool:
    """Pre-screen RSS entries to prevent converting consumer gadgets or
    sales into absurd 'defense/geopolitics' reports."""
    text = f"{title} {summary}".lower()
    for kw in IRRELEVANT_KEYWORDS:
        if re.search(r'\b' + re.escape(kw) + r'\b', text):
            return False
    return True

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
    # 1. media:thumbnail
    for m in getattr(entry, 'media_thumbnail', []):
        u = m.get('url', '')
        if u.startswith('http'):
            return u
    # 2. media:content
    for m in getattr(entry, 'media_content', []):
        u = m.get('url', '')
        if u.startswith('http') and any(u.lower().endswith(x) for x in ('.jpg','.jpeg','.png','.webp')):
            return u
    # 3. enclosures
    for enc in getattr(entry, 'enclosures', []):
        u = enc.get('href', '') or enc.get('url', '')
        if u.startswith('http') and 'image' in enc.get('type', 'image'):
            return u
    # 4. first <img> in summary
    summary_html = getattr(entry, 'summary', '')
    if summary_html:
        soup = BeautifulSoup(summary_html, 'html.parser')
        img = soup.find('img')
        if img and img.get('src', '').startswith('http'):
            return img['src']
    # 5. first <img> in content (content:encoded)
    content_list = getattr(entry, 'content', [])
    for content_item in content_list:
        content_html = content_item.get('value', '')
        if content_html:
            soup = BeautifulSoup(content_html, 'html.parser')
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
# Gemini API caller with primary (gemini-2.5-pro) and fallback (gemini-2.5-flash)
# ---------------------------------------------------------------------------
def call_gemini_api(prompt: str) -> str | None:
    if not GEMINI_API_KEY:
        logging.error("GEMINI_API_KEY is not set.")
        return None

    models_to_try = [GEMINI_PRIMARY_MODEL]
    if GEMINI_FALLBACK_MODEL not in models_to_try:
        models_to_try.append(GEMINI_FALLBACK_MODEL)

    for model_name in models_to_try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={GEMINI_API_KEY}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.6,
                "maxOutputTokens": 8192,
                "responseMimeType": "application/json"
            }
        }
        try:
            logging.info(f"Generating briefing via {model_name}...")
            resp = requests.post(url, json=payload, timeout=60)
            if resp.status_code == 429:
                logging.warning(f"Rate limited (429) on {model_name}. Attempting fallback...")
                time.sleep(4)
                continue
            resp.raise_for_status()
            data = resp.json()
            candidates = data.get('candidates', [])
            if not candidates or candidates[0].get('finishReason') not in ('STOP', None, ''):
                logging.warning(f"{model_name} response incomplete or filtered (finishReason: {candidates[0].get('finishReason') if candidates else 'empty'}).")
                continue
            return candidates[0]['content']['parts'][0]['text']
        except Exception as e:
            logging.warning(f"Error calling {model_name}: {e}")
            continue

    logging.error("All Gemini model attempts failed.")
    return None

# ---------------------------------------------------------------------------
# Strategic Intelligence Skill & Content Rewriter
# ---------------------------------------------------------------------------
def rewrite_content(title: str, text: str, region: str) -> dict | None:
    if region == "Indian":
        identity = "Amarjeet Singh, Senior Strategic Analyst & Publisher at Neodymium World, specializing in Indian defense posture, Atmanirbhar Bharat, border deterrence, and South Asian geopolitics"
    else:
        identity = "Alexander Sterling, Global Defense & Emerging Tech Strategist, specializing in Western defense modernization, NATO deterrence, aerospace, and critical supply chain hegemony"

    prompt = f"""You are {identity}. You are writing an in-depth, highly authoritative, and deeply engaging strategic intelligence feature (800 to 1,200 words) based on the provided source material.

JOURNALISTIC & STRATEGIC STANDARDS:
1. NATURAL JOURNALISTIC VOICE: Write like a seasoned national security correspondent (Foreign Policy, Reuters Special Reports, Janes, The Economist). Never sound like an AI assistant, corporate marketer, or a textbook.
2. COMPELLING OPENING (LEDE & NUT GRAPH):
   - Open with the decisive event, actors, and immediate development (the news peg).
   - Follow immediately with the "nut graph" establishing the high-stakes strategic, technological, or geopolitical implications.
3. ORGANIC, STORY-DRIVEN SUBHEADINGS: Do NOT use rigid, generic headers like "Strategic Context & Operational Baseline". Instead, use creative, descriptive, journalistic subheaders tailored specifically to this story (e.g., "The Hypersonic Standoff Dilemma", "Engineering Standoff Superiority", "Vulnerabilities Across the Chokepoints", "Deterrence Vectors on the Northern Border").
4. EDITORIAL PULL QUOTE: Include exactly ONE significant pull quote or strategic verdict inside `<blockquote class="editorial-pullquote">"..."</blockquote>` highlighting the pivotal insight of the analysis.
5. DEEP TECHNICAL & GEOPOLITICAL GROUNDING: Cite concrete numbers, platform ranges, payload capacities, contract values, doctrine shifts, and supply chain dependencies where applicable.
6. ZERO ROBOTIC FLUFF: Strictly eliminate phrases like "delve into", "tapestry", "in today's rapidly changing world", "a testament to", "it remains to be seen". Do NOT use repetitive first-person openers ("I observe that", "I argue that"). Speak with seasoned institutional judgment.
7. HTML ARTICLE BODY: The "Article Body" MUST be valid semantic HTML using <h2>, <p>, <blockquote class="editorial-pullquote">, <ul>, <li>, and <strong>. Ensure 4 to 6 substantial narrative sections with 3-5 rich sentences per paragraph.

IMPORTANT: Return ONLY a valid JSON object without markdown fences.

Required JSON fields:
- "Title": High-impact, natural journalistic headline under 85 chars
- "seo_title": Keyword-front-loaded headline under 60 chars
- "meta_description": Compelling search snippet under 155 chars
- "social_hook": Engaging hook for social feeds / Discord under 280 chars
- "Category": One of [Intelligence, AI & Autonomy, Policy Watch, Space & Satellites, Cyber & EW, Defense Tech]
- "SEO Tags": List of 4 to 6 high-relevance topic strings (e.g. ["Hypersonic Weapons", "DRDO", "LAC Deterrence", "Atmanirbhar Bharat"])
- "Executive Summary": Authoritative 3-sentence executive brief
- "Key Takeaways": List of exactly 4 concise strategic takeaway strings
- "Article Body": Full, comprehensive HTML body (800-1,200 words)
- "Reading Time": Integer minutes (typically 6 to 8)

ARTICLE TITLE: {title}
ARTICLE TEXT: {text[:MAX_CHARS]}"""

    try:
        raw = None
        if region == "Indian" and SARVAM_API_KEY:
            headers = {"Content-Type": "application/json", "api-subscription-key": SARVAM_API_KEY}
            payload = {
                "model": "sarvam-105b",
                "messages": [
                    {"role": "system", "content": "You are a JSON-generating expert defense analyst. ONLY output valid JSON. No markdown formatting."},
                    {"role": "user", "content": prompt}
                ]
            }
            try:
                resp = requests.post(SARVAM_URL, json=payload, headers=headers, timeout=45)
                if resp.status_code == 200:
                    raw = resp.json()['choices'][0]['message']['content']
            except Exception as se:
                logging.warning(f"Sarvam call failed: {se}. Falling back to Gemini.")

        # If Sarvam was not used or failed, call Gemini Pro/Flash
        if not raw:
            raw = call_gemini_api(prompt)

        if not raw:
            return None

        # Strip accidental markdown fences
        raw = re.sub(r'^```json\s*|^```\s*|```$', '', raw.strip(), flags=re.MULTILINE)
        return json.loads(raw)
    except json.JSONDecodeError as e:
        logging.error(f"JSON parse error for '{title}': {e}")
        return None
    except Exception as e:
        logging.error(f"API error for '{title}': {e}")
        return None

# ---------------------------------------------------------------------------
# Write article markdown
# ---------------------------------------------------------------------------
def write_article(slug: str, link: str, image_url: str,
                  published: str, full_report: dict):
    os.makedirs(ARTICLES_DIR, exist_ok=True)
    filepath = os.path.join(ARTICLES_DIR, f"{slug}.md")

    # Normalize SEO Tags into a clean list of strings
    raw_tags = full_report.get('SEO Tags', [])
    if isinstance(raw_tags, str):
        clean_tags = [t.strip().lstrip('#') for t in raw_tags.split(',') if t.strip()]
    elif isinstance(raw_tags, list):
        clean_tags = [str(t).strip().lstrip('#') for t in raw_tags if str(t).strip()]
    else:
        clean_tags = []

    # Fallback to authentic defense/tech stock photography if RSS feed provided no image
    if not image_url or not image_url.startswith('http'):
        resolved = media_resolver.resolve_secondary_image(
            full_report.get('Title', ''),
            clean_tags,
            full_report.get('Category', 'Intelligence')
        )
        image_url = resolved['url']

    frontmatter = {
        'title':            full_report.get('Title', ''),
        'seo_title':        full_report.get('seo_title', '')[:60],
        'meta_description': full_report.get('meta_description', '')[:155],
        'social_hook':      full_report.get('social_hook', '')[:280],
        'slug':             slug,
        'category':         full_report.get('Category', 'Intelligence'),
        'seo_tags':         clean_tags,
        'image_url':        image_url,
        'source_url':       link,
        'published_at':     published,
        'reading_time':     full_report.get('Reading Time', 6),
        'executive_summary': full_report.get('Executive Summary', ''),
        'key_takeaways':    full_report.get('Key Takeaways', []),
        'article_url':      f'articles/{slug}.html',
        'draft':            False,
        'posted_to_discord': False,
    }
    # Include FAQ only if explicitly present and non-empty
    if full_report.get('FAQ'):
        frontmatter['faq'] = full_report.get('FAQ')

    body = full_report.get('Article Body', '')
    content = f"---\n{yaml.dump(frontmatter, sort_keys=False, allow_unicode=True)}---\n\n{body}\n"
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    logging.info(f"Written: {filepath}")

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    seen_urls = load_seen_urls()  # O(1) set lookup
    processed = 0
    new_slugs = []

    # Shuffle feeds to ensure we get a random mix of Indian and Western news,
    # since we are only pulling 1 article per run to save Zapier/dlvr.it quotas.
    random.shuffle(RSS_FEEDS)

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

            # Anti-Spam Topic Filter: Skip consumer gadgets, discounts, shopping deals
            if not is_relevant_topic(title, summary):
                logging.info(f"Skipping consumer/irrelevant topic: {title[:60]}")
                seen_urls.add(link)
                continue

            published = getattr(entry, 'published', datetime.now(timezone.utc).isoformat())
            image_url = get_image_url(entry)

            # Rate-limit pause before API call
            if processed > 0:
                time.sleep(RATE_LIMIT_SLEEP)

            # Fetch article text — lightweight
            text = fetch_article_text(link, summary)
            if not text:
                logging.warning(f"No text extracted, skipping: {link}")
                seen_urls.add(link)
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
