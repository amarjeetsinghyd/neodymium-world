import os
import requests
import frontmatter

def post_to_discord():
    print("Starting Discord Automation...")
    
    webhook_url = os.environ.get('DISCORD_WEBHOOK_URL')
    
    if not webhook_url:
        print("Missing DISCORD_WEBHOOK_URL. Skipping Discord posting.")
        return

    articles_dir = 'content/articles'
    if not os.path.exists(articles_dir):
        print("No articles directory found.")
        return

    for filename in os.listdir(articles_dir):
        if not filename.endswith('.md'):
            continue
            
        filepath = os.path.join(articles_dir, filename)
        with open(filepath, 'r', encoding='utf-8') as f:
            post = frontmatter.load(f)

        if post.metadata.get('posted_to_discord') == True:
            continue
            
        title = post.metadata.get('title', 'Unknown Title')
        slug = post.metadata.get('slug', os.path.splitext(filename)[0])
        article_url = f"articles/{slug}.html"
        image_url = post.metadata.get('image_url', '')
        
        # Build summary
        summary_text = "A new intelligence report has been published."
        if post.metadata.get("executive_summary"):
            summary_text = post.metadata["executive_summary"]
        elif post.content:
            from bs4 import BeautifulSoup
            import markdown
            html_content = markdown.markdown(post.content)
            text = BeautifulSoup(html_content, "html.parser").get_text()
            summary_text = text[:297] + "..." if len(text) > 300 else text
            
        neo_link = f"https://neodymium.world/{article_url}"
        print(f"Posting to Discord: {title}")
        
        embed = {
            "title": title,
            "description": summary_text,
            "url": neo_link,
            "color": 16738304,
            "author": {
                "name": "Neodymium Intelligence",
                "url": "https://neodymium.world"
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
            response.raise_for_status()
            
            # Mark as posted
            post.metadata['posted_to_discord'] = True
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(frontmatter.dumps(post))
            print(f"Successfully posted and marked {filename} as posted.")
            
        except Exception as e:
            print(f"Failed to post {filename} to Discord: {e}")

if __name__ == "__main__":
    post_to_discord()
