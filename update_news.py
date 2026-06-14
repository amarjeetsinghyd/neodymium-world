import feedparser
import json
import os
import re
import google.generativeai as genai
from datetime import datetime
import trafilatura
from urllib.parse import urlparse
from jinja2 import Environment, FileSystemLoader

# Configure Gemini API
API_KEY = os.environ.get("GEMINI_API_KEY")
if not API_KEY:
    raise ValueError("GEMINI_API_KEY environment variable not set.")

genai.configure(api_key=API_KEY)
# Use a recommended gemini model
model = genai.GenerativeModel('gemini-1.5-flash')

# Feed configuration
# Using a standard Tech/Defense RSS Feed (Breaking Defense as an example)
RSS_FEED_URL = "https://breakingdefense.com/feed/"
DATA_FILE = "news_data.json"

def get_image_url(entry):
    """Extracts image URL from an RSS entry if available."""
    # Check for media content
    if 'media_content' in entry and len(entry.media_content) > 0:
        return entry.media_content[0].get('url')
    # Check for enclosures
    if 'enclosures' in entry and len(entry.enclosures) > 0:
        for enc in entry.enclosures:
            if 'image' in enc.get('type', ''):
                return enc.get('href')
    # Regex fallback to find image in summary
    if 'summary' in entry:
        match = re.search(r'<img[^>]+src="([^">]+)"', entry.summary)
        if match:
            return match.group(1)
    return None

def rewrite_content(title, text):
    """Uses Gemini to rewrite article into an Intelligence Report."""
    prompt = f"""
You are a Chief Defense Analyst. Rewrite this article into a professional, high-impact 500-word Intelligence Report.
Include: Executive Summary, Technical Deep-Dive, Strategic Impact, and Conclusion.
Use a formal, institutional tone.

Original Title: {title}
Original Content: {text}

Respond strictly in the following JSON format without any markdown blocks or extra text:
{{
    "full_report": {{
        "executive_summary": "Summary here...",
        "technical_deep_dive": "Deep dive here...",
        "strategic_impact": "Impact assessment here...",
        "conclusion": "Conclusion here..."
    }}
}}
"""
    try:
        response = model.generate_content(prompt)
        # Clean up response if it contains markdown JSON blocks
        result_text = response.text.strip()
        if result_text.startswith("```json"):
            result_text = result_text[7:-3].strip()
        elif result_text.startswith("```"):
            result_text = result_text[3:-3].strip()
        
        rewritten_data = json.loads(result_text)
        return rewritten_data.get("full_report", {})
    except Exception as e:
        print(f"Error during Gemini rewriting: {e}")
        # Fallback
        return {
            "executive_summary": text[:200] + "...",
            "technical_deep_dive": "Pending technical analysis.",
            "strategic_impact": "Analysis pending.",
            "conclusion": "Pending conclusion."
        }

def main():
    print(f"Fetching RSS feed from {RSS_FEED_URL}...")
    feed = feedparser.parse(RSS_FEED_URL)
    
    # Setup Jinja2 Environment
    env = Environment(loader=FileSystemLoader('.'))
    try:
        template = env.get_template('article_template.html')
    except Exception as e:
        print(f"Could not load article_template.html: {e}")
        return

    # Ensure articles directory exists
    os.makedirs('articles', exist_ok=True)
    
    # Load existing data
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            try:
                existing_news = json.load(f)
            except json.JSONDecodeError:
                existing_news = []
    else:
        existing_news = []

    existing_links = {item.get('original_link', item.get('link')) for item in existing_news}
    new_items = []

    # Process top 5 entries
    for entry in feed.entries[:5]:
        link = entry.link
        if link in existing_links:
            continue
            
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
        
        full_report = rewrite_content(title, article_text)
        
        # Generate Slug
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
            
        news_item = {
            "title": title,
            "full_report": full_report,
            "original_link": link,
            "image_url": image_url,
            "published_at": published_date,
            "added_at": datetime.utcnow().isoformat(),
            "slug": slug,
            "article_url": article_url
        }
        new_items.append(news_item)
        
        # Render and save static HTML
        html_content = template.render(
            title=title,
            full_report=full_report,
            image_url=image_url,
            published_at=published_date,
            original_link=link,
            publisher_name=publisher_name
        )
        with open(article_url, 'w', encoding='utf-8') as f:
            f.write(html_content)
        print(f"Generated static page: {article_url}")

    if new_items:
        print(f"Adding {len(new_items)} new articles.")
        # Prepend new items
        updated_news = new_items + existing_news
        # Keep only the latest 50 articles to prevent massive files
        updated_news = updated_news[:50]
        
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(updated_news, f, indent=4, ensure_ascii=False)
        print("Updated news_data.json successfully.")
    else:
        print("No new articles found.")

if __name__ == "__main__":
    main()
