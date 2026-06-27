# 🌐 Neodymium World

> A static HTML news & blog platform with a Python-powered build pipeline, AI-assisted content generation, and automated publishing.

[![Live Site](https://img.shields.io/badge/Live-neodymium.world-blue?style=flat-square)](https://neodymium.world)
[![License](https://img.shields.io/badge/license-MIT-green?style=flat-square)](#)

---

## 📌 What is This?

Neodymium World is a **self-hosted, GitHub Pages–deployed content website** built entirely with raw HTML/CSS and a custom Python build system. There is no frontend framework — pages are generated from templates and compiled via Python scripts. Content is sourced via RSS feeds, processed using Trafilatura + Google Gemini AI, stored in a SQLite database, and then rendered to static HTML files.

---

## 🗂️ Project Structure

```
neodymium-world/
├── index.html              # Main homepage
├── about.html              # About page
├── articles/               # Published article HTML files
├── assets/                 # CSS, JS, images
├── content/                # Markdown/raw content source files
├── admin/                  # Admin-side tooling or panel
├── templates/              # (Recommended) HTML/XML templates
│   ├── article_template.html
│   ├── archive_template.html
│   ├── rss_template.xml
│   └── sitemap_template.xml
├── scripts/                # (Recommended) Build & utility scripts
│   ├── update_news.py      # Core news fetch + AI processing pipeline
│   ├── recompile_html.py   # Regenerates HTML from templates
│   ├── post_to_discord.py  # Discord webhook publisher
│   ├── migrate_to_sqlite.py
│   ├── migrate_db_to_md.py
│   ├── fix_bullets.py
│   ├── fix_bullets_proper.py
│   └── fix_pre_code.py
├── sitemap.xml             # Auto-generated sitemap
├── rss.xml                 # Auto-generated RSS feed
├── robots.txt              # Crawler directives
├── ads.txt                 # AdSense/ad network declaration
├── llms.txt                # AI crawler guidance
├── CNAME                   # Custom domain config for GitHub Pages
└── requirements.txt        # Python dependencies
```

---

## ⚙️ Setup & Installation

### Prerequisites
- Python 3.10+
- Git

### 1. Clone the Repository
```bash
git clone https://github.com/amarjeetsinghyd/neodymium-world.git
cd neodymium-world
```

### 2. Create a Virtual Environment
```bash
python -m venv venv
source venv/bin/activate        # On Windows: venv\Scripts\activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables
Create a `.env` file at the root (never commit this):
```env
GEMINI_API_KEY=your_google_gemini_api_key
DISCORD_WEBHOOK_URL=your_discord_webhook_url
```

---

## 🚀 Build Pipeline

The build pipeline works in the following order:

1. **Fetch & Process Content**
   ```bash
   python update_news.py
   ```
   Fetches RSS feeds, scrapes article content via Trafilatura, processes with Google Gemini AI, and saves results to the local database.

2. **Recompile HTML Pages**
   ```bash
   python recompile_html.py
   ```
   Reads from the database and regenerates all article HTML pages using templates.

3. **Post to Discord** *(optional)*
   ```bash
   python post_to_discord.py
   ```
   Publishes newly generated articles to your configured Discord channel via webhook.

4. **Deploy**
   Commit the generated HTML files and push to `main`. GitHub Pages will serve the updated site automatically.

---

## 🔐 Security Notes

- **Never commit** `.env`, `*.db`, or `news_data.json` to the repository.
- API keys for Google Gemini and Discord webhook URLs must be stored in `.env` and loaded via `python-dotenv`.
- The `.gitignore` in this repo excludes all sensitive file types.

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Raw HTML5 / CSS3 |
| Build System | Python 3.10+ |
| AI Processing | Google Gemini (`google-generativeai`) |
| Content Scraping | Trafilatura |
| Feed Parsing | Feedparser |
| Templating | Jinja2 |
| Content Format | Markdown + Python-Frontmatter |
| Database | SQLite |
| Hosting | GitHub Pages |
| Domain | Custom via CNAME |

---

## 📡 SEO & Discoverability

The site includes a full SEO stack out of the box:
- `sitemap.xml` — auto-generated for all articles
- `rss.xml` — RSS feed for subscribers and feed aggregators
- `robots.txt` — search engine crawler rules
- `ads.txt` — ad network authorization
- `llms.txt` — AI crawler guidance file
- Google Search Console ownership verification

---

## 👤 Author

**Amarjeet Singh**  
Senior Executive — R&D, Invesmate Insights Pvt. Ltd.  
Piro, Bihar, India  
[GitHub](https://github.com/amarjeetsinghyd)

---

*Built with ❤️ and Python.*
