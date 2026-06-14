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
    """Uses Gemini to rewrite title and description into an Executive Brief."""
    prompt = f"""
You are a senior intelligence analyst and editor for a premium, institutional Future Tech and Defense dashboard called 'Neodymium'.
Rewrite the following news title and description into an 'Executive Brief'.
The brief must feature:
1. A crisp Headline (title)
2. 3-4 Bullet points (Technical & Strategic analysis)
3. 'Strategic Impact' assessment (Why this defense/tech shift matters for institutional players)

Remove any clickbait, sensationalism, or informal language. Make it sound highly advanced, objective, and premium.

Original Title: {title}
Original Description: {description}

Respond strictly in the following JSON format without any markdown blocks or extra text:
{{
    "title": "Crisp Headline Here",
    "bullet_points": ["Point 1", "Point 2", "Point 3"],
    "strategic_impact": "Strategic impact assessment here"
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
        return rewritten_data
    except Exception as e:
        print(f"Error during Gemini rewriting: {e}")
        # Fallback
        return {
            "title": title,
            "bullet_points": [description],
            "strategic_impact": "Analysis pending."
        }

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
        rewritten_data = rewrite_content(title, raw_description)
        
        news_item = {
            "title": rewritten_data.get("title", title),
            "bullet_points": rewritten_data.get("bullet_points", [raw_description]),
            "strategic_impact": rewritten_data.get("strategic_impact", "Analysis pending."),
            "original_link": link,
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
