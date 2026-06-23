import os
import requests
import json
import database

def post_to_discord():
    print("Starting Discord Automation...")
    
    webhook_url = os.environ.get('DISCORD_WEBHOOK_URL')
    
    if not webhook_url:
        print("Missing DISCORD_WEBHOOK_URL. Skipping Discord posting.")
        return

    database.init_db()
    conn = database.sqlite3.connect(database.DB_FILE)
    cursor = conn.cursor()
    
    # Get articles not yet posted to Discord
    cursor.execute('''
        SELECT id, title, article_url, image_url, full_report, discord_post
        FROM articles 
        WHERE posted_to_discord = 0 OR posted_to_discord IS NULL
        ORDER BY published_at ASC
    ''')
    
    unposted_articles = cursor.fetchall()
    
    if not unposted_articles:
        print("No new articles to post to Discord.")
        return
        
    for article in unposted_articles:
        art_id, title, article_url, image_url, full_report_json, discord_post = article
        
        try:
            if discord_post and discord_post.strip():
                summary_text = discord_post
            else:
                report_data = json.loads(full_report_json) if full_report_json else {}
                # Fallback to the first available section
                first_section = list(report_data.values())[0] if report_data else 'A new intelligence report has been published.'
                from bs4 import BeautifulSoup
                summary_text = BeautifulSoup(first_section, "html.parser").get_text()
            
            # Limit summary to 300 chars for the embed
            if len(summary_text) > 300:
                summary_text = summary_text[:297] + "..."
                
        except Exception:
            summary_text = "A new intelligence report has been published."
            
        # Build the Neodymium link
        neo_link = f"https://neodymium.world/{article_url}"
        
        print(f"Posting to Discord: {title}")
        
        # Build the Discord Rich Embed
        embed = {
            "title": title,
            "description": summary_text,
            "url": neo_link,
            "color": 16738304, # Neodymium Orange/Amber color code
            "author": {
                "name": "Neodymium Intelligence",
                "url": "https://neodymium.world",
                "icon_url": "https://neodymium.world/assets/logo.png" # Assuming a logo exists, otherwise Discord defaults gracefully
            },
            "image": {
                "url": image_url if image_url else ""
            },
            "footer": {
                "text": "Neodymium World | Live Intelligence Feed"
            }
        }
        
        payload = {
            "content": "🚨 **New Intelligence Report**",
            "embeds": [embed]
        }
        
        try:
            response = requests.post(webhook_url, json=payload)
            response.raise_for_status() # Raise exception for bad status codes
            
            # Mark as posted in DB
            cursor.execute('UPDATE articles SET posted_to_discord = 1 WHERE id = ?', (art_id,))
            conn.commit()
            print(f"Successfully posted and marked article ID {art_id} as posted.")
            
        except Exception as e:
            print(f"Failed to post article ID {art_id} to Discord: {e}")
            # Do not mark as posted if it failed

    conn.close()
    print("Discord Automation Complete.")

if __name__ == "__main__":
    post_to_discord()
