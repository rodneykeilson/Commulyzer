# Commulyzer

Commulyzer at its current state collects community discussion data from Reddit for downstream machine
learning tasks.

## Features

- Fetch up to the top 100 posts JSON for any subreddit via `scrape-subreddits.py`.
- Persist listing metadata (`posts.json`), extracted permalinks (`links.json`),
  and the 1:1 post payloads under `post_jsons/` when JSON output is enabled.
- Optionally emit `posts.csv` and `comments.csv` flattened summaries for each subreddit.
- Automatically clamp request limits to Reddit's caps (100 posts, 500 comments) and
  generate hash-shortened filenames to avoid OS path limits.
- Respectful scraping defaults: browser-like headers, retries with backoff,
  and a 30-second delay between post fetches.
- Works with multiple subreddits in a single run; each subreddit gets its own
  directory under `data/raw/reddit/`.

## Usage

```powershell
# install dependencies
pip install requests

# a VPN may be required where reddit.com is blocked
python scrape-subreddits.py subreddit1 subreddit2 --output-format both
```

Outputs are written to `data/raw/reddit/<subreddit>/`. Use `--output-format csv`
or `--output-format both` to enable CSV summaries. You can override the number
of posts (max 100), comment limit (max 500), per-request delay, time filter
(top of day/week/etc.), and TLS verification via CLI flags (`python
scrape-subreddits.py --help`).

## Roadmap

- Flatten the collected JSON/CSV into a unified tabular dataset.
- Add assisted labeling tools for downstream modeling.
