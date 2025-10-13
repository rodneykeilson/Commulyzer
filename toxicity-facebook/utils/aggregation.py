"""Fungsi agregasi skor toksisitas."""
from __future__ import annotations

import random
from collections import Counter, defaultdict
from typing import Dict, List, Any, Tuple

try:
    from sklearn.feature_extraction.text import TfidfVectorizer  # type: ignore
except ImportError:  # pragma: no cover - fallback bila scikit-learn tidak terpasang
    TfidfVectorizer = None  # type: ignore

from utils.logger import get_logger

LOGGER = get_logger(__name__)


def _bootstrap_ci(values: List[float], n_bootstrap: int = 200, confidence: float = 0.95) -> Tuple[float, float]:
    """Hitung interval kepercayaan bootstrap sederhana."""
    if not values:
        return (0.0, 0.0)
    means = []
    for _ in range(n_bootstrap):
        sample = [random.choice(values) for _ in values]
        means.append(sum(sample) / len(sample))
    means.sort()
    lower_idx = int(((1 - confidence) / 2) * len(means))
    upper_idx = int((confidence + (1 - confidence) / 2) * len(means))
    upper_idx = min(upper_idx, len(means) - 1)
    return (means[lower_idx], means[upper_idx])


def aggregate_score_for_query(posts_and_comments: List[Dict[str, Any]], threshold: float = 0.5) -> Dict[str, Any]:
    """Agregasi skor toksisitas per query."""
    if not posts_and_comments:
        return {
            "query": None,
            "total_items": 0,
            "toxic_items": 0,
            "toxic_percent": 0.0,
            "per_page": {},
            "top_toxic_words": [],
            "confidence_interval": (0.0, 0.0),
        }

    total_items = len(posts_and_comments)
    toxic_items = [item for item in posts_and_comments if item.get("score", 0.0) >= threshold]
    toxic_percent = (len(toxic_items) / total_items) * 100

    per_page_counts: Dict[str, Dict[str, int]] = defaultdict(lambda: {"total": 0, "toxic": 0})
    toxicity_values: List[float] = []
    for item in posts_and_comments:
        page = item.get("page", "unknown")
        per_page_counts[page]["total"] += 1
        toxicity_values.append(1.0 if item.get("score", 0.0) >= threshold else 0.0)
        if item.get("score", 0.0) >= threshold:
            per_page_counts[page]["toxic"] += 1

    per_page_output = {}
    for page, counts in per_page_counts.items():
        total = counts["total"]
        toxic = counts["toxic"]
        per_page_output[page] = {
            "total": total,
            "toxic": toxic,
            "toxic_percent": (toxic / total * 100) if total else 0.0,
        }

    toxic_texts = [item.get("text", "") for item in toxic_items if item.get("text")]
    top_words: List[str] = []
    if toxic_texts:
        if TfidfVectorizer is not None:
            tfidf = TfidfVectorizer(max_features=50, stop_words="english")
            try:
                tfidf.fit(toxic_texts)
                scores = tfidf.idf_
                terms = tfidf.get_feature_names_out()
                pairs = sorted(zip(terms, scores), key=lambda x: x[1])
                top_words = [term for term, _ in pairs[:10]]
            except ValueError:
                LOGGER.warning("Gagal menghitung TF-IDF untuk top toxic words")
        else:
            counts = Counter()
            for text in toxic_texts:
                counts.update(text.lower().split())
            top_words = [word for word, _ in counts.most_common(10)]

    ci_lower, ci_upper = _bootstrap_ci(toxicity_values)
    return {
        "query": posts_and_comments[0].get("query"),
        "total_items": total_items,
        "toxic_items": len(toxic_items),
        "toxic_percent": toxic_percent,
        "per_page": per_page_output,
        "top_toxic_words": top_words,
        "confidence_interval": (ci_lower * 100, ci_upper * 100),
    }
