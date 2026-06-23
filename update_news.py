import feedparser
import json
import os
import re
import requests
import time
import trafilatura
import markdown
from datetime import datetime
from urllib.parse import urlparse
from jinja2 import Environment, FileSystemLoader, select_autoescape
from bs4 import BeautifulSoup
import database

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
DATA_FILE = "news_data.json"

def get_image_url(entry):
    """Extracts image URL from an RSS entry if available."""
    if 'media_content' in entry and len(entry.media_content) > 0:
        return entry.media_content[0].get('url')
    if 'enclosures' in entry and len(entry.enclosures) > 0:
        for enc in entry.enclosures:
            if 'image' in enc.get('type', ''):
                return enc.get('href')
    if 'summary' in entry:
        soup = BeautifulSoup(entry.summary, 'html.parser')
        img_tag = soup.find('img')
        if img_tag and img_tag.get('src'):
            return img_tag['src']
    return None

class CriticalAPIError(Exception):
    """Custom exception for critical Gemini API errors like quota limits."""
    pass

def rewrite_content(title, text):
    """Uses Gemini to rewrite article into an Intelligence Report."""
    prompt = f"""
You are a Chief Defense Analyst. Rewrite this article in its entirety. Do not summarize or shorten it. Produce a comprehensive, highly elaborative Intelligence Report that matches or exceeds the length and depth of the original article.

Core Guidelines:
1. Unique, Analytical Headlines: Generate a completely original, highly analytical, and intelligence-oriented headline for this report. The headline MUST be distinct and different from the original title, framing the issue from a strategic intelligence, market-disruption, or geopolitical perspective rather than a standard news report.
2. Premium Value-Add: If the article contains strategic, geopolitical, or highly technical elements, create a section for it. But if it is a simple startup funding round or product launch, adjust your headings to be "Market Analysis", "Funding Details", etc. Be completely flexible with your section headings.
3. Detail: The Technical Deep-Dive should be exceptionally detailed and analytical.
4. Tone: Use a formal, institutional tone.
5. Formatting: Ensure you use proper Markdown formatting. ALWAYS place a blank line before starting any bulleted or numbered list.
6. AI Gatekeeper (Strict Filtering): Carefully analyze the core subject of the Original Content. If the article is NOT fundamentally about one of the following four topics: "Tech Startups", "Global Tech Innovations", "Artificial Intelligence", or "Defense Technology", you MUST reject it. To reject an article, return exactly this JSON and nothing else: {"error": "IRRELEVANT_TOPIC"}

Original Title: {title}
Original Content: {text}

Respond strictly in the following JSON format without any markdown blocks or extra text:
{{
    "headline": "Your newly generated original headline...",
    "category": "One of: Tech Startups, Global Tech, AI & Autonomy, Defense Technology",
    "seo_tags": ["#Tag1", "#Tag2", "#Tag3"],
    "full_report": {{
        "Overview": "Summary here...",
        "Dynamic Heading 1": "Dynamic content here based on the story...",
        "Dynamic Heading 2": "Dynamic content here based on the story...",
        "Dynamic Heading N": "More sections as needed..."
    }}
}}
(Or return {"error": "IRRELEVANT_TOPIC"} if it violates rule 6)
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
        
        resp = requests.post(url, json=payload)
        if resp.status_code == 429:
            raise CriticalAPIError(f"API Quota/Rate Limit Exceeded (HTTP 429): {resp.text}")
            
        resp.raise_for_status()
        data = resp.json()
        
        if "error" in data:
            err_code = data['error'].get('code')
            err_msg = data['error'].get('message', '')
            if err_code == 429 or any(x in err_msg.lower() for x in ["quota", "exhausted", "limit", "rate"]):
                raise CriticalAPIError(f"API Quota/Rate Limit Exceeded: {err_msg}")
            raise Exception(f"API Error {err_code}: {err_msg}")
            
        result_text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
        
        if result_text.startswith("```json"):
            result_text = result_text[7:-3].strip()
        elif result_text.startswith("```"):
            result_text = result_text[3:-3].strip()
            
        rewritten_data = json.loads(result_text)
        
        if "error" in rewritten_data and rewritten_data["error"] == "IRRELEVANT_TOPIC":
            print(f"  -> AI Gatekeeper rejected article: Not about Tech/AI/Defense.")
            return None
        
        if "full_report" in rewritten_data and "category" in rewritten_data:
            return rewritten_data
        elif "full_report" in rewritten_data:
            return {"category": "Global Tech", "full_report": rewritten_data["full_report"]}
        elif "executive_summary" in rewritten_data:
            return {"category": "Global Tech", "full_report": rewritten_data}
        else:
            return {"category": "Global Tech", "full_report": rewritten_data.get("full_report", {})}
            
    except CriticalAPIError as e:
        raise e
    except Exception as e:
        print(f"Error during Gemini rewriting: {e}")
        # If API fails (like 503 overload), we return None so the script skips this article
        # rather than publishing an 'ERROR' tagged placeholder.
        return None

def build_index_html():
    """Generates the static index.html and rss.xml from templates."""
    try:
        env = Environment(
            loader=FileSystemLoader('.'),
            autoescape=select_autoescape(['html', 'xml'])
        )
    except Exception as e:
        print(f"Could not load templates: {e}")
        return

def main():
    # Setup Jinja2 Environment
    env = Environment(
        loader=FileSystemLoader('.'),
        autoescape=select_autoescape(['html', 'xml'])
    )
    try:
        template = env.get_template('article_template.html')
    except Exception as e:
        print(f"Could not load templates: {e}")
        return

    # Ensure articles directory exists
    os.makedirs('articles', exist_ok=True)
    
    # Initialize SQLite database
    database.init_db()

    new_items = []

    entries_to_process = []
    for feed_url in RSS_FEEDS:
        print(f"Fetching RSS feed from {feed_url}...")
        feed = feedparser.parse(feed_url)
        count = 0
        for entry in feed.entries:
            if database.is_duplicate(entry.link):
                continue
            entries_to_process.append(entry)
            count += 1
            if count >= 2:
                break
        if len(entries_to_process) >= 5:
            break
            
    entries_to_process = entries_to_process[:5]

    # Process up to 5 entries
    for entry in entries_to_process:
        link = entry.link
        title = entry.title
        # Clean HTML from description
        raw_description = re.sub(r'<[^>]+>', '', entry.get('summary', ''))
        image_url = get_image_url(entry)
        published_date = entry.get('published', datetime.utcnow().isoformat())
        
        print(f"Processing new article: {title}")
        
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
        
        print(f"\nProcessing: {title}")
        
        try:
            rewritten_content = rewrite_content(title, article_text)
        except CriticalAPIError as ce:
            print(f"Critical API Error: {ce}. Halting article generation for this instance. Remaining pipeline tasks will continue.")
            break
            
        if not rewritten_content:
            print("Skipping article due to AI processing failure.")
            continue
            
        full_report = rewritten_content.get("full_report", {})
        category = rewritten_content.get("category", "Intelligence")
        seo_tags = rewritten_content.get("seo_tags", [])
        
        # Override the original title with the AI-generated headline to prevent copyright match
        title = rewritten_content.get("headline", title)
        
        # Convert markdown fields to HTML
        for key in full_report:
            if isinstance(full_report[key], str):
                text = full_report[key]
                # Remove leading spaces before bullet points to prevent <pre><code> blocks
                text = re.sub(r'^[ \t]+([\*\-]) ', r'\1 ', text, flags=re.MULTILINE)
                # Ensure blank lines before lists so python-markdown parses them correctly
                text = re.sub(r'([^\n])\n(\s*[\*\-])\s', r'\1\n\n\2 ', text)
                full_report[key] = markdown.markdown(text)
        
        # Free Tier Rate Limit Handling: 5 Requests Per Minute = 12.5 seconds per request.
        time.sleep(12.5)
        
        # Generate slug from the NEW title
        slug = re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-')
        if not slug:
            slug = f"article-{int(datetime.utcnow().timestamp())}"
        
        article_url = f"articles/{slug}.html"
        
        # Parse publisher name
        publisher_name = "Unknown Source"
        try:
            publisher_name = urlparse(link).netloc.replace('www.', '')
        except:
            publisher_name = link
            
        word_count = sum(len(str(v).split()) for v in full_report.values())
        reading_time = max(1, round(word_count / 200))
            
        news_item = {
            "title": title,
            "category": category,
            "seo_tags": seo_tags,
            "full_report": full_report,
            "original_link": link,
            "image_url": image_url,
            "published_at": published_date,
            "added_at": datetime.utcnow().isoformat(),
            "slug": slug,
            "article_url": article_url,
            "reading_time": reading_time
        }
        new_items.append(news_item)
        # Render and save static HTML
        try:
            html_content = template.render(
                title=title,
                category=category,
                seo_tags=seo_tags,
                full_report=full_report,
                image_url=image_url,
                published_at=published_date,
                original_link=link,
                publisher_name=publisher_name,
                slug=slug,
                reading_time=reading_time
            )
            with open(article_url, 'w', encoding='utf-8') as f:
                f.write(html_content)
            print(f"Generated static page: {article_url}")
        except Exception as e:
            print(f"Failed to render HTML for new article '{title}': {e}")
            
        # Insert into database
        if database.insert_article(news_item):
            print(f"Successfully inserted into database: {title}")

    # Export feed for frontend
    database.export_frontend_feed()
    
    # Get all articles for RSS, Sitemap, and Missing HTML rebuilding
    updated_news = database.get_all_articles(limit=1000)

    # Build missing HTML files (for CMS manual entries)
    for item in updated_news:
        if "article_url" in item and not os.path.exists(item["article_url"]):
            print(f"Rebuilding missing HTML for: {item.get('title')}")
            # Format markdown if necessary
            report = item.get("full_report", {})
            for key in report:
                if isinstance(report[key], str) and not report[key].strip().startswith("<"):
                    report[key] = markdown.markdown(report[key])
            
            pub_name = "Neodymium Intel"
            try:
                if item.get("original_link") and "http" in item["original_link"]:
                    pub_name = urlparse(item["original_link"]).netloc.replace('www.', '')
            except:
                pass
                
            try:
                html_content = template.render(
                    title=item.get("title", ""),
                    category=item.get("category", "Intelligence"),
                    seo_tags=item.get("seo_tags", []),
                    full_report=report,
                    image_url=item.get("image_url", ""),
                    published_at=item.get("published_at", ""),
                    original_link=item.get("original_link", "#"),
                    publisher_name=pub_name,
                    slug=item.get("slug", ""),
                    reading_time=item.get("reading_time", max(1, round(sum(len(str(v).split()) for v in report.values()) / 200)))
                )
                with open(item["article_url"], 'w', encoding='utf-8') as f:
                    f.write(html_content)
            except Exception as e:
                print(f"Failed to rebuild HTML for '{item.get('title')}': {e}")

    # Generate RSS Feed
    try:
        rss_template = env.get_template('rss_template.xml')
        rss_content = rss_template.render(articles=updated_news[:50])
        with open('rss.xml', 'w', encoding='utf-8') as f:
            f.write(rss_content)
        print("Successfully generated rss.xml")
    except Exception as e:
        print(f"Failed to generate RSS feed: {e}")

    # Generate Sitemap
    try:
        sitemap_template = env.get_template('sitemap_template.xml')
        sitemap_content = sitemap_template.render(articles=updated_news, current_date=datetime.utcnow().strftime('%Y-%m-%d'))
        with open('sitemap.xml', 'w', encoding='utf-8') as f:
            f.write(sitemap_content)
        print("Successfully generated sitemap.xml")
    except Exception as e:
        print(f"Failed to generate Sitemap: {e}")

if __name__ == "__main__":
    main()
