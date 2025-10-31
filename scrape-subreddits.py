"""End-to-end Reddit scraper for one or more subreddits.

For each subreddit the script performs:
* Download the /top listing JSON (up to 100 posts by default).
* Extract the top post permalinks into a links.json file when JSON output is enabled.
* Fetch each individual post JSON (including up to 500 comments) and store it under
    ``post_jsons/`` when JSON output is enabled.
* Optionally flatten the posts and comments into CSV summary files.

The script relies on the public Reddit JSON endpoints (no official API keys).
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
import time
from datetime import datetime
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


def extract_links(listing_json: dict) -> List[dict[str, Any]]:
    children = listing_json.get("data", {}).get("children", [])
    links: List[dict[str, Any]] = []
    for rank, child in enumerate(children, start=1):
        child_data = child.get("data", {})
        permalink = child_data.get("permalink")
        if not permalink:
            continue
        if not permalink.startswith("/"):
            permalink = "/" + permalink
        if not permalink.endswith("/"):
            permalink = permalink + "/"
        links.append(
            {
                "rank": rank,
                "id": child_data.get("id"),
                "title": child_data.get("title"),
                "created_utc": child_data.get("created_utc"),
                "permalink": permalink,
                "url": f"{BASE_URL}{permalink}.json",
            }
        )
    return links


def derive_filename(link_info: dict[str, Any], post_data: dict[str, Any] | None) -> str:
    rank = link_info.get("rank")
    post_id = link_info.get("id") or "post"
    slug_source = link_info.get("title") or link_info.get("permalink") or "post"
    created_ts = link_info.get("created_utc")

    if post_data:
        post_id = post_data.get("id") or post_id
        created_ts = post_data.get("created_utc") or created_ts
        slug_source = post_data.get("title") or slug_source

    date_fragment = ""
    if created_ts:
        try:
            date_fragment = datetime.utcfromtimestamp(float(created_ts)).strftime("%Y%m%d")
        except (ValueError, TypeError, OverflowError):
            date_fragment = ""

    safe_id = re.sub(r"[^A-Za-z0-9_-]+", "_", str(post_id)) or "post"
    safe_slug = re.sub(r"[^A-Za-z0-9_-]+", "_", slug_source) or "post"
    safe_id = shorten_component(safe_id, 40)
    safe_slug = shorten_component(safe_slug, 100)

    parts: List[str] = []
    if rank is not None:
        try:
            parts.append(f"{int(rank):03d}")
        except (ValueError, TypeError):
            pass
    if date_fragment:
        parts.append(date_fragment)
    parts.append(safe_id)
    parts.append(safe_slug)

    return "_".join(parts) + ".json"


def save_json(data: Any, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def write_csv(rows: List[dict[str, Any]], fieldnames: List[str], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fp:
        writer = csv.DictWriter(fp, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def format_timestamp(epoch: Any) -> str:
    try:
        return datetime.utcfromtimestamp(float(epoch)).isoformat()
    except (TypeError, ValueError, OverflowError):
        return ""


def shorten_component(text: str, max_length: int = 80) -> str:
    if len(text) <= max_length:
        return text
    digest = hashlib.sha1(text.encode("utf-8")).hexdigest()[:8]
    prefix_length = max(1, max_length - 9)
    return f"{text[:prefix_length]}_{digest}"


def flatten_post_record(
    subreddit: str, link_info: dict[str, Any], post_data: dict[str, Any] | None
) -> dict[str, Any]:
    post_data = post_data or {}
    permalink = post_data.get("permalink") or link_info.get("permalink") or ""
    if permalink and not permalink.startswith("http"):
        permalink = f"{BASE_URL}{permalink}"

    created_utc = post_data.get("created_utc") or link_info.get("created_utc")

    return {
        "rank": link_info.get("rank"),
        "post_id": post_data.get("id") or link_info.get("id"),
        "title": post_data.get("title") or link_info.get("title"),
        "author": post_data.get("author") or post_data.get("author_fullname"),
        "subreddit": post_data.get("subreddit") or subreddit,
        "created_utc": created_utc,
        "created_iso": format_timestamp(created_utc),
        "score": post_data.get("score"),
        "upvote_ratio": post_data.get("upvote_ratio"),
        "num_comments": post_data.get("num_comments"),
        "permalink": permalink,
        "url": post_data.get("url_overridden_by_dest")
        or post_data.get("url")
        or link_info.get("url"),
        "selftext": post_data.get("selftext"),
        "link_flair_text": post_data.get("link_flair_text"),
        "over_18": post_data.get("over_18"),
    }


def _flatten_comment_tree(
    nodes: Iterable[dict[str, Any]],
    *,
    post_context: dict[str, Any],
    depth: int,
    records: List[dict[str, Any]],
) -> None:
    for node in nodes:
        if not isinstance(node, dict):
            continue
        kind = node.get("kind")
        data = node.get("data", {})
        if kind != "t1":
            # skip "more" or other aggregations
            continue

        created_utc = data.get("created_utc")
        comment_permalink = data.get("permalink")
        if comment_permalink and not comment_permalink.startswith("http"):
            comment_permalink = f"{BASE_URL}{comment_permalink}"
        record = {
            "post_id": post_context.get("post_id"),
            "post_rank": post_context.get("rank"),
            "post_title": post_context.get("title"),
            "subreddit": post_context.get("subreddit"),
            "comment_id": data.get("id"),
            "parent_id": data.get("parent_id"),
            "author": data.get("author"),
            "created_utc": created_utc,
            "created_iso": format_timestamp(created_utc),
            "score": data.get("score"),
            "depth": depth,
            "body": data.get("body"),
            "permalink": comment_permalink,
            "is_submitter": data.get("is_submitter"),
        }
        records.append(record)

        replies = data.get("replies")
        if isinstance(replies, dict):
            children = replies.get("data", {}).get("children", [])
            _flatten_comment_tree(
                children,
                post_context=post_context,
                depth=depth + 1,
                records=records,
            )


def flatten_comments(post_json: Any, post_context: dict[str, Any]) -> List[dict[str, Any]]:
    if not isinstance(post_json, list) or len(post_json) < 2:
        return []
    comment_listing = post_json[1]
    if not isinstance(comment_listing, dict):
        return []
    children = comment_listing.get("data", {}).get("children", [])
    records: List[dict[str, Any]] = []
    _flatten_comment_tree(children, post_context=post_context, depth=0, records=records)
    return records


def rebuild_csv_from_cache(subreddit: str) -> None:
    """Recreate CSV summaries from previously saved JSON artifacts."""
    base_dir = DATA_ROOT / subreddit
    posts_dir = base_dir / "post_jsons"
    links_path = base_dir / "links.json"
    if not posts_dir.exists():
        raise FileNotFoundError(f"No cached post_jsons/ directory for r/{subreddit} (expected {posts_dir})")

    links: list[dict[str, Any]] = []
    if links_path.exists():
        try:
            links = json.loads(links_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            print(f"[WARN] Failed to parse {links_path}: {exc}. Continuing without link metadata.")

    link_map: dict[str, dict[str, Any]] = {}
    for entry in links:
        if isinstance(entry, dict):
            post_id = str(entry.get("id") or "").strip()
            if post_id:
                link_map[post_id] = entry

    posts_records: List[dict[str, Any]] = []
    comments_records: List[dict[str, Any]] = []

    json_files = sorted(posts_dir.glob("*.json"))
    for idx, path in enumerate(json_files, start=1):
        try:
            post_json = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            print(f"[WARN] Skipping {path.name}: invalid JSON ({exc})")
            continue

        post_data: dict[str, Any] | None = None
        if isinstance(post_json, list) and post_json:
            first = post_json[0]
            if isinstance(first, dict):
                children = first.get("data", {}).get("children", [])
                if children:
                    maybe_post = children[0].get("data")
                    if isinstance(maybe_post, dict):
                        post_data = maybe_post
        if post_data is None:
            post_data = {}

        post_id = str(post_data.get("id") or "").strip()
        link_info = link_map.get(post_id, {})
        if not link_info:
            link_info = {
                "rank": idx,
                "id": post_data.get("id") or path.stem,
                "title": post_data.get("title"),
                "created_utc": post_data.get("created_utc"),
                "permalink": post_data.get("permalink"),
                "url": post_data.get("permalink"),
            }
        else:
            link_info = dict(link_info)
            link_info.setdefault("rank", idx)

        post_record = flatten_post_record(subreddit, link_info, post_data)
        posts_records.append(post_record)
        comments_records.extend(
            flatten_comments(
                post_json,
                {
                    "post_id": post_record.get("post_id"),
                    "rank": post_record.get("rank"),
                    "title": post_record.get("title"),
                    "subreddit": post_record.get("subreddit"),
                },
            )
        )

    if not posts_records:
        print(f"[WARN] No posts reconstructed for r/{subreddit}")
        return

    def _rank_key(value: Any) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return float("inf")

    posts_records.sort(key=lambda r: (_rank_key(r.get("rank")), r.get("created_utc") or 0))

    posts_csv_path = base_dir / "posts.csv"
    comments_csv_path = base_dir / "comments.csv"
    write_csv(
        posts_records,
        [
            "rank",
            "post_id",
            "title",
            "author",
            "subreddit",
            "created_utc",
            "created_iso",
            "score",
            "upvote_ratio",
            "num_comments",
            "permalink",
            "url",
            "selftext",
            "link_flair_text",
            "over_18",
        ],
        posts_csv_path,
    )
    write_csv(
        comments_records,
        [
            "post_id",
            "post_rank",
            "post_title",
            "subreddit",
            "comment_id",
            "parent_id",
            "author",
            "created_utc",
            "created_iso",
            "score",
            "depth",
            "body",
            "permalink",
            "is_submitter",
        ],
        comments_csv_path,
    )
    print(f"Rebuilt CSV summaries for r/{subreddit} at {posts_csv_path} and {comments_csv_path}")


def process_subreddit(
    subreddit: str,
    *,
    session: requests.Session,
    limit: int,
    comment_limit: int,
    delay: float,
    time_filter: str,
    output_formats: set[str],
) -> None:
    print(f"\n=== Processing r/{subreddit} ===")
    base_dir = DATA_ROOT / subreddit
    posts_path = base_dir / "posts.json"
    links_path = base_dir / "links.json"
    posts_dir = base_dir / "post_jsons"

    listing_limit = max(1, min(limit, 100))
    comment_limit_capped = max(1, min(comment_limit, 500))

    listing_url = f"{BASE_URL}/r/{subreddit}/top/.json"
    listing_params = {"limit": listing_limit, "raw_json": 1, "t": time_filter}
    listing_json = fetch_json(session, listing_url, params=listing_params)
    if "json" in output_formats:
        save_json(listing_json, posts_path)
        print(f"Saved listing to {posts_path}")
    else:
        print(f"Fetched listing for r/{subreddit}")

    links = extract_links(listing_json)
    if "json" in output_formats:
        save_json(links, links_path)
        print(f"Saved {len(links)} links to {links_path}")
    else:
        print(f"Extracted {len(links)} post permalinks")

    total_links = len(links)
    posts_records: List[dict[str, Any]] = []
    comments_records: List[dict[str, Any]] = []

    for link_info in links:
        post_url = link_info.get("url")
        if not post_url:
            continue
        rank_label = link_info.get("rank")
        progress = f"{rank_label}/{total_links}" if rank_label else f"?/{total_links}"
        params = {"raw_json": 1, "limit": comment_limit_capped}
        post_json = fetch_json(session, post_url, params=params)

        post_data = None
        if isinstance(post_json, list) and post_json:
            first = post_json[0]
            if isinstance(first, dict):
                children = first.get("data", {}).get("children", [])
                if children:
                    post_data = children[0].get("data")

        if "json" in output_formats:
            filename = derive_filename(link_info, post_data)
            target_path = posts_dir / filename
            print(f"[{progress}] Fetching {post_url} -> {target_path}")
            save_json(post_json, target_path)
        else:
            print(f"[{progress}] Fetching {post_url}")

        if "csv" in output_formats:
            post_record = flatten_post_record(subreddit, link_info, post_data)
            posts_records.append(post_record)
            comments_records.extend(
                flatten_comments(
                    post_json,
                    {
                        "post_id": post_record.get("post_id"),
                        "rank": post_record.get("rank"),
                        "title": post_record.get("title"),
                        "subreddit": post_record.get("subreddit"),
                    },
                )
            )
        time.sleep(delay)

    if "csv" in output_formats:
        posts_csv_path = base_dir / "posts.csv"
        comments_csv_path = base_dir / "comments.csv"
        write_csv(
            posts_records,
            [
                "rank",
                "post_id",
                "title",
                "author",
                "subreddit",
                "created_utc",
                "created_iso",
                "score",
                "upvote_ratio",
                "num_comments",
                "permalink",
                "url",
                "selftext",
                "link_flair_text",
                "over_18",
            ],
            posts_csv_path,
        )
        write_csv(
            comments_records,
            [
                "post_id",
                "post_rank",
                "post_title",
                "subreddit",
                "comment_id",
                "parent_id",
                "author",
                "created_utc",
                "created_iso",
                "score",
                "depth",
                "body",
                "permalink",
                "is_submitter",
            ],
            comments_csv_path,
        )
        print(f"Wrote CSV summaries to {posts_csv_path} and {comments_csv_path}")


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
        default=100,
        help="Maximum number of posts to fetch from the top listing (default: 100).",
    )
    parser.add_argument(
        "--comment-limit",
        type=int,
        default=500,
        help="Maximum number of comments to retrieve per post (default: 500).",
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
    parser.add_argument(
        "--rebuild-from-json",
        action="store_true",
        help="Recreate CSV outputs from previously saved JSON files without new network calls.",
    )
    parser.add_argument(
        "--output-format",
        choices=["json", "csv", "both"],
        default="json",
        help="Persist results as JSON files, CSV summaries, or both (default: json).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    subreddits = parse_subreddits(args.subreddits)
    if not subreddits:
        print("No subreddits provided. Exiting.")
        sys.exit(0)

    if args.rebuild_from_json:
        for subreddit in subreddits:
            try:
                rebuild_csv_from_cache(subreddit)
            except Exception as exc:
                print(f"Failed to rebuild CSV for r/{subreddit}: {exc}", file=sys.stderr)
        return

    session = build_session(args.user_agent, not args.insecure)

    if args.output_format == "both":
        output_formats = {"json", "csv"}
    elif args.output_format == "csv":
        output_formats = {"csv"}
    else:
        output_formats = {"json"}

    for subreddit in subreddits:
        try:
            process_subreddit(
                subreddit,
                session=session,
                limit=args.limit,
                comment_limit=args.comment_limit,
                delay=args.delay,
                time_filter=args.time_filter,
                output_formats=output_formats,
            )
        except Exception as exc:
            print(f"Failed to process r/{subreddit}: {exc}", file=sys.stderr)


if __name__ == "__main__":
    main()
