import feedparser
import os
import json
import datetime
import requests
import trafilatura
import time
from openai import OpenAI

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

FEEDS = [
    "https://news.google.com/rss/search?q=translation+localization+OR+interpreting+when:7d&hl=en-US&gl=US&ceid=US:en",
    "https://multilingual.com/feed/",
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
Focus on key facts and implications. End with "Source: {url}".

Article text:
{text[:15000]}"""

        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a helpful, concise news summarizer."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=300,
                temperature=0.3
            )
            gist = response.choices[0].message.content.strip()
        except Exception as e:
            print(f"OpenAI API error for {url}: {e}")
            gist = f"Summary generation failed due to API error.\n\nRead the full article: {url}"

        # ────────────────────────────────────────────────
        # Date handling — prefer article date, fallback to now
        # ────────────────────────────────────────────────
        if 'published_parsed' in entry and entry.published_parsed:
            pub_dt = datetime.datetime(*entry.published_parsed[:6])
        else:
            pub_dt = datetime.datetime.now()

        post_date_str = pub_dt.strftime("%Y-%m-%d")
        time_str = pub_dt.strftime("%H:%M:%S")

        # Simple slug (you can improve later with slugify if desired)
        slug_raw = entry.title.lower().replace(" ", "-")
        slug = "".join(c for c in slug_raw if c.isalnum() or c == "-")[:60].rstrip("-")

        filename = f"_posts/{post_date_str}-{slug}.md"

        # Clean source URL (use entry.link — usually the original)
        source_url = entry.link if entry.link else url

        # ────────────────────────────────────────────────
        # Individual post Markdown content
        # ────────────────────────────────────────────────
        md_content = f"""---
title: "{entry.title.replace('"', '\\"')}"
date: {post_date_str}T{time_str}Z
layout: post
categories: [{YOUR_AREA.lower()}]
tags: [translation, localization, news, gist]
excerpt: "{gist[:160].replace('"', '\\"')}..."   # first ~160 chars for previews
source_url: {source_url}
---

{gist}

[→ Read the full article]({source_url})
"""

        # Ensure _posts directory exists
        os.makedirs("_posts", exist_ok=True)

        # Write the file
        with open(filename, "w", encoding="utf-8") as f:
            f.write(md_content)

        posts.append({
            "title": entry.title,
            "url": source_url,
            "gist": gist,
            "date": post_date_str
        })

        seen.append(url)
        count += 1

        time.sleep(2)  # polite delay between API calls

# ────────────────────────────────────────────────
# Summary & cleanup
# ────────────────────────────────────────────────
print(f"Generated {len(posts)} individual gist posts")

# Keep only last 500 seen URLs
json.dump(seen[-500:], open(SEEN_FILE, "w"), indent=2)
