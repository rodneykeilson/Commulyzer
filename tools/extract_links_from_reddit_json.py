#!/usr/bin/env python3
"""Extract post permalinks from a Reddit listing JSON and write links ending with '/.json'.

Reads: mobilelegends_top_post.json (repo root)
Writes: mobilelegends_top_links.json (repo root)
"""
import json
import os

ROOT = os.path.dirname(os.path.abspath(__file__))
repo_root = os.path.dirname(ROOT)
in_path = os.path.join(repo_root, "mobilelegends_top_post.json")
out_path = os.path.join(repo_root, "mobilelegends_top_links.json")

def main():
    with open(in_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    links = []
    # Navigate to children list
    children = data.get("data", {}).get("children", [])
    for child in children:
        pdata = child.get("data", {})
        permalink = pdata.get("permalink")
        if not permalink:
            # try to fall back to permalink-like fields
            continue
        # ensure permalink starts with '/'
        if not permalink.startswith("/"):
            permalink = "/" + permalink
        # ensure it ends with '/'
        if not permalink.endswith("/"):
            permalink = permalink + "/"
        full = f"https://www.reddit.com{permalink}.json"
        links.append(full)

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(links, f, indent=2, ensure_ascii=False)

    print(f"Wrote {len(links)} links to: {out_path}")

if __name__ == "__main__":
    main()
