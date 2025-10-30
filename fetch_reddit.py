#!/usr/bin/env python3
"""Fetch top posts from r/MobileLegendsGame and save to data/raw/reddit_mobilelegends_top.json

Usage: python fetch_reddit.py
"""
import os
import sys
import json
import ssl
from urllib.error import URLError

URL = "https://www.reddit.com/r/MobileLegendsGame/top/.json"

def fetch_with_requests(url, verify=True):
    import requests
    from requests.exceptions import SSLError

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/json, text/javascript, */*; q=0.01',
        'Accept-Language': 'en-US,en;q=0.8',
        'Referer': 'https://www.reddit.com/',
        'Connection': 'keep-alive',
    }

    try:
        r = requests.get(url, headers=headers, timeout=20, verify=verify)
        r.raise_for_status()
        return r.json()
    except SSLError:
        # re-raise to be handled by caller
        raise


def fetch_with_urllib(url, verify=True):
    # use urllib as a fallback if requests isn't installed
    from urllib.request import Request, urlopen

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/json, text/javascript, */*; q=0.01',
        'Accept-Language': 'en-US,en;q=0.8',
        'Referer': 'https://www.reddit.com/',
        'Connection': 'keep-alive',
    }

    req = Request(url, headers=headers)
    if verify:
        ctx = None
    else:
        ctx = ssl._create_unverified_context()
    with urlopen(req, timeout=20, context=ctx) as resp:
        return json.load(resp)


def main():
    repo_root = os.path.dirname(os.path.abspath(__file__))
    out_dir = os.path.join(repo_root, "data", "raw")
    os.makedirs(out_dir, exist_ok=True)
    out_file = os.path.join(out_dir, "reddit_mobilelegends_top.json")

    # Strategy:
    # 1) Try requests with verification on (preferred)
    # 2) If requests unavailable, try urllib with verification on
    # 3) If verification error occurs, retry with verification disabled (insecure, last resort)

    data = None
    last_err = None

    # Try requests first
    try:
        try:
            import requests  # noqa: F401
            print("Trying fetch with requests (verify=True)")
            data = fetch_with_requests(URL, verify=True)
        except Exception as e:
            # either requests not installed or request failed; remember and try urllib
            last_err = e
            print("Requests fetch failed or not available; will try urllib. Reason:", repr(e))
            data = fetch_with_urllib(URL, verify=True)
    except ssl.SSLError as e:
        last_err = e
        print("SSL verification failed; retrying without verification (INSECURE)", file=sys.stderr)
        try:
            # try requests without verification if available
            try:
                import requests  # noqa: F401
                data = fetch_with_requests(URL, verify=False)
            except Exception:
                data = fetch_with_urllib(URL, verify=False)
        except Exception as e2:
            last_err = e2
    except URLError as e:
        last_err = e
    except Exception as e:
        last_err = e

    if data is None:
        # Final insecure fallback: try without verification regardless of previous error
        print("All verified attempts failed; trying final INSECURE fetch (verify=False)", file=sys.stderr)
        try:
            try:
                import requests  # noqa: F401
                data = fetch_with_requests(URL, verify=False)
            except Exception:
                data = fetch_with_urllib(URL, verify=False)
        except Exception as e:
            last_err = e

    if data is None:
        print("Failed to fetch JSON from Reddit; last error:", repr(last_err), file=sys.stderr)
        sys.exit(2)

    # Save the JSON
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"Saved JSON to: {out_file}")


if __name__ == "__main__":
    main()
