import feedparser, os, json, datetime, requests, trafilatura, time
from google import genai
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

FEEDS = [
    "https://www.languagemagazine.com/feed/",
    "https://multilingual.com/feed/",
]

SEEN_FILE = "seen.json"
YOUR_AREA = "Translation"
MAX_ARTICLES = 1  # ← defined here before the loop

seen = json.load(open(SEEN_FILE)) if os.path.exists(SEEN_FILE) else []
posts = []
count = 0  # ← counter initialized here before the loop

for feed_url in FEEDS:
    if count >= MAX_ARTICLES:  # ← check before each feed
        break
    feed = feedparser.parse(feed_url)
    for entry in feed.entries[:10]:
        if count >= MAX_ARTICLES:  # ← check before each article
            break
        url = entry.link
        if url in seen:
            continue

        downloaded = trafilatura.fetch_url(url)
        text = trafilatura.extract(downloaded, include_comments=False) or entry.description

        prompt = f"Create a concise gist (3–5 bullets or 100–200 words) of this article. Focus on key facts, implications. End with source: {url}\n\n{text[:15000]}"
        response = client.models.generate_content(model="gemini-2.0-flash", contents=prompt)
        gist = response.text
        time.sleep(15)

        posts.append({"title": entry.title, "url": url, "gist": gist, "date": entry.published})
        seen.append(url)
        count += 1  # ← increment after each successful API call

# Generate Jekyll post
today = datetime.date.today().isoformat()
md_content = f"""---
title: "{YOUR_AREA} News Gists - {today}"
date: {today}
layout: post
---
## Today's AI-curated gists
"""
for p in posts:
    md_content += f"### [{p['title']}]({p['url']})\n\n{p['gist']}\n\n---\n\n"

with open(f"_posts/{today}-news-gist.md", "w") as f:
    f.write(md_content)

json.dump(seen[-500:], open(SEEN_FILE, "w"))
