# Commulyzer

Commulyzer at its current state collects community discussion data from Reddit for downstream machine
learning tasks.

## Features

- Fetch the 25 top posts JSON for any subreddit via `scrape_subreddits.py`.
- Persist listing metadata (`posts.json`), extracted permalinks (`links.json`),
  and the 1:1 post payloads under `post_jsons/`.
- Respectful scraping defaults: browser-like headers, retries with backoff,
  and a 30-second delay between post fetches.
- Works with multiple subreddits in a single run; each subreddit gets its own
  directory under `data/raw/reddit/`.

## Usage

```powershell
# install dependencies
pip install requests
pip install playwright

# a VPN may be required where reddit.com is blocked
python scrape_subreddits.py subreddit1 subreddit2 and_so_on
```

Outputs are written to `data/raw/reddit/<subreddit>/`. You can override the
number of posts, per-request delay, time filter (top of day/week/etc.), and
whether to skip TLS verification via CLI flags (`python scrape_subreddits.py --help`).

## Roadmap

- Flatten the collected JSON into a unified tabular dataset.
- Add assisted labeling tools for downstream modeling.
