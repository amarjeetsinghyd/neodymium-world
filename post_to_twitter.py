import os
import sqlite3
import json
import time
import requests
import tweepy

DB_FILE = 'neodymium.db'

def get_twitter_clients():
    consumer_key = os.environ.get("TWITTER_CONSUMER_KEY")
    consumer_secret = os.environ.get("TWITTER_CONSUMER_SECRET")
    access_token = os.environ.get("TWITTER_ACCESS_TOKEN")
    access_token_secret = os.environ.get("TWITTER_ACCESS_TOKEN_SECRET")

    if not all([consumer_key, consumer_secret, access_token, access_token_secret]):
        print("Twitter credentials missing. Skipping Twitter post.")
        return None, None

    # v1.1 API for media upload
    auth = tweepy.OAuth1UserHandler(consumer_key, consumer_secret, access_token, access_token_secret)
    api = tweepy.API(auth)

    # v2 API for tweeting
    client = tweepy.Client(
        consumer_key=consumer_key,
        consumer_secret=consumer_secret,
        access_token=access_token,
        access_token_secret=access_token_secret
    )
    return client, api

def post_threads():
    client, api = get_twitter_clients()
    if not client:
        return

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    # Get all unposted articles
    cursor.execute("SELECT id, title, article_url, image_url, twitter_thread FROM articles WHERE posted_to_twitter = 0")
    articles = cursor.fetchall()

    for row in articles:
        article_id, title, article_url, image_url, thread_json = row
        try:
            thread = json.loads(thread_json)
            if not thread or len(thread) == 0:
                continue
        except (json.JSONDecodeError, TypeError):
            continue
        
        print(f"Posting thread for: {title}")
        
        # Download and upload media
        media_id = None
        if image_url:
            try:
                img_response = requests.get(image_url, timeout=10)
                if img_response.status_code == 200:
                    with open("temp_img.jpg", "wb") as f:
                        f.write(img_response.content)
                    media = api.media_upload("temp_img.jpg")
                    media_id = media.media_id
                    os.remove("temp_img.jpg")
            except Exception as e:
                print(f"Error downloading/uploading image: {e}")

        previous_tweet_id = None
        for i, tweet_text in enumerate(thread):
            # Process CTA link
            tweet_text = tweet_text.replace("[LINK]", article_url)
            
            try:
                if i == 0 and media_id:
                    response = client.create_tweet(text=tweet_text, media_ids=[media_id])
                elif previous_tweet_id:
                    response = client.create_tweet(text=tweet_text, in_reply_to_tweet_id=previous_tweet_id)
                else:
                    response = client.create_tweet(text=tweet_text)
                
                previous_tweet_id = response.data['id']
                print(f"  - Tweet {i+1} posted: {previous_tweet_id}")
                time.sleep(2)  # Delay between tweets in thread to respect rate limits
            except Exception as e:
                print(f"Error posting tweet {i+1}: {e}")
                break # Stop the thread if one fails

        # Mark as posted even if failed midway to avoid spamming partial threads
        cursor.execute("UPDATE articles SET posted_to_twitter = 1 WHERE id = ?", (article_id,))
        conn.commit()
        time.sleep(5)  # Delay between distinct article threads
        
    conn.close()

if __name__ == "__main__":
    post_threads()
