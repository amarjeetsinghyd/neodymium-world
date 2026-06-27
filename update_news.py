import feedparser
import json
import os
import re
import requests
import sys
import time
import trafilatura
import yaml
import traceback
import logging
from datetime import datetime, timezone
from urllib.parse import urlparse

# --- Logging ---
# In CI (GitHub Actions) there is no persistent filesystem — log to stdout
# so output appears in the Actions run log. Locally, this still prints to
# the terminal. run_log.txt is gitignored and not created here.
logging.basicConfig(
    stream=sys.stdout,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

API_KEY = os.environ.get("GEMINI_API_KEY")
if not API_KEY:
    raise ValueError("GEMINI_API_KEY environment variable not set.")

RSS_FEEDS = [
    "https://breakingdefense.com/feed/",
    "https://techcrunch.com/category/artificial-intelligence/feed/",
    "https://www.wired.com/feed/category/tech/latest/rss",
    "http://www.indiandefensenews.in/feeds/posts/default?alt=rss",
    "https://www.thehindu.com/sci-tech/technology/feeder/default.rss",
    "https://yourstory.com/feed",
    "https://inc42.com/feed/",
    "https://feeds.feedburner.com/ndtv-gadgets-360",
    "https://www.firstpost.com/feed/rss/tech",
    "https://indianexpress.com/section/india/feed/",
    "https://venturebeat.com/category/ai/feed/",
    "https://www.technologyreview.com/feed/"
]

ARTICLES_DIR = 'content/articles'
MAX_ARTICLES_PER_RUN = 10


def sanitize_filename(name):
    """Remove spaces, colons, and special chars from image filenames."""
    return re.sub(r'[^a-z0-9._-]', '-', name.lower()).strip('-')


def get_image_url(entry):
    if 'media_content' in entry and entry.media_content:
        return entry.media_content[0].get('url')
    if 'enclosures' in entry and entry.enclosures:
        for enc in entry.enclosures:
            if 'image' in enc.get('type', ''):
                return enc.get('href')
    if 'summary' in entry:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(entry.summary, 'html.parser')
        img_tag = soup.find('img')
        if img_tag and img_tag.get('src'):
            return img_tag['src']
    return None


class CriticalAPIError(Exception):
    pass


def rewrite_content(title, text):
    """Send article to Gemini for rewriting. Returns parsed JSON or None."""
    MAX_CHARS = 8000
    if len(text) > MAX_CHARS:
        text = text[:MAX_CHARS] + "...[truncated]"

    prompt = f"""
You are a Chief Defense and Technology Analyst. Rewrite this article as a comprehensive, institutional intelligence report.

Core Guidelines:
1. Generate a completely original, analytical, intelligence-oriented HEADLINE (max 110 characters).
2. Generate a SHORT SEO TITLE (max 55 characters) for the HTML <title> tag — punchy, keyword-rich.
3. Generate a META DESCRIPTION (max 155 characters) — summarises the report's key finding for search engine snippets.
4. Generate a SOCIAL HOOK (max 280 characters) — an engaging opening statement for Twitter/LinkedIn. Use no hashtags. Start with a provocative fact or number.
5. Generate THREAD TWEETS — an array of 2 additional tweet strings (each max 270 chars) that continue the social hook as a thread. Include key data points.
6. Produce a full intelligence report body in Markdown.
7. If the article is NOT about Tech Startups, Global Tech, AI, or Defense Technology, return exactly: {{"error": "IRRELEVANT_TOPIC"}}

Original Title: {title}
Original Content: {text}

Respond strictly in this JSON format (no markdown blocks, no extra text):
{{
    "headline": "Original analytical headline (max 110 chars)",
    "seo_title": "Short punchy SEO title (max 55 chars)",
    "meta_description": "Search snippet description (max 155 chars)",
    "social_hook": "Opening tweet/LinkedIn post (max 280 chars, no hashtags)",
    "thread_tweets": ["Tweet 2 continuation (max 270 chars)", "Tweet 3 continuation (max 270 chars)"],
    "category": "One of: Policy Watch, Global Index, Data Analytics, Intelligence Brief, Tech Startups, Global Tech, AI & Autonomy, Defense Technology",
    "seo_tags": ["#Tag1", "#Tag2", "#Tag3"],
    "full_report": {{
        "Key Takeaways": ["Bullet 1", "Bullet 2", "Bullet 3"],
        "Overview": "Summary here...",
        "Dynamic Heading 1": "Dynamic content...",
        "Dynamic Heading 2": "Dynamic content...",
        "FAQ": [
            {{"question": "What is the main impact?", "answer": "..."}},
            {{"question": "Who is affected?", "answer": "..."}}
        ]
    }}
}}
"""
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={API_KEY}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"responseMimeType": "application/json"},
            "safetySettings": [
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}
            ]
        }

        response = requests.post(url, json=payload, timeout=60)
        response.raise_for_status()
        data = response.json()

        candidates = data.get('candidates', [])
        if not candidates:
            logging.warning(f"No candidates returned for: {title}. Response: {data}")
            return None

        candidate = candidates[0]
        finish_reason = candidate.get('finishReason', '')
        if finish_reason not in ('STOP', ''):
            logging.warning(f"Non-STOP finish_reason '{finish_reason}' for: {title}")
            return None

        content = candidate['content']['parts'][0]['text'].strip()
        if content.startswith("```json"):
            content = content[7:]
        if content.endswith("```"):
            content = content[:-3]

        parsed_json = json.loads(content)

        if parsed_json.get("error") == "IRRELEVANT_TOPIC":
            print(f"Skipped (irrelevant): {title}")
            return None

        return parsed_json

    except requests.exceptions.HTTPError as e:
        if response.status_code == 429:
            raise CriticalAPIError("Gemini API Quota Exceeded (429)")
        logging.error(f"API HTTP Error for '{title}': {e}")
        return None
    except (json.JSONDecodeError, KeyError) as e:
        logging.error(f"JSON/Key parse error for '{title}': {e}")
        return None
    except Exception as e:
        logging.error(f"Gemini API error for '{title}': {e}\n{traceback.format_exc()}")
        return None


def is_already_processed(link):
    if not os.path.exists(ARTICLES_DIR):
        return False
    for filename in os.listdir(ARTICLES_DIR):
        if filename.endswith('.md'):
            filepath = os.path.join(ARTICLES_DIR, filename)
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    if link in f.read():
                        return True
            except OSError:
                pass
    return False


def get_published_timestamp(entry):
    try:
        from email.utils import parsedate_to_datetime
        return parsedate_to_datetime(entry.published).timestamp()
    except Exception:
        return 0


def main():
    print("Starting news gathering process...")
    all_entries = []

    for feed_url in RSS_FEEDS:
        print(f"Fetching {feed_url}...")
        try:
            feed = feedparser.parse(feed_url)
            all_entries.extend(feed.entries)
        except Exception as e:
            logging.error(f"Failed to fetch {feed_url}: {e}\n{traceback.format_exc()}")

    all_entries.sort(key=get_published_timestamp, reverse=True)
    print(f"Found {len(all_entries)} total entries across all feeds.")

    processed_count = 0
    os.makedirs(ARTICLES_DIR, exist_ok=True)

    for entry in all_entries:
        if processed_count >= MAX_ARTICLES_PER_RUN:
            print(f"Reached maximum of {MAX_ARTICLES_PER_RUN} articles. Stopping.")
            break

        link = getattr(entry, 'link', None)
        if not link or is_already_processed(link):
            continue

        title = entry.title
        raw_description = re.sub(r'<[^>]+>', '', entry.get('summary', ''))
        image_url = get_image_url(entry)
        published_date = entry.get('published', datetime.now(timezone.utc).isoformat())

        print(f"\nProcessing: {title}")

        article_text = raw_description
        try:
            downloaded = trafilatura.fetch_url(link)
            if downloaded:
                extracted = trafilatura.extract(downloaded, output_format='json')
                if extracted:
                    ext_data = json.loads(extracted)
                    if ext_data.get('text'):
                        article_text = ext_data['text']
                    if ext_data.get('image'):
                        image_url = ext_data['image']
        except Exception as e:
            logging.warning(f"Trafilatura failed for {link}: {e}")

        if image_url:
            if not image_url.startswith('http'):
                image_url = None
            else:
                url_parts = image_url.rsplit('/', 1)
                if len(url_parts) == 2:
                    image_url = url_parts[0] + '/' + sanitize_filename(url_parts[1])

        if processed_count > 0:
            print("Rate-limit pause: 13 seconds...")
            time.sleep(13)

        try:
            rewritten_content = rewrite_content(title, article_text)
        except CriticalAPIError as ce:
            print(f"Critical API Error: {ce}. Halting.")
            logging.critical(str(ce))
            break

        if not rewritten_content:
            continue

        full_report = rewritten_content.get("full_report", {})
        category = rewritten_content.get("category", "Intelligence")
        seo_tags = rewritten_content.get("seo_tags", [])
        title = rewritten_content.get("headline", title)
        seo_title = rewritten_content.get("seo_title", "")
        meta_description = rewritten_content.get("meta_description", "")
        social_hook = rewritten_content.get("social_hook", "")
        thread_tweets = rewritten_content.get("thread_tweets", [])

        key_takeaways = full_report.pop("Key Takeaways", [])
        faq = full_report.pop("FAQ", [])

        body_md = ""
        for section_name, section_content in full_report.items():
            if section_name in ["Key Takeaways", "FAQ", "executive_summary"]:
                continue
            formatted_name = section_name.replace('_', ' ').title()
            body_md += f"## {formatted_name}\n\n{section_content}\n\n"

        base_slug = re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-')
        if not base_slug:
            base_slug = 'article'
        timestamp_suffix = str(int(datetime.now(timezone.utc).timestamp()))[-6:]
        slug = f"{base_slug[:80]}-{timestamp_suffix}"

        word_count = len(body_md.split())
        reading_time = max(1, round(word_count / 200))

        frontmatter_data = {
            "title": title,
            "seo_title": seo_title,
            "meta_description": meta_description,
            "social_hook": social_hook,
            "thread_tweets": thread_tweets,
            "slug": slug,
            "category": category,
            "seo_tags": seo_tags,
            "image_url": image_url,
            "original_link": link,
            "published_at": published_date,
            "added_at": datetime.now(timezone.utc).isoformat(),
            "reading_time": reading_time,
            # draft: False — articles are published immediately on the next
            # recompile_html.py run. Set to True in the CMS if manual review
            # is preferred before going live.
            "draft": False,
        }

        if key_takeaways:
            frontmatter_data["key_takeaways"] = key_takeaways
        if faq:
            frontmatter_data["faq"] = faq

        md_content = f"---\n{yaml.dump(frontmatter_data, sort_keys=False, allow_unicode=True)}---\n\n{body_md}"

        filepath = os.path.join(ARTICLES_DIR, f"{slug}.md")
        try:
            with open(filepath, "w", encoding='utf-8') as f:
                f.write(md_content)
            print(f"Successfully created: {filepath}")
            logging.info(f"Created: {filepath}")
        except OSError as e:
            logging.error(f"Failed to write {filepath}: {e}")
            continue

        processed_count += 1

    print("Generation complete!")


if __name__ == "__main__":
    main()
