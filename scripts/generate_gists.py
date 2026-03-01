import feedparser
import os
import json
import datetime
import requests
import trafilatura
import time
from urllib.parse import urlparse
from openai import OpenAI

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

FEEDS = [
    "https://news.google.com/rss/search?q=translation+localization+OR+interpreting+when:7d&hl=en-US&gl=US&ceid=US:en",
    "https://techcrunch.com/tag/translation/feed/",
    "https://techcrunch.com/tag/ai-translation/feed/",
    "https://techcrunch.com/tag/machine-translation/feed/",
    "https://techcrunch.com/tag/localization/feed/",
    "https://techcrunch.com/tag/translate/feed/",
    "https://techcrunch.com/tag/translations/feed/",
]

SEEN_FILE = "seen.json"
YOUR_AREA = "Translation"
MAX_ARTICLES = 18


def yaml_escape(text: str) -> str:
    """Escape content for safe inclusion in quoted YAML scalar values."""
    return text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ").strip()


def get_publisher_domain(url: str) -> str:
    """Extract clean domain name from URL (e.g. 'distractify.com')"""
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        # Remove common prefixes
        if domain.startswith(('www.', 'amp.', 'm.')):
            domain = domain.split('.', 1)[1] if '.' in domain[4:] else domain[4:]
        # Remove port if present (rare)
        domain = domain.split(':', 1)[0]
        return domain if domain else "Unknown Publisher"
    except Exception:
        return "Unknown Publisher"


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

        prompt = f"""Create a concise gist (100–200 words) of this article.
Focus on key facts and implications.

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
            gist = f"Summary generation failed due to API error.\n\nRead the full article below."

        # ────────────────────────────────────────────────
        # Date handling
        # ────────────────────────────────────────────────
        if 'published_parsed' in entry and entry.published_parsed:
            pub_dt = datetime.datetime(*entry.published_parsed[:6])
        else:
            pub_dt = datetime.datetime.now()

        post_date_str = pub_dt.strftime("%Y-%m-%d")
        time_str = pub_dt.strftime("%H:%M:%S")

        # Slug
        slug_raw = entry.title.lower().replace(" ", "-")
        slug = "".join(c for c in slug_raw if c.isalnum() or c == "-")[:60].rstrip("-")
        filename = f"_posts/{post_date_str}-{slug}.md"

        # Source information
        source_url = entry.link if entry.link else url
        publisher = get_publisher_domain(source_url)

        # ────────────────────────────────────────────────
        # Markdown content — one post per article
        # ────────────────────────────────────────────────
        safe_title = yaml_escape(entry.title)
        safe_excerpt = yaml_escape(gist[:160])

        md_content = f"""---
title: "{safe_title}"
date: {post_date_str}T{time_str}Z
layout: post
categories: [{YOUR_AREA.lower()}]
tags: [translation, localization, news, gist]
excerpt: "{safe_excerpt}..."
publisher: {publisher}
source_url: "{source_url}"
---

{gist}

[→ Read full article via {publisher}]({source_url})
"""

        os.makedirs("_posts", exist_ok=True)

        with open(filename, "w", encoding="utf-8") as f:
            f.write(md_content)

        posts.append({
            "title": entry.title,
            "publisher": publisher,
            "url": source_url,
            "gist": gist,
            "date": post_date_str
        })

        seen.append(url)
        count += 1

        time.sleep(2)

# ────────────────────────────────────────────────
print(f"Generated {len(posts)} individual gist posts")
with open(SEEN_FILE, "w", encoding="utf-8") as seen_file:
    json.dump(seen[-500:], seen_file, indent=2)
