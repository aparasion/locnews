import feedparser, os, json, datetime, requests, trafilatura
from google import genai  # pip install google-generativeai

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# === CONFIGURE YOUR SPECIFIC AREA HERE ===
FEEDS = [
    "https://news.google.com/rss/search?q=your+keywords+OR+topic+when:1d",  # Google News RSS
    "https://rss.nytimes.com/services/xml/rss/nyt/YourSection.xml",
    # add 10–20 relevant RSS feeds
]
SEEN_FILE = "seen.json"

# Load seen URLs
seen = json.load(open(SEEN_FILE)) if os.path.exists(SEEN_FILE) else []

posts = []
for feed_url in FEEDS:
    feed = feedparser.parse(feed_url)
    for entry in feed.entries[:10]:  # limit per feed
        url = entry.link
        if url in seen: continue
        
        # Extract full clean text
        downloaded = trafilatura.fetch_url(url)
        text = trafilatura.extract(downloaded, include_comments=False) or entry.description
        
        # AI gist
        prompt = f"Create a concise gist (3–5 bullets or 100–200 words) of this article. Focus on key facts, implications. End with source: {url}\n\n{text[:15000]}"
        response = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
        gist = response.text
        time.sleep(15)  # 15s gap = max ~4 requests/min, safely under the limit
        
        posts.append({"title": entry.title, "url": url, "gist": gist, "date": entry.published})
        seen.append(url)

# Generate Jekyll post (daily digest style)
today = datetime.date.today().isoformat()
md_content = f"""---
title: "{your_area} News Gists - {today}"
date: {today}
layout: post
---

## Today's AI-curated gists

"""
for p in posts:
    md_content += f"### [{p['title']}]({p['url']})\n\n{p['gist']}\n\n---\n\n"

with open(f"_posts/{today}-news-gist.md", "w") as f:
    f.write(md_content)

# Save seen
json.dump(seen[-500:], open(SEEN_FILE, "w"))  # keep last 500
