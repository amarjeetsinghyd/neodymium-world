import os
import markdown
import database
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

    database.init_db()
    articles = database.get_all_articles(limit=1000)

    for item in articles:
        if "article_url" in item:
            print(f"Recompiling HTML for: {item.get('title')}")
            report = item.get("full_report", {})
            for key in report:
                if isinstance(report[key], str) and not report[key].strip().startswith("<"):
                    report[key] = markdown.markdown(report[key])
            
            pub_name = "Neodymium Intel"
            try:
                if item.get("original_link") and "http" in item["original_link"]:
                    pub_name = urlparse(item["original_link"]).netloc.replace('www.', '')
            except:
                pass
                
            word_count = sum(len(str(v).split()) for v in report.values())
            reading_time = max(1, round(word_count / 200))
            
            try:
                html_content = template.render(
                    title=item.get("title", ""),
                    category=item.get("category", "Intelligence"),
                    seo_tags=item.get("seo_tags", []),
                    full_report=report,
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
                
    print("Recompilation complete.")

if __name__ == "__main__":
    main()
