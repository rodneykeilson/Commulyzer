MobileLegendsGame subreddit data
================================

This folder stores the extracted data for the r/MobileLegendsGame subreddit in an organized layout.

Structure
- posts.json             -- full subreddit listing JSON (copy of root mobilelegends_top_post.json)
- links.json             -- array of post links (copy of root mobilelegends_top_links.json)
- post_jsons/            -- per-post JSON files (placeholders). Paste each post's JSON into the matching file.

Filenames in post_jsons are formatted as: {post_id}_{slug}.json where slug is sanitized (non-alnum -> underscore).

Instructions
1. Paste the full JSON for a specific post into the corresponding file inside `post_jsons/`.
2. Keep filenames unchanged to preserve mapping.
3. If you prefer a different layout or need automated fetching, I can add a script to pull each `.json` using these links.
