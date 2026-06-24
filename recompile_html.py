import os
import json
import markdown
import frontmatter
from datetime import datetime
from jinja2 import Environment, FileSystemLoader, select_autoescape
from urllib.parse import urlparse

def main():
    env = Environment(
        loader=FileSystemLoader('.'),
        autoescape=select_autoescape(['html', 'xml'])
    )
    try:
        template = env.get_template('article_template.html')
    except Exception as e:
        print(f"Could not load templates: {e}")
        return

    articles_dir = 'content/articles'
    if not os.path.exists(articles_dir):
        print(f"Directory {articles_dir} does not exist.")
        return

    articles = []
    
    # Read all markdown files
    for filename in os.listdir(articles_dir):
        if filename.endswith('.md'):
            filepath = os.path.join(articles_dir, filename)
            with open(filepath, 'r', encoding='utf-8') as f:
                post = frontmatter.load(f)

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
                item["published_at"] = datetime.utcnow().isoformat()
            
            articles.append(item)

    # Sort articles by published_at descending
    articles.sort(key=lambda x: x.get('published_at', ''), reverse=True)

    # Build individual article HTMLs
    for item in articles:
        print(f"Recompiling HTML for: {item.get('title')}")
        pub_name = "Neodymium Intel"
        try:
            if item.get("original_link") and "http" in item["original_link"]:
                pub_name = urlparse(item["original_link"]).netloc.replace('www.', '')
        except:
            pass
            
        word_count = len(item["full_report"].get("Article Body", "").split())
        reading_time = item.get("reading_time") or max(1, round(word_count / 200))
        
        try:
            html_content = template.render(
                title=item.get("title", ""),
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
            with open(item["article_url"], 'w', encoding='utf-8') as f:
                f.write(html_content)
        except Exception as e:
            print(f"Failed to rebuild HTML for '{item.get('title')}': {e}")
            
    # Generate archive.html
    try:
        archive_template = env.get_template('archive_template.html')
        archive_content = archive_template.render(articles=articles)
        with open('archive.html', 'w', encoding='utf-8') as f:
            f.write(archive_content)
        print("Generated archive.html")
    except Exception as e:
        print(f"Failed to generate archive.html: {e}")

    # Generate RSS Feed
    try:
        rss_template = env.get_template('rss_template.xml')
        rss_content = rss_template.render(articles=articles[:50])
        with open('rss.xml', 'w', encoding='utf-8') as f:
            f.write(rss_content)
        print("Successfully generated rss.xml")
    except Exception as e:
        print(f"Failed to generate RSS feed: {e}")

    # Generate Sitemap
    try:
        sitemap_template = env.get_template('sitemap_template.xml')
        from datetime import datetime, timezone
        sitemap_content = sitemap_template.render(articles=articles, current_date=datetime.now(timezone.utc).strftime('%Y-%m-%d'))
        with open('sitemap.xml', 'w', encoding='utf-8') as f:
            f.write(sitemap_content)
        print("Successfully generated sitemap.xml")
    except Exception as e:
        print(f"Failed to generate Sitemap: {e}")

    # Generate news_data.json for frontend
    try:
        with open('news_data.json', 'w', encoding='utf-8') as f:
            json.dump(articles, f, indent=4)
        print("Successfully generated news_data.json")
    except Exception as e:
        print(f"Failed to generate news_data.json: {e}")
                
    print("Recompilation complete.")

if __name__ == "__main__":
    main()
