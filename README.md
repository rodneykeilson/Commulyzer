# Commulyzer

Commulyzer collects Reddit community discussions, normalises the raw data, and produces rule-based toxicity labels for downstream analysis.

## Capabilities

- Scrape top-post listings, permalinks, and full post/comment payloads with `scrape-subreddits.py` (multiple subreddits per run).
- Regenerate `posts.csv` and `comments.csv` later without re-scraping via `--rebuild-from-json`.
- Merge every `comments.csv` under `data/raw/reddit/` into a single dataset with `merge_comments.py` (adds a `source_subreddit` column).
- Optionally clean labeled outputs with `clean_comments.py` (drop blank bodies, dedupe comment text).
- Run `label-comments.py` to assign multilabel toxicity scores (toxic, severe_toxic, obscene, threat, insult, identity_hate, racism) plus per-subreddit statistics.
- Maintain extensible regex libraries under `patterns/`—drop additional TSV rows to expand coverage without code changes.

## Setup

```powershell
# install dependencies
pip install requests pandas tqdm

# optional: confirm CLI options
python scrape-subreddits.py --help
python label-comments.py --help
```

## Typical Workflow

```powershell
# 1. Scrape one or more subreddits (JSON + CSV outputs)
python scrape-subreddits.py MobileLegendsGame FortniteBR --output-format both

# 2. (Optional) Rebuild CSVs later from cached JSON without new network calls
python scrape-subreddits.py MobileLegendsGame --rebuild-from-json

# 3. Merge all subreddit comments into a single file
python merge-comments.py
# -> data/processed/merged/merged_comments.csv

# 4. Label the merged dataset (creates *_labeled.csv next to the input)
python label-comments.py --input data/processed/merged/merged_comments.csv
# -> data/processed/merged/merged_comments_labeled.csv

# 5. (Optional) Clean the labeled file (removes blank bodies, deduplicates comment text)
python clean_comments.py --input data/processed/merged/merged_comments_labeled.csv
# -> data/processed/merged/merged_comments_labeled_cleaned.csv
```

The labeling script prints overall totals and per-subreddit toxicity ratios. When you pass `--threshold` the binary cut-off changes (default 0.5). Override the pattern directory or provide extra regexes with `--pattern-dir` and `--extra-patterns-dir` respectively.

## Data Layout

- `data/raw/reddit/<subreddit>/` – scraped assets (`posts.json`, `links.json`, `post_jsons/*.json`, optional CSVs).
- `data/processed/merged/` – merged, labeled, and cleaned comment datasets.
- `patterns/` – base regex TSV files per label (`<label>.tsv`).

The generated CSVs retain all original comment metadata and add `_score`, `_bin`, and a `labels` column containing the active tags.

## Notes

- All pattern files include offensive language solely for detection purposes.
- Respect Reddit rate limits; tune `--delay`, `--limit`, and `--comment-limit` as needed.
- A VPN or proxy may be required where reddit.com is blocked.
