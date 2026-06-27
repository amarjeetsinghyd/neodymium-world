import os
import json
import markdown
import frontmatter
import logging
import traceback
from datetime import datetime, timezone
from jinja2 import Environment, FileSystemLoader, select_autoescape
from urllib.parse import urlparse

# --- Logging ---
logging.basicConfig(
    filename='run_log.txt',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

ARTICLES_DIR = 'content/articles'


def parse_date(date_val):
    """Robustly parse any date value into a timezone-aware datetime object."""
    import datetime as dt
    from email.utils import parsedate_to_datetime
    if not date_val:
        return dt.datetime.min.replace(tzinfo=dt.timezone.utc)
    if isinstance(date_val, dt.datetime):
        return date_val if date_val.tzinfo else date_val.replace(tzinfo=dt.timezone.utc)
    if isinstance(date_val, dt.date):
        return dt.datetime.combine(date_val, dt.time.min).replace(tzinfo=dt.timezone.utc)
    date_str = str(date_val)
    try:
        return parsedate_to_datetime(date_str)
    except Exception:
        pass
    try:
        return dt.datetime.fromisoformat(date_str.replace('Z', '+00:00'))
    except Exception:
        return dt.datetime.min.replace(tzinfo=dt.timezone.utc)


def load_articles():
    """Read all non-draft markdown articles and return a sorted list of dicts."""
    if not os.path.exists(ARTICLES_DIR):
        print(f"Directory {ARTICLES_DIR} does not exist. Nothing to compile.")
        return []

    articles = []

    for filename in sorted(os.listdir(ARTICLES_DIR)):
        if not filename.endswith('.md'):
            continue
        filepath = os.path.join(ARTICLES_DIR, filename)

        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                post = frontmatter.load(f)
        except Exception as e:
            print(f"Skipping {filename}: failed to parse frontmatter — {e}")
            logging.warning(f"Skipping {filename}: {e}")
            continue

        if post.metadata.get('draft') is True or str(post.metadata.get('draft', '')).lower() == 'true':
            continue

        report = {}
        if "key_takeaways" in post.metadata:
            report["Key Takeaways"] = post.metadata["key_takeaways"]
        if "faq" in post.metadata:
            report["FAQ"] = post.metadata["faq"]
        report["Article Body"] = markdown.markdown(post.content)

        item = post.metadata.copy()
        item["full_report"] = report

        if "slug" not in item:
            item["slug"] = os.path.splitext(filename)[0]
        if "article_url" not in item:
            item["article_url"] = f"articles/{item['slug']}.html"

        if "published_at" not in item:
            item["published_at"] = datetime.now(timezone.utc).isoformat()

        # Normalize relative image paths to absolute URLs
        raw_img = item.get('image_url', '')
        if raw_img and not raw_img.startswith('http'):
            # Strip leading ../ or / and build absolute URL
            clean = raw_img.lstrip('./').lstrip('/')
            item['image_url'] = f"https://neodymium.world/{clean}"

        dt_obj = parse_date(item.get('published_at'))
        item['published_at'] = dt_obj.isoformat()

        articles.append(item)

    articles.sort(key=lambda x: x.get('published_at', ''), reverse=True)
    return articles


def build_articles(env, articles):
    """Render individual HTML pages for each article."""
    try:
        template = env.get_template('article_template.html')
    except Exception as e:
        print(f"Could not load article_template.html: {e}")
        logging.error(f"Could not load article_template.html: {e}")
        return

    os.makedirs('articles', exist_ok=True)

    for item in articles:
        print(f"Recompiling HTML for: {item.get('title')}")
        pub_name = "Neodymium Intel"
        try:
            if item.get("original_link") and "http" in item["original_link"]:
                pub_name = urlparse(item["original_link"]).netloc.replace('www.', '')
        except Exception:
            pass

        word_count = len(item["full_report"].get("Article Body", "").split())
        reading_time = item.get("reading_time") or max(1, round(word_count / 200))

        try:
            html_content = template.render(
                title=item.get("title", ""),
                seo_title=item.get("seo_title", ""),
                meta_description=item.get("meta_description", ""),
                social_hook=item.get("social_hook", ""),
                category=item.get("category", "Intelligence"),
                seo_tags=item.get("seo_tags", []),
                full_report=item["full_report"],
                image_url=item.get("image_url", ""),
                published_at=item.get("published_at", ""),
                original_link=item.get("original_link", "#"),
                publisher_name=pub_name,
                slug=item.get("slug", ""),
                reading_time=reading_time
            )
            out_path = item["article_url"]
            with open(out_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
        except Exception as e:
            print(f"Failed to rebuild HTML for '{item.get('title')}': {e}")
            logging.error(f"Failed to rebuild HTML for '{item.get('title')}': {e}")


def main():
    env = Environment(
        loader=FileSystemLoader('templates'),
        autoescape=select_autoescape(['html', 'xml'])
    )

    articles = load_articles()
    print(f"Loaded {len(articles)} published articles.")

    build_articles(env, articles)

    # Generate archive.html
    try:
        archive_template = env.get_template('archive_template.html')
        archive_content = archive_template.render(articles=articles)
        with open('archive.html', 'w', encoding='utf-8') as f:
            f.write(archive_content)
        print("Generated archive.html")
    except Exception as e:
        print(f"Failed to generate archive.html: {e}")
        logging.error(f"Failed to generate archive.html: {e}")

    # Generate RSS Feed (capped at 50 most recent)
    try:
        rss_template = env.get_template('rss_template.xml')
        rss_content = rss_template.render(articles=articles[:50])
        with open('rss.xml', 'w', encoding='utf-8') as f:
            f.write(rss_content)
        print("Successfully generated rss.xml")
    except Exception as e:
        print(f"Failed to generate RSS feed: {e}")
        logging.error(f"Failed to generate rss.xml: {e}")

    # Generate Sitemap with Google News extension
    try:
        sitemap_template = env.get_template('sitemap_template.xml')
        sitemap_content = sitemap_template.render(
            articles=articles,
            current_date=datetime.now(timezone.utc).strftime('%Y-%m-%d')
        )
        with open('sitemap.xml', 'w', encoding='utf-8') as f:
            f.write(sitemap_content)
        print("Successfully generated sitemap.xml")
    except Exception as e:
        print(f"Failed to generate Sitemap: {e}")
        logging.error(f"Failed to generate sitemap.xml: {e}")

    # Generate news_data.json — slim card metadata only (no HTML body)
    try:
        FRONTEND_FIELDS = [
            'title', 'slug', 'category', 'seo_tags', 'image_url',
            'published_at', 'reading_time', 'article_url',
            'key_takeaways', 'seo_title', 'meta_description', 'social_hook'
        ]
        slim_articles = [
            {k: v for k, v in a.items() if k in FRONTEND_FIELDS}
            for a in articles
        ]
        with open('news_data.json', 'w', encoding='utf-8') as f:
            json.dump(slim_articles, f, indent=2)
        print(f"Successfully generated news_data.json ({len(slim_articles)} articles)")
    except Exception as e:
        print(f"Failed to generate news_data.json: {e}")
        logging.error(f"Failed to generate news_data.json: {e}")

    print("Recompilation complete.")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        error_msg = f"Fatal error in recompile_html.py: {e}"
        print(error_msg)
        logging.error(error_msg + "\n" + traceback.format_exc())
        raise
