import feedparser, os, json, datetime, requests, trafilatura, time
from openai import OpenAI

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

FEEDS = [
    "https://news.google.com/rss/search?q=translation+localization+OR+topic+when:1d",  # Google News RSS
    # add more feeds here as needed
]

SEEN_FILE = "seen.json"
YOUR_AREA = "Translation"
MAX_ARTICLES = 18

seen = json.load(open(SEEN_FILE)) if os.path.exists(SEEN_FILE) else []
posts = []
count = 0

for feed_url in FEEDS:
    if count >= MAX_ARTICLES:
        break
    feed = feedparser.parse(feed_url)
    for entry in feed.entries[:10]:
        if count >= MAX_ARTICLES:
            break
        url = entry.link
        if url in seen:
            continue

        downloaded = trafilatura.fetch_url(url)
        text = trafilatura.extract(downloaded, include_comments=False) or entry.description

        prompt = f"""Create a concise gist (3–5 bullets or 100–200 words) of this article. 
Focus on key facts, implications. End with source: {url}

Article text:
{text[:15000]}"""

        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a helpful news summarizer."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=300,
                temperature=0.3
            )
            gist = response.choices[0].message.content.strip()
        except Exception as e:
            print(f"OpenAI API error for {url}: {e}")
            gist = f"Summary failed (API error). Read full article: {url}"

        # Prepare data for this individual post
        post_date = entry.get("published_parsed") or datetime.datetime.now()
        post_date_str = datetime.datetime(*post_date[:6]).strftime("%Y-%m-%d")  # fallback to today if missing
        slug = entry.title.lower().replace(" ", "-").replace("[^a-z0-9-]", "")[:50]  # simple slug
        filename = f"_posts/{post_date_str}-{slug}.md"

        # Front matter + content for this single post
        md_content = f"""---
title: "{entry.title.replace('"', '\\"')}"
date: {post_date_str}T{datetime.datetime.now().strftime("%H:%M:%S")}Z  # approximate time
layout: post
categories: [{YOUR_AREA.lower()}]
tags: [translation, news, gist]
source: {url}
---

{prompt.split("Article text:")[0].strip()}  <!-- optional: show the instruction as intro -->

{gist}
"""

        # Write individual file
        os.makedirs("_posts", exist_ok=True)
        with open(filename, "w", encoding="utf-8") as f:
            f.write(md_content)

        posts.append({"title": entry.title, "url": url, "gist": gist, "date": post_date_str})  # still collect for logging if needed
        seen.append(url)
        count += 1

        time.sleep(2)  # polite delay

# Optional: log how many new posts were created
print(f"Generated {len(posts)} individual gist posts")

# Update seen file (keep last 500)
json.dump(seen[-500:], open(SEEN_FILE, "w"), indent=2)
