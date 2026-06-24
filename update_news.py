import feedparser
import json
import os
import re
import requests
import time
import trafilatura
import yaml
import traceback
import logging
from datetime import datetime
from urllib.parse import urlparse

# Configure logging
logging.basicConfig(
    filename='error.log',
    level=logging.ERROR,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Configure Gemini API
API_KEY = os.environ.get("GEMINI_API_KEY")
if not API_KEY:
    raise ValueError("GEMINI_API_KEY environment variable not set.")

# Feed configuration
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

def get_image_url(entry):
    if 'media_content' in entry and len(entry.media_content) > 0:
        return entry.media_content[0].get('url')
    if 'enclosures' in entry and len(entry.enclosures) > 0:
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
    prompt = f"""
You are a Chief Defense Analyst. Rewrite this article in its entirety. Do not summarize or shorten it. Produce a comprehensive, highly elaborative Intelligence Report that matches or exceeds the length and depth of the original article.

Core Guidelines:
1. Unique, Analytical Headlines: Generate a completely original, highly analytical, and intelligence-oriented headline for this report. The headline MUST be distinct and different from the original title, framing the issue from a strategic intelligence, market-disruption, or geopolitical perspective rather than a standard news report.
2. Premium Value-Add: If the article contains strategic, geopolitical, or highly technical elements, create a section for it. But if it is a simple startup funding round or product launch, adjust your headings to be "Market Analysis", "Funding Details", etc. Be completely flexible with your section headings.
3. Detail: The Technical Deep-Dive should be exceptionally detailed and analytical.
4. Tone: Use a formal, institutional tone.
5. Formatting: Ensure you use proper Markdown formatting. ALWAYS place a blank line before starting any bulleted or numbered list.
6. AI Gatekeeper (Strict Filtering): Carefully analyze the core subject of the Original Content. If the article is NOT fundamentally about one of the following four topics: "Tech Startups", "Global Tech Innovations", "Artificial Intelligence", or "Defense Technology", you MUST reject it. To reject an article, return exactly this JSON and nothing else: {{"error": "IRRELEVANT_TOPIC"}}

Original Title: {title}
Original Content: {text}

Respond strictly in the following JSON format without any markdown blocks or extra text:
{{
    "headline": "Your newly generated original headline...",
    "category": "One of: Policy Watch, Global Index, Data Analytics, Intelligence Brief, Tech Startups, Global Tech, AI & Autonomy, Defense Technology",
    "seo_tags": ["#Tag1", "#Tag2", "#Tag3"],
    "full_report": {{
        "Key Takeaways": ["Bullet 1", "Bullet 2", "Bullet 3"],
        "Overview": "Summary here...",
        "Dynamic Heading 1": "Dynamic content here based on the story...",
        "Dynamic Heading 2": "Dynamic content here based on the story...",
        "FAQ": [
            {{"question": "What is the main impact of this?", "answer": "The main impact is..."}},
            {{"question": "Who is affected?", "answer": "..."}}
        ]
    }}
}}
(Or return {{"error": "IRRELEVANT_TOPIC"}} if it violates rule 6)
"""
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={API_KEY}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "responseMimeType": "application/json"
            },
            "safetySettings": [
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}
            ]
        }
        
        response = requests.post(url, json=payload)
        response.raise_for_status()
        data = response.json()
        
        content = data['candidates'][0]['content']['parts'][0]['text']
        content = content.strip()
        if content.startswith("```json"):
            content = content[7:-3]
            
        parsed_json = json.loads(content)
        
        if "error" in parsed_json and parsed_json["error"] == "IRRELEVANT_TOPIC":
            print(f"Skipped: Irrelevant Topic -> {title}")
            return None
            
        return parsed_json
        
    except requests.exceptions.HTTPError as e:
        if response.status_code == 429:
            raise CriticalAPIError("Gemini API Quota Exceeded (429)")
        print(f"API HTTP Error: {e} - Response: {response.text}")
        return None
    except Exception as e:
        print(f"Error calling Gemini API: {e}")
        return None

def is_already_processed(link):
    # Check if a markdown file contains this original link
    articles_dir = 'content/articles'
    if not os.path.exists(articles_dir):
        return False
    for filename in os.listdir(articles_dir):
        if filename.endswith('.md'):
            with open(os.path.join(articles_dir, filename), 'r', encoding='utf-8') as f:
                content = f.read()
                if link in content:
                    return True
    return False

def main():
    print("Starting news gathering process...")
    all_entries = []

    for feed_url in RSS_FEEDS:
        print(f"Fetching {feed_url}...")
        try:
            feed = feedparser.parse(feed_url)
            all_entries.extend(feed.entries)
        except Exception as e:
            error_msg = f"Failed to fetch {feed_url}: {e}"
            print(error_msg)
            logging.error(error_msg + "\n" + traceback.format_exc())

    # Sort entries by published date (newest first) if available
    def get_published(entry):
        try:
            from email.utils import parsedate_to_datetime
            return parsedate_to_datetime(entry.published).timestamp()
        except:
            return 0
            
    all_entries.sort(key=get_published, reverse=True)

    print(f"Found {len(all_entries)} total entries across all feeds.")

    processed_count = 0
    os.makedirs('content/articles', exist_ok=True)

    for entry in all_entries:
        if processed_count >= 10:
            print("Reached maximum limit of 10 articles per run. Stopping.")
            break
            
        link = entry.link
        
        if is_already_processed(link):
            continue
            
        title = entry.title
        raw_description = re.sub(r'<[^>]+>', '', entry.get('summary', ''))
        image_url = get_image_url(entry)
        published_date = entry.get('published', datetime.utcnow().isoformat())
        
        print(f"\nProcessing: {title}")
        
        # Scrape full text with Trafilatura
        article_text = raw_description
        downloaded = trafilatura.fetch_url(link)
        if downloaded:
            extracted = trafilatura.extract(downloaded, output_format='json')
            if extracted:
                try:
                    ext_data = json.loads(extracted)
                    if ext_data.get('text'):
                        article_text = ext_data['text']
                    if ext_data.get('image'):
                        image_url = ext_data['image']
                except json.JSONDecodeError:
                    pass
        
        try:
            rewritten_content = rewrite_content(title, article_text)
        except CriticalAPIError as ce:
            print(f"Critical API Error: {ce}. Halting article generation for this instance.")
            break
            
        if not rewritten_content:
            continue
            
        full_report = rewritten_content.get("full_report", {})
        category = rewritten_content.get("category", "Intelligence")
        seo_tags = rewritten_content.get("seo_tags", [])
        
        # Override the original title with the AI-generated headline to prevent copyright match
        title = rewritten_content.get("headline", title)
        
        key_takeaways = full_report.pop("Key Takeaways", [])
        faq = full_report.pop("FAQ", [])

        # Build the body markdown
        body_md = ""
        for section_name, section_content in full_report.items():
            if section_name in ["Key Takeaways", "FAQ", "executive_summary"]:
                continue
            formatted_name = section_name.replace('_', ' ').title()
            body_md += f"## {formatted_name}\n\n{section_content}\n\n"
        
        # Free Tier Rate Limit Handling: 5 Requests Per Minute = 12.5 seconds per request.
        time.sleep(12.5)
        
        # Generate slug
        slug = re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-')
        if not slug:
            slug = f"article-{int(datetime.utcnow().timestamp())}"
        
        word_count = len(body_md.split())
        reading_time = max(1, round(word_count / 200))
            
        frontmatter = {
            "title": title,
            "slug": slug,
            "category": category,
            "seo_tags": seo_tags,
            "image_url": image_url,
            "original_link": link,
            "published_at": published_date,
            "added_at": datetime.utcnow().isoformat(),
            "reading_time": reading_time,
            "draft": True,
        }
        
        if key_takeaways:
            frontmatter["key_takeaways"] = key_takeaways
        if faq:
            frontmatter["faq"] = faq

        md_content = f"---\n{yaml.dump(frontmatter, sort_keys=False, allow_unicode=True)}---\n\n{body_md}"
        
        filepath = f"content/articles/{slug}.md"
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(md_content)
            
        print(f"Successfully created: {filepath}")
        processed_count += 1

    print("Generation complete! Recompiling HTML...")
    os.system("python recompile_html.py")

if __name__ == "__main__":
    main()
