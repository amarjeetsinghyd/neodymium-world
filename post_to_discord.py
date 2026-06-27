import os
import requests
import frontmatter
import logging
import traceback

logging.basicConfig(
    filename='run_log.txt',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

ARTICLES_DIR = 'content/articles'


def post_to_discord():
    print("Starting Discord Automation...")

    webhook_url = os.environ.get('DISCORD_WEBHOOK_URL')
    if not webhook_url:
        print("Missing DISCORD_WEBHOOK_URL. Skipping Discord posting.")
        return

    if not os.path.exists(ARTICLES_DIR):
        print("No articles directory found.")
        return

    for filename in sorted(os.listdir(ARTICLES_DIR)):
        if not filename.endswith('.md'):
            continue

        filepath = os.path.join(ARTICLES_DIR, filename)
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                post = frontmatter.load(f)
        except Exception as e:
            print(f"Skipping {filename}: could not read — {e}")
            continue

        # Skip drafts — do not post unpublished articles to Discord
        if post.metadata.get('draft') is True or str(post.metadata.get('draft', '')).lower() == 'true':
            continue

        if post.metadata.get('posted_to_discord') is True:
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
            summary_text = (text[:297] + "...") if len(text) > 300 else text

        neo_link = f"https://neodymium.world/{article_url}"
        print(f"Posting to Discord: {title}")

        embed = {
            "title": title[:256],  # Discord embed title limit is 256 chars
            "description": summary_text[:4096],  # Discord embed description limit
            "url": neo_link,
            "color": 16738304,
            "author": {
                "name": "Neodymium Intelligence",
                "url": "https://neodymium.world"
            },
            "footer": {
                "text": "Neodymium World | Live Intelligence Feed"
            }
        }

        # BUG FIX #9: Only include the image field if image_url is a valid
        # non-empty URL. Passing an empty string to Discord's "image.url"
        # causes the API to return a 400 Bad Request, silently failing the post.
        if image_url and image_url.startswith('http'):
            embed["image"] = {"url": image_url}

        payload = {
            "content": "\U0001f6a8 **New Intelligence Report**",
            "embeds": [embed]
        }

        try:
            response = requests.post(webhook_url, json=payload, timeout=15)
            response.raise_for_status()

            # Mark as posted and write back
            post.metadata['posted_to_discord'] = True
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(frontmatter.dumps(post))
            print(f"Successfully posted and marked: {filename}")
            logging.info(f"Discord posted: {filename}")

        except requests.exceptions.HTTPError as e:
            print(f"HTTP error posting {filename}: {e} — {response.text}")
            logging.error(f"Discord HTTP error for {filename}: {e} — {response.text}")
        except Exception as e:
            print(f"Failed to post {filename} to Discord: {e}")
            logging.error(f"Discord error for {filename}: {e}\n{traceback.format_exc()}")


if __name__ == "__main__":
    post_to_discord()
