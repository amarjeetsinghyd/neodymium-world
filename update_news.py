import feedparser
import json
import os
import re
import google.generativeai as genai
from datetime import datetime

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

def rewrite_content(title, description):
    """Uses Gemini to rewrite title and description in an institutional tone."""
    prompt = f"""
You are a senior intelligence analyst and editor for a premium, institutional Future Tech and Defense dashboard called 'Neodymium'.
Rewrite the following news title and description into a highly advanced, objective, and premium institutional tone. 
Remove any clickbait, sensationalism, or informal language. Make it sound like an executive briefing.

Original Title: {title}
Original Description: {description}

Respond strictly in the following JSON format without any markdown blocks or extra text:
{{
    "title": "Rewritten Title Here",
    "description": "Rewritten Description Here"
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
        return rewritten_data.get("title", title), rewritten_data.get("description", description)
    except Exception as e:
        print(f"Error during Gemini rewriting: {e}")
        # Fallback to original if rewriting fails
        return title, description

def main():
    print(f"Fetching RSS feed from {RSS_FEED_URL}...")
    feed = feedparser.parse(RSS_FEED_URL)
    
    # Load existing data
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            try:
                existing_news = json.load(f)
            except json.JSONDecodeError:
                existing_news = []
    else:
        existing_news = []

    existing_links = {item['link'] for item in existing_news}
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
        rewritten_title, rewritten_desc = rewrite_content(title, raw_description)
        
        news_item = {
            "title": rewritten_title,
            "description": rewritten_desc,
            "link": link,
            "image_url": image_url,
            "published_at": published_date,
            "added_at": datetime.utcnow().isoformat()
        }
        new_items.append(news_item)

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
