import os
import sys
import requests
import frontmatter
import logging
import traceback

# --- Logging ---
# Route to stdout so output appears in GitHub Actions run logs.
# run_log.txt is gitignored and not created here.
logging.basicConfig(
    stream=sys.stdout,
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

        # Build embed description — priority order:
        # 1. social_hook: Gemini-written 280-char teaser, always present on new articles
        # 2. executive_summary: legacy field from older article schema
        # 3. First 300 chars of article body as a plain-text fallback
        social_hook = post.metadata.get('social_hook', '').strip()
        executive_summary = post.metadata.get('executive_summary', '').strip()

        if social_hook:
            summary_text = social_hook
        elif executive_summary:
            summary_text = executive_summary
        else:
            # Plain-text fallback from article body
            from bs4 import BeautifulSoup
            import markdown as md_lib
            html_content = md_lib.markdown(post.content)
            text = BeautifulSoup(html_content, "html.parser").get_text()
            summary_text = (text[:297] + "...") if len(text) > 300 else text

        neo_link = f"https://neodymium.world/{article_url}"
        print(f"Posting to Discord: {title}")

        embed = {
            "title": title[:256],
            "description": summary_text[:4096],
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

        # Only include image if URL is valid — empty string causes Discord 400
        if image_url and image_url.startswith('http'):
            embed["image"] = {"url": image_url}

        payload = {
            "content": "\U0001f6a8 **New Intelligence Report**",
            "embeds": [embed]
        }

        try:
            response = requests.post(webhook_url, json=payload, timeout=15)
            response.raise_for_status()

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
