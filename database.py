import sqlite3
import json
import os

DB_FILE = 'neodymium.db'
FEED_FILE = 'news_data.json'

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            slug TEXT NOT NULL,
            article_url TEXT NOT NULL,
            original_link TEXT UNIQUE NOT NULL,
            image_url TEXT,
            published_at TEXT,
            added_at TEXT,
            reading_time INTEGER,
            category TEXT,
            seo_tags TEXT,
            full_report TEXT,
            posted_to_discord BOOLEAN DEFAULT 0
        )
    ''')
    try:
        cursor.execute("ALTER TABLE articles ADD COLUMN twitter_thread TEXT")
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("ALTER TABLE articles ADD COLUMN linkedin_post TEXT")
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("ALTER TABLE articles ADD COLUMN discord_post TEXT")
    except sqlite3.OperationalError:
        pass
    conn.commit()
    conn.close()

def insert_article(article_data):
    """
    Inserts a new article into the SQLite database.
    Returns True if successful, False if it was a duplicate (original_link exists).
    """
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    seo_tags_json = json.dumps(article_data.get('seo_tags', []))
    full_report_json = json.dumps(article_data.get('full_report', {}))
    
    try:
        cursor.execute('''
            INSERT INTO articles (
                title, slug, article_url, original_link, image_url, 
                published_at, added_at, reading_time, category, 
                seo_tags, full_report, twitter_thread, linkedin_post, discord_post

            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            article_data.get('title'),
            article_data.get('slug'),
            article_data.get('article_url'),
            article_data.get('original_link'),
            article_data.get('image_url'),
            article_data.get('published_at'),
            article_data.get('added_at'),
            article_data.get('reading_time', 5),
            article_data.get('category', 'Intelligence'),
            seo_tags_json,
            full_report_json,
            json.dumps(article_data.get('twitter_thread', [])),
            article_data.get('linkedin_post', ''),
            article_data.get('discord_post', '')
        ))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        # This handles the UNIQUE constraint on original_link (preventing duplicates)
        return False
    finally:
        conn.close()

def get_all_articles(limit=50):
    """
    Retrieves the latest articles from the database.
    """
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT * FROM articles 
        ORDER BY added_at DESC
        LIMIT ?
    ''', (limit,))
    
    rows = cursor.fetchall()
    articles = []
    
    for row in rows:
        article = dict(row)
        # Deserialize JSON fields
        try:
            article['seo_tags'] = json.loads(article['seo_tags'])
        except:
            article['seo_tags'] = []
            
        try:
            article['full_report'] = json.loads(article['full_report'])
        except:
            article['full_report'] = {}
            
        try:
            article['twitter_thread'] = json.loads(article['twitter_thread']) if article.get('twitter_thread') else []
        except:
            article['twitter_thread'] = []
            
        articles.append(article)
        
    conn.close()
    return articles

def is_duplicate(original_link):
    """Checks if an original_link already exists in the database."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('SELECT 1 FROM articles WHERE original_link = ?', (original_link,))
    exists = cursor.fetchone() is not None
    conn.close()
    return exists

def export_frontend_feed():
    """
    Exports the latest 50 articles from the SQLite database to news_data.json
    for the frontend UI to consume efficiently.
    """
    articles = get_all_articles(limit=50)
    with open(FEED_FILE, 'w', encoding='utf-8') as f:
        json.dump(articles, f, indent=4)

def export_automation_feed():
    """
    Exports the latest 10 articles with their Twitter threads for Make.com automation.
    Formats the payload nicely for easy parsing.
    """
    articles = get_all_articles(limit=10)
    automation_data = []
    for a in articles:
        automation_data.append({
            "title": a.get("title"),
            "url": f"https://neodymium.world/{a.get('article_url')}",
            "report_content": a.get("full_report", {}),
            "published_at": a.get("published_at")
        })
    with open("automation_feed.json", 'w', encoding='utf-8') as f:
        json.dump(automation_data, f, indent=4)
    print(f"Exported {len(articles)} articles to {FEED_FILE} for the frontend.")

if __name__ == '__main__':
    init_db()
    print("Database initialized successfully.")
