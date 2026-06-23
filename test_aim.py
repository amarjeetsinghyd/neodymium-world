import feedparser
import requests
import trafilatura

url = "https://analyticsindiamag.com/feed/"
print(f"Fetching: {url}")
feed = feedparser.parse(url)

print(f"Status from feedparser: {feed.get('status', 'No status (might be blocked/cached)')}")
print(f"Number of entries: {len(feed.entries)}")

if len(feed.entries) > 0:
    entry = feed.entries[0]
    print(f"\nFirst entry title: {entry.title}")
    print(f"First entry link: {entry.link}")
    
    print("\nAttempting to download full article with Trafilatura...")
    downloaded = trafilatura.fetch_url(entry.link)
    if downloaded:
        text = trafilatura.extract(downloaded)
        if text:
            print(f"Successfully extracted {len(text)} characters of text.")
            print("Preview:")
            print(text[:200] + "...")
        else:
            print("Failed to extract text. (Site might have strict HTML/JS blocking)")
    else:
        print("Failed to download URL. (Trafilatura was blocked)")
else:
    print("No entries found. The RSS feed might be dead or blocking python requests.")
