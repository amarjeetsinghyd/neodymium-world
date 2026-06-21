import os
import sys
import praw
import database

def post_to_reddit():
    print("Starting Reddit Automation...")
    
    # Initialize Reddit client
    client_id = os.environ.get('REDDIT_CLIENT_ID')
    client_secret = os.environ.get('REDDIT_CLIENT_SECRET')
    username = os.environ.get('REDDIT_USERNAME')
    password = os.environ.get('REDDIT_PASSWORD')
    target_subreddit = os.environ.get('REDDIT_SUBREDDIT', 'test')  # Defaults to r/test for safety
    
    if not all([client_id, client_secret, username, password]):
        print("Missing Reddit credentials. Skipping Reddit posting.")
        return

    try:
        reddit = praw.Reddit(
            client_id=client_id,
            client_secret=client_secret,
            username=username,
            password=password,
            user_agent="windows:neodymium_automation:v1.0 (by /u/NeodymiumWorld)"
        )
        print(f"Authenticated as /u/{reddit.user.me()}")
    except Exception as e:
        print(f"Failed to authenticate with Reddit: {e}")
        return

    database.init_db()
    conn = database.sqlite3.connect(database.DB_FILE)
    cursor = conn.cursor()
    
    # Get articles not yet posted to Reddit
    cursor.execute('''
        SELECT id, title, article_url, original_link 
        FROM articles 
        WHERE posted_to_reddit = 0 OR posted_to_reddit IS NULL
        ORDER BY published_at ASC
    ''')
    
    unposted_articles = cursor.fetchall()
    
    if not unposted_articles:
        print("No new articles to post to Reddit.")
        return
        
    subreddit = reddit.subreddit(target_subreddit)
    
    for article in unposted_articles:
        art_id, title, article_url, original_link = article
        
        # Build the Neodymium link
        neo_link = f"https://neodymium.world/{article_url}"
        
        print(f"Posting to r/{target_subreddit}: {title}")
        
        try:
            # Submit a Link Post
            subreddit.submit(title=title, url=neo_link)
            
            # Mark as posted in DB
            cursor.execute('UPDATE articles SET posted_to_reddit = 1 WHERE id = ?', (art_id,))
            conn.commit()
            print(f"Successfully posted and marked article ID {art_id} as posted.")
            
        except Exception as e:
            print(f"Failed to post article ID {art_id}: {e}")
            # Do not mark as posted if it failed

    conn.close()
    print("Reddit Automation Complete.")

if __name__ == "__main__":
    post_to_reddit()
