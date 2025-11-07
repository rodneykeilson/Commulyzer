# Commulyzer

Commulyzer collects Reddit community discussions, normalises the raw data, and produces rule-based toxicity labels for downstream analysis.

## Data Acquisition

Reddit data is fetched using [ScrapiReddit](https://github.com/rodneykeilson/ScrapiReddit), a dedicated scraping tool created and maintained by the author of this repository. This ensures full control over the scraping process and data provenance.

## Capabilities

- Import top-post listings, permalinks, and full post/comment payloads from ScrapiReddit outputs (multiple subreddits per run).
- Merge every `comments.csv` under `data/raw/reddit/` into a single dataset with `merge-comments.py` (adds a `source_subreddit` column).
- Optionally clean labeled outputs with `clean_comments.py` (drop blank bodies, dedupe comment text).
- Run `label-comments.py` to assign multilabel toxicity scores (toxic, severe_toxic, obscene, threat, insult, identity_hate, racism) plus per-subreddit statistics.
- Maintain extensible regex libraries under `patterns/`—drop additional TSV rows to expand coverage without code changes.

## Setup

```powershell
# install dependencies
pip install requests pandas tqdm

# optional: confirm CLI options
python label-comments.py --help
```

## Typical Workflow

```powershell
# 1. Scrape one or more subreddits using ScrapiReddit (see its README for usage)
#    Place the resulting JSON/CSV files under data/raw/reddit/<subreddit>/

# 2. Merge all subreddit comments into a single file
python merge-comments.py
# -> data/processed/merged/merged_comments.csv

# 3. Label the merged dataset (creates *_labeled.csv next to the input)
python label-comments.py --input data/processed/merged/merged_comments.csv
# -> data/processed/merged/merged_comments_labeled.csv

# 4. (Optional) Clean the labeled file (removes blank bodies, deduplicates comment text)
python clean-comments.py --input data/processed/merged/merged_comments_labeled.csv
# -> data/processed/merged/merged_comments_labeled_cleaned.csv
```

The labeling script prints overall totals and per-subreddit toxicity ratios. When you pass `--threshold` the binary cut-off changes (default 0.5). Override the pattern directory or provide extra regexes with `--pattern-dir` and `--extra-patterns-dir` respectively.

## Data Layout

- `data/raw/reddit/<subreddit>/` – scraped assets (`posts.json`, `links.json`, `post_jsons/*.json`, optional CSVs) from ScrapiReddit.
- `data/processed/merged/` – merged, labeled, and cleaned comment datasets.
- `patterns/` – base regex TSV files per label (`<label>.tsv`).

The generated CSVs retain all original comment metadata and add `_score`, `_bin`, and a `labels` column containing the active tags.

## Notes

- All pattern files include offensive language solely for detection purposes.
- Respect Reddit rate limits; tune ScrapiReddit's delay and limit options as needed.
- A VPN or proxy may be required where reddit.com is blocked.
