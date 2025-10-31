"""End-to-end Reddit scraper for one or more subreddits.

For each subreddit the script performs:
* Download the /top listing JSON.
* Extract the top post permalinks into a links.json file.
* Fetch each individual post JSON and store it under post_jsons/.

The script relies on the public Reddit JSON endpoints (no official API keys).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path
from typing import Any, Iterable, List, Sequence
from urllib.parse import urlparse

import requests

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
BASE_URL = "https://www.reddit.com"
DATA_ROOT = Path(__file__).resolve().parent / "data" / "raw" / "reddit"


def parse_subreddits(args_subreddits: Sequence[str]) -> List[str]:
    if args_subreddits:
        return [name.strip() for name in args_subreddits if name.strip()]

    raw = input("Enter subreddit names (comma-separated): ").strip()
    return [name.strip() for name in raw.split(",") if name.strip()]


def build_session(user_agent: str, verify: bool) -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": user_agent,
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Accept-Language": "en-US,en;q=0.8",
            "Referer": "https://www.reddit.com/",
            "Connection": "keep-alive",
        }
    )
    session.verify = verify
    return session


def fetch_json(
    session: requests.Session,
    url: str,
    *,
    params: dict | None = None,
    retries: int = 3,
    backoff: float = 1.0,
) -> Any:
    last_exc: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            response = session.get(url, params=params, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as exc:
            last_exc = exc
            if attempt == retries:
                break
            wait_time = backoff * (2 ** (attempt - 1))
            time.sleep(wait_time)
    raise RuntimeError(f"Failed to fetch {url!r}: {last_exc}") from last_exc


def extract_links(listing_json: dict) -> List[str]:
    children = listing_json.get("data", {}).get("children", [])
    links: List[str] = []
    for child in children:
        permalink = child.get("data", {}).get("permalink")
        if not permalink:
            continue
        if not permalink.startswith("/"):
            permalink = "/" + permalink
        if not permalink.endswith("/"):
            permalink = permalink + "/"
        links.append(f"{BASE_URL}{permalink}.json")
    return links


def derive_filename(post_url: str) -> str:
    parsed = urlparse(post_url)
    parts = [segment for segment in parsed.path.split("/") if segment]
    try:
        idx = parts.index("comments")
    except ValueError:
        slug = parts[-1] if parts else "post"
        post_id = "post"
    else:
        post_id = parts[idx + 1] if len(parts) > idx + 1 else "post"
        slug = parts[idx + 2] if len(parts) > idx + 2 else "post"
    safe_id = re.sub(r"[^A-Za-z0-9_-]+", "_", post_id) or "post"
    safe_slug = re.sub(r"[^A-Za-z0-9_-]+", "_", slug) or "post"
    return f"{safe_id}_{safe_slug}.json"


def save_json(data: Any, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def process_subreddit(
    subreddit: str,
    *,
    session: requests.Session,
    limit: int,
    delay: float,
    time_filter: str,
) -> None:
    print(f"\n=== Processing r/{subreddit} ===")
    base_dir = DATA_ROOT / subreddit
    posts_path = base_dir / "posts.json"
    links_path = base_dir / "links.json"
    posts_dir = base_dir / "post_jsons"

    listing_url = f"{BASE_URL}/r/{subreddit}/top/.json"
    listing_params = {"limit": limit, "raw_json": 1, "t": time_filter}
    listing_json = fetch_json(session, listing_url, params=listing_params)
    save_json(listing_json, posts_path)
    print(f"Saved listing to {posts_path}")

    links = extract_links(listing_json)
    save_json(links, links_path)
    print(f"Saved {len(links)} links to {links_path}")

    for idx, post_url in enumerate(links, start=1):
        filename = derive_filename(post_url)
        target_path = posts_dir / filename
        print(f"[{idx}/{len(links)}] Fetching {post_url} -> {target_path}")
        params = {"raw_json": 1}
        post_json = fetch_json(session, post_url, params=params)
        save_json(post_json, target_path)
        time.sleep(delay)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Scrape Reddit top posts JSON for one or more subreddits."
    )
    parser.add_argument(
        "subreddits",
        nargs="*",
        help="Subreddit names (without the r/ prefix). When omitted you will be prompted.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=25,
        help="Maximum number of posts to fetch from the top listing (default: 25).",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=5.0,
        help="Delay in seconds between individual post requests (default: 5.0).",
    )
    parser.add_argument(
        "--user-agent",
        default=DEFAULT_USER_AGENT,
        help="Custom User-Agent header to send with requests.",
    )
    parser.add_argument(
        "--time-filter",
        choices=["hour", "day", "week", "month", "year", "all"],
        default="day",
        help="Which 'top' timeframe to use (default: day).",
    )
    parser.add_argument(
        "--insecure",
        action="store_true",
        help="Disable TLS certificate verification (only if you trust the network).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    subreddits = parse_subreddits(args.subreddits)
    if not subreddits:
        print("No subreddits provided. Exiting.")
        sys.exit(0)

    session = build_session(args.user_agent, not args.insecure)

    for subreddit in subreddits:
        try:
            process_subreddit(
                subreddit,
                session=session,
                limit=args.limit,
                delay=args.delay,
                time_filter=args.time_filter,
            )
        except Exception as exc:
            print(f"Failed to process r/{subreddit}: {exc}", file=sys.stderr)


if __name__ == "__main__":
    main()
