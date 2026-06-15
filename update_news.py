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
from jinja2 import Environment, FileSystemLoader

# Configure Gemini API
API_KEY = os.environ.get("GEMINI_API_KEY")
if not API_KEY:
    raise ValueError("GEMINI_API_KEY environment variable not set.")

# Feed configuration
RSS_FEEDS = [
    "https://breakingdefense.com/feed/",
    "https://techcrunch.com/category/artificial-intelligence/feed/",
    "https://www.wired.com/feed/category/tech/latest/rss",
    "https://idrw.org/feed/",
    "https://www.thehindu.com/sci-tech/technology/feeder/default.rss",
    "https://analyticsindiamag.com/feed/"
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
        match = re.search(r'<img[^>]+src="([^">]+)"', entry.summary)
        if match:
            return match.group(1)
    return None

def rewrite_content(title, text):
    """Uses Gemini to rewrite article into an Intelligence Report."""
    prompt = f"""
You are a Chief Defense Analyst. Rewrite this article in its entirety. Do not summarize or shorten it. Produce a comprehensive, highly elaborative Intelligence Report that matches or exceeds the length and depth of the original article.
Include: Executive Summary, Technical Deep-Dive, Strategic Impact, and Conclusion. The Technical Deep-Dive should be exceptionally detailed.
Use a formal, institutional tone.

Original Title: {title}
Original Content: {text}

Respond strictly in the following JSON format without any markdown blocks or extra text:
{{
    "category": "One of: Geopolitics, Defense Technology, Cyber Security, Space Economy, AI & Autonomy, Global Tech",
    "full_report": {{
        "executive_summary": "Summary here...",
        "technical_deep_dive": "Deep dive here...",
        "strategic_impact": "Impact assessment here...",
        "conclusion": "Conclusion here..."
    }}
}}
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
        data = resp.json()
        
        if "error" in data:
            raise Exception(f"API Error {data['error'].get('code')}: {data['error'].get('message')}")
            
        result_text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
        
        if result_text.startswith("```json"):
            result_text = result_text[7:-3].strip()
        elif result_text.startswith("```"):
            result_text = result_text[3:-3].strip()
            
        rewritten_data = json.loads(result_text)
        
        if "full_report" in rewritten_data and "category" in rewritten_data:
            return rewritten_data
        elif "full_report" in rewritten_data:
            return {"category": "Global Tech", "full_report": rewritten_data["full_report"]}
        elif "executive_summary" in rewritten_data:
            return {"category": "Global Tech", "full_report": rewritten_data}
        else:
            return {"category": "Global Tech", "full_report": rewritten_data.get("full_report", {})}
            
    except Exception as e:
        print(f"Error during Gemini rewriting: {e}")
        
        # Debug: Fetch available models
        available_models_text = "Could not fetch models list."
        try:
            models_url = f"https://generativelanguage.googleapis.com/v1beta/models?key={API_KEY}"
            models_resp = requests.get(models_url)
            models_data = models_resp.json()
            if "models" in models_data:
                model_names = [m.get("name") for m in models_data["models"]]
                available_models_text = "Available models on this API key: " + ", ".join(model_names)
            else:
                available_models_text = f"Models fetch error: {models_data}"
        except Exception as ex:
            available_models_text = f"Failed to list models: {ex}"

        return {
            "category": "Error",
            "full_report": {
                "executive_summary": text[:200] + "...",
                "technical_deep_dive": f"Exception occurred during generation: {str(e)}\n\nDEBUG INFO:\n{available_models_text}",
                "strategic_impact": "Analysis pending.",
                "conclusion": "Pending conclusion."
            }
        }

def main():
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
                data = json.load(f)
                existing_news = data.get("articles", []) if isinstance(data, dict) else data
            except json.JSONDecodeError:
                existing_news = []
    else:
        existing_news = []

    existing_links = {item.get('original_link', item.get('link')) for item in existing_news}
    new_items = []

    entries_to_process = []
    for feed_url in RSS_FEEDS:
        print(f"Fetching RSS feed from {feed_url}...")
        feed = feedparser.parse(feed_url)
        count = 0
        for entry in feed.entries:
            if entry.link in existing_links:
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
        
        rewrite_result = rewrite_content(title, article_text)
        category = rewrite_result.get("category", "Global Tech")
        full_report = rewrite_result.get("full_report", {})
        
        # Convert markdown fields to HTML
        for key in full_report:
            if isinstance(full_report[key], str):
                full_report[key] = markdown.markdown(full_report[key])
        
        # Free Tier Rate Limit Handling: 5 Requests Per Minute = 12.5 seconds per request.
        time.sleep(12.5)
        
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
            "category": category,
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
            category=category,
            full_report=full_report,
            image_url=image_url,
            published_at=published_date,
            original_link=link,
            publisher_name=publisher_name
        )
        with open(article_url, 'w', encoding='utf-8') as f:
            f.write(html_content)
        print(f"Generated static page: {article_url}")

    # Build missing HTML files (for CMS manual entries)
    for item in existing_news:
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
                
            html_content = template.render(
                title=item.get("title", ""),
                category=item.get("category", "Intelligence"),
                full_report=report,
                image_url=item.get("image_url", ""),
                published_at=item.get("published_at", ""),
                original_link=item.get("original_link", "#"),
                publisher_name=pub_name
            )
            with open(item["article_url"], 'w', encoding='utf-8') as f:
                f.write(html_content)

    if new_items:
        print(f"Adding {len(new_items)} new articles.")
        # Prepend new items
        updated_news = new_items + existing_news
        # Keep up to 1000 articles to build a deep historical database
        updated_news = updated_news[:1000]
        
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump({"articles": updated_news}, f, indent=4, ensure_ascii=False)
        print("Updated news_data.json successfully.")
    else:
        print("No new articles found.")

if __name__ == "__main__":
    main()
