#!/usr/bin/env python3
"""
The Mac Alchemist — Site Builder
---------------------------------
Fetches Medium posts via RSS and generates index.html from template + data files.
Also fetches and caches app icons from the iTunes Search API.

Usage:
  python3 build.py
"""

import json
import re
import sys
import time
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime
from html import unescape
from pathlib import Path

BASE_DIR = Path(__file__).parent
MEDIUM_FEED_URL = "https://medium.com/feed/the-mac-alchemist"
MAX_BLOG_POSTS = 6       # cards shown in "Recent Experiments"
MAX_ALL_POSTS  = 50      # rows shown in "All Posts" (RSS caps at ~10 items)


# ─────────────────────────────────────────────
# Icon fetching
# ─────────────────────────────────────────────

def fetch_icon_url_by_id(app_store_id: int) -> str | None:
    """Fetch icon directly by App Store ID — much more reliable than search."""
    url = f"https://itunes.apple.com/lookup?id={app_store_id}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=12) as resp:
            data = json.loads(resp.read())
        results = data.get("results", [])
        if results:
            return results[0].get("artworkUrl512") or results[0].get("artworkUrl100")
    except Exception as e:
        print(f"  [icon] ID lookup {app_store_id} failed: {e}", file=sys.stderr)
    return None


def fetch_icon_url(app_name: str, search_term: str, is_ios: bool = False) -> str | None:
    """Fetch a high-res icon URL from the iTunes Search API."""
    term = search_term or app_name
    encoded = urllib.parse.quote(term)

    entities = ["software"] if is_ios else ["macSoftware", "software"]

    for entity in entities:
        url = (
            f"https://itunes.apple.com/search"
            f"?media=software&entity={entity}&term={encoded}&limit=5&country=us"
        )
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=12) as resp:
                data = json.loads(resp.read())

            results = data.get("results", [])
            if not results:
                continue

            # Prefer exact or partial name match
            for r in results:
                track_name = r.get("trackName", "").lower()
                if app_name.lower() in track_name or track_name in app_name.lower():
                    icon = r.get("artworkUrl512") or r.get("artworkUrl100")
                    if icon:
                        return icon

            # Fall back to first result
            icon = results[0].get("artworkUrl512") or results[0].get("artworkUrl100")
            if icon:
                return icon

        except Exception as e:
            print(f"  [icon] {app_name}: {e}", file=sys.stderr)

        time.sleep(0.25)

    return None


def load_icon_cache() -> dict:
    path = BASE_DIR / "icon_cache.json"
    if path.exists():
        try:
            return json.loads(path.read_text())
        except Exception:
            pass
    return {}


def save_icon_cache(cache: dict) -> None:
    (BASE_DIR / "icon_cache.json").write_text(json.dumps(cache, indent=2))


def get_icons_for_apps(apps: list) -> dict:
    """Return {app_name: icon_url} for all apps, fetching missing ones."""
    cache = load_icon_cache()
    updated = False

    for app in apps:
        name = app["name"]
        if name not in cache or cache.get(name) is None:
            print(f"  Fetching icon: {name}…")
            # Prefer App Store ID lookup (precise) over search (fuzzy)
            if app.get("app_store_id"):
                url = fetch_icon_url_by_id(app["app_store_id"])
                if not url:
                    url = fetch_icon_url(name, app.get("search_term", ""), app.get("is_ios", False))
            else:
                url = fetch_icon_url(name, app.get("search_term", ""), app.get("is_ios", False))
            cache[name] = url
            updated = True
            time.sleep(0.3)

    if updated:
        save_icon_cache(cache)
        print(f"  ✓ Icon cache updated ({sum(1 for v in cache.values() if v)} icons)")

    return cache


# ─────────────────────────────────────────────
# Medium RSS
# ─────────────────────────────────────────────

def strip_html(text: str) -> str:
    text = unescape(text)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def excerpt(text: str, max_len: int = 180) -> str:
    clean = strip_html(text)
    if len(clean) <= max_len:
        return clean
    return clean[:max_len].rsplit(" ", 1)[0] + "…"


def fetch_medium_posts(feed_url: str, max_posts: int = MAX_BLOG_POSTS) -> list | None:
    try:
        req = urllib.request.Request(
            feed_url, headers={"User-Agent": "Mozilla/5.0 (site-builder)"}
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read()
    except Exception as e:
        print(f"  [rss] Could not fetch feed: {e}", file=sys.stderr)
        return None

    try:
        root = ET.fromstring(raw)
    except ET.ParseError as e:
        print(f"  [rss] XML parse error: {e}", file=sys.stderr)
        return None

    channel = root.find("channel")
    if channel is None:
        print("  [rss] No <channel> found", file=sys.stderr)
        return None

    posts = []
    for item in channel.findall("item")[:max_posts]:
        title = item.findtext("title", "").strip()
        link  = item.findtext("link", "").strip()
        pub   = item.findtext("pubDate", "").strip()
        desc  = item.findtext("description", "").strip()

        # Parse date
        date_str = ""
        for fmt in ("%a, %d %b %Y %H:%M:%S %Z", "%a, %d %b %Y %H:%M:%S %z"):
            try:
                date_str = datetime.strptime(pub, fmt).strftime("%B %d, %Y")
                break
            except ValueError:
                continue

        # Category label (first tag)
        categories = [c.text for c in item.findall("category") if c.text]
        cat_label = categories[0] if categories else "The Mac Alchemist"

        posts.append({
            "title":    title,
            "url":      link,
            "date":     date_str,
            "category": cat_label,
            "excerpt":  excerpt(desc),
        })

    return posts or None


# ─────────────────────────────────────────────
# HTML generators
# ─────────────────────────────────────────────

# Gradient colours per category (for letter-fallback icons)
CATEGORY_GRADIENTS = {
    "launchers":     ("#6366f1", "#8b5cf6"),
    "productivity":  ("#0ea5e9", "#2563eb"),
    "utilities":     ("#14b8a6", "#0891b2"),
    "design":        ("#f59e0b", "#f97316"),
    "menubar":       ("#8b5cf6", "#ec4899"),
    "weather":       ("#38bdf8", "#0284c7"),
    "fun":           ("#f43f5e", "#f97316"),
    "health":        ("#22c55e", "#16a34a"),
    "reading":       ("#a855f7", "#7c3aed"),
    "travel":        ("#10b981", "#0d9488"),
    "entertainment": ("#f97316", "#dc2626"),
    "ios":           ("#06b6d4", "#3b82f6"),
}


def icon_html(app: dict, icon_url: str | None) -> str:
    g1, g2 = CATEGORY_GRADIENTS.get(app["category"], ("#D4AF37", "#2C8C99"))
    letter = app["icon"]
    if icon_url:
        return (
            f'<div class="app-icon" style="background:none;padding:0;">'
            f'<img src="{icon_url}" alt="{app["name"]} icon" '
            f'onerror="this.parentElement.innerHTML=\'<span class=&quot;icon-letter&quot; '
            f'style=&quot;background:linear-gradient(135deg,{g1},{g2})&quot;>{letter}</span>\'">'
            f'</div>'
        )
    return (
        f'<div class="app-icon">'
        f'<span class="icon-letter" style="background:linear-gradient(135deg,{g1},{g2});">'
        f'{letter}</span>'
        f'</div>'
    )


def generate_blog_cards(posts: list) -> str:
    cards = []
    for post in posts:
        cards.append(f"""\
                <article class="blog-card">
                    <div class="blog-meta">{post['category']} • {post['date']}</div>
                    <h3><a href="{post['url']}" target="_blank">{post['title']}</a></h3>
                    <p class="blog-excerpt">{post['excerpt']}</p>
                    <a href="{post['url']}" target="_blank" class="read-more">Read on Medium →</a>
                </article>""")
    return "\n".join(cards)


def generate_all_blog_posts(posts: list) -> str:
    rows = []
    for post in posts:
        rows.append(f"""\
                <a class="post-row" href="{post['url']}" target="_blank">
                    <span class="post-row-date">{post['date']}</span>
                    <span class="post-row-body">
                        <span class="post-row-title">{post['title']}</span>
                        <span class="post-row-category">{post['category']}</span>
                    </span>
                    <span class="post-row-arrow">Read →</span>
                </a>""")
    return "\n".join(rows)


PRICING_LABELS = {
    "free": ("Free", "free"),
    "paid": ("Paid", "paid"),
    "subscription": ("Sub", "subscription"),
    "setapp": ("SetApp", "setapp"),
}


def generate_apps_grid(apps: list, icons: dict) -> str:
    cards = []
    for app in apps:
        label, cls = PRICING_LABELS.get(app["pricing"], (app["pricing"].title(), app["pricing"]))
        icon_block = icon_html(app, icons.get(app["name"]))
        app_url = app.get("url") or "#"
        linked_icon = f'<a href="{app_url}" target="_blank" aria-label="{app["name"]}">{icon_block}</a>'
        cards.append(f"""\
                <div class="app-card" data-category="{app['category']}" data-name="{app['name'].lower()}">
                    {linked_icon}
                    <div class="app-info">
                        <div class="app-header">
                            <h3 class="app-title"><a href="{app.get('url','#') or '#'}" target="_blank">{app['name']}</a></h3>
                            <span class="app-pricing {cls}">{label}</span>
                        </div>
                        <p class="app-description">{app['description']}</p>
                        <span class="app-category-tag">{app['category_label']}</span>
                    </div>
                </div>""")
    return "\n".join(cards)


def generate_filter_buttons(apps: list) -> str:
    seen: set = set()
    cats: list = []
    for app in apps:
        k = app["category"]
        if k not in seen:
            seen.add(k)
            cats.append((k, app["category_label"]))

    buttons = [
        '                    <button class="filter-btn active" onclick="filterByCategory(\'all\')">All Apps</button>'
    ]
    for k, label in cats:
        buttons.append(
            f'                    <button class="filter-btn" onclick="filterByCategory(\'{k}\')">{label}</button>'
        )
    return "\n".join(buttons)


def generate_featured_guides(guides: list) -> str:
    cards = []
    for g in guides:
        cards.append(f"""\
                <div class="setting-card">
                    <div class="setting-number">{g['number']}</div>
                    <h3><a href="{g['url']}" target="_blank">{g['title']}</a></h3>
                    <p>{g['description']}</p>
                </div>""")
    return "\n".join(cards)


def inject(template: str, marker: str, content: str) -> str:
    pattern = rf"<!-- INJECT:{marker} -->.*?<!-- /INJECT:{marker} -->"
    replacement = f"<!-- INJECT:{marker} -->\n{content}\n<!-- /INJECT:{marker} -->"
    return re.sub(pattern, replacement, template, flags=re.DOTALL)


# ─────────────────────────────────────────────
# Main build
# ─────────────────────────────────────────────

def build():
    print("═" * 50)
    print("  The Mac Alchemist — Site Builder")
    print("═" * 50)

    # Load data
    with open(BASE_DIR / "apps.json") as f:
        apps = json.load(f)["apps"]

    with open(BASE_DIR / "featured.json") as f:
        guides = json.load(f)["guides"]

    # Load template
    template = (BASE_DIR / "template.html").read_text()

    # Icons
    print("\n[1/3] Fetching app icons…")
    icons = get_icons_for_apps(apps)

    # Medium RSS — fetch all available posts, use first 6 for featured cards
    print("\n[2/3] Fetching Medium posts…")
    all_posts = fetch_medium_posts(MEDIUM_FEED_URL, max_posts=MAX_ALL_POSTS)
    if all_posts:
        featured_posts = all_posts[:MAX_BLOG_POSTS]
        print(f"  ✓ Got {len(all_posts)} posts ({len(featured_posts)} featured)")
    else:
        all_posts = featured_posts = None
        print("  ✗ Could not fetch posts — keeping existing blog sections")

    # Build HTML
    print("\n[3/3] Generating index.html…")
    result = template

    if featured_posts:
        result = inject(result, "BLOG_POSTS", generate_blog_cards(featured_posts))
    if all_posts:
        result = inject(result, "ALL_BLOG_POSTS", generate_all_blog_posts(all_posts))

    result = inject(result, "APPS_GRID", generate_apps_grid(apps, icons))
    result = inject(result, "FILTER_BUTTONS", generate_filter_buttons(apps))
    result = inject(result, "FEATURED_GUIDES", generate_featured_guides(guides))
    result = re.sub(r"<!-- INJECT:APP_COUNT -->", str(len(apps)), result)

    (BASE_DIR / "index.html").write_text(result)

    print(f"\n✓ Built index.html")
    print(f"  • {len(apps)} apps")
    print(f"  • {sum(1 for v in icons.values() if v)} icons resolved")
    if all_posts:
        print(f"  • {len(all_posts)} blog posts ({len(featured_posts)} featured, {len(all_posts)} in full list)")
    print("═" * 50)


if __name__ == "__main__":
    build()
