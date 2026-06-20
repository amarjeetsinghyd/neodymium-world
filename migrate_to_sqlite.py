import json
import database
import os

DATA_FILE = "news_data.json"

def migrate():
    database.init_db()
    
    if not os.path.exists(DATA_FILE):
        print("No news_data.json found to migrate.")
        return
        
    with open(DATA_FILE, 'r', encoding='utf-8') as f:
        try:
            data = json.load(f)
            articles = data.get("articles", []) if isinstance(data, dict) else data
        except Exception as e:
            print(f"Error reading JSON: {e}")
            return
            
    print(f"Found {len(articles)} articles in JSON. Migrating to SQLite...")
    
    success_count = 0
    duplicate_count = 0
    
    # Reverse to insert oldest first, so they get sequential IDs
    for item in reversed(articles):
        # original_link is required for deduplication. Use link as fallback.
        if 'original_link' not in item and 'link' in item:
            item['original_link'] = item['link']
            
        if 'original_link' not in item:
            item['original_link'] = f"unknown-{item.get('slug', 'slug')}"
            
        inserted = database.insert_article(item)
        if inserted:
            success_count += 1
        else:
            duplicate_count += 1
            
    print(f"Migration complete: {success_count} inserted, {duplicate_count} skipped (duplicates).")
    
if __name__ == '__main__':
    migrate()
