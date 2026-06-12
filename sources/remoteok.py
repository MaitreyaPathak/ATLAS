"""
remoteok.py — Scraper for RemoteOK RSS feed.

feedparser gives us structured access to title, link, author (company),
and tags. We extract all of them properly.
"""

import feedparser
import html
import re

RSS_URL = "https://remoteok.com/remote-jobs.rss"


def _clean_text(text: str) -> str:
    """Strip HTML tags and unescape entities."""
    text = re.sub(r"<[^>]+>", "", text)
    return html.unescape(text).strip()


def fetch_jobs() -> list[dict]:
    print("Fetching RemoteOK jobs...")

    feed = feedparser.parse(RSS_URL)

    if feed.bozo and not feed.entries:
        print(f"  RemoteOK: feed parse error — {feed.bozo_exception}")
        return []

    jobs = []

    for entry in feed.entries:
        title = _clean_text(getattr(entry, "title", ""))
        link = getattr(entry, "link", "").strip()

        if not title or not link:
            continue

        # RemoteOK puts "Company - Role" in the title
        company = "Unknown"
        if " - " in title:
            parts = title.split(" - ", 1)
            company = parts[0].strip()
            title = parts[1].strip()

        # Tags from categories
        tags = [t.get("term", "") for t in getattr(entry, "tags", [])]

        description = _clean_text(getattr(entry, "summary", ""))

        jobs.append({
            "Title": title,
            "Company": company,
            "Link": link.split("?")[0],
            "Source": "RemoteOK",
            "Tags": ", ".join(tags[:5]),
            "Location": "Remote",
            "Description": description[:500],
        })

    print(f"  RemoteOK: {len(jobs)} jobs")
    return jobs
