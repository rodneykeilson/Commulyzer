"""FastAPI untuk analisis toksisitas komunitas Facebook."""
from __future__ import annotations

import hashlib
import os
import time
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import Depends, FastAPI, HTTPException, Request  # type: ignore
from fastapi.security import APIKeyHeader  # type: ignore
from pydantic import BaseModel  # type: ignore

from preprocess.clean import extract_items_from_raw
from scrapers.cli import _load_pages_file
from scrapers.facebook_safe import scrape_pages
from scrapers.page_discovery import discover_pages_from_keyword
from train.train_toxicity import predict_texts
from utils.aggregation import aggregate_score_for_query
from utils.io import read_jsonl
from utils.logger import get_logger

LOGGER = get_logger(__name__)

API_KEY_NAME = "X-API-Key"
API_KEY = os.getenv("API_KEY")
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

MODEL_PATH = os.getenv("MODEL_PATH", "models/best")
AUDIT_LOG = Path("audit/predictions.log")
AUDIT_LOG.parent.mkdir(parents=True, exist_ok=True)

REQUEST_COUNTS: Dict[str, List[float]] = {}
MAX_REQUESTS_PER_MIN = 5

app = FastAPI(title="Toxicity Facebook Analyzer", description="API analisis toksisitas komunitas Facebook")


class AnalyzePayload(BaseModel):
    query: str
    discover: bool = False
    pages_file: Optional[str] = None
    pages: Optional[List[str]] = None
    max_posts: int = 200
    delay: float = 1.5


class PredictPayload(BaseModel):
    texts: List[str]


class PredictResponse(BaseModel):
    scores: List[float]
    labels: List[int]
    model_version: str


def get_api_key(api_key_header_value: str = Depends(api_key_header)) -> str:
    if API_KEY is None:
        return "anonymous"
    if api_key_header_value != API_KEY:
        raise HTTPException(status_code=401, detail="API key tidak valid")
    return api_key_header_value


def rate_limit(request: Request) -> None:
    client_ip = request.client.host if request.client else "unknown"
    now = time.time()
    timestamps = REQUEST_COUNTS.setdefault(client_ip, [])
    timestamps[:] = [ts for ts in timestamps if now - ts < 60]
    if len(timestamps) >= MAX_REQUESTS_PER_MIN:
        raise HTTPException(status_code=429, detail="Terlalu banyak permintaan, coba lagi nanti")
    timestamps.append(now)


def _audit_log(entry: Dict[str, str]) -> None:
    serialized = "|".join(f"{key}={value}" for key, value in entry.items())
    with AUDIT_LOG.open("a", encoding="utf-8") as f:
        f.write(serialized + "\n")


def _load_pages(payload: AnalyzePayload) -> List[str]:
    pages: List[str] = []
    if payload.discover:
        pages.extend(discover_pages_from_keyword(payload.query))
    if payload.pages_file:
        pages.extend(_load_pages_file(payload.pages_file))
    if payload.pages:
        pages.extend(payload.pages)
    pages = list(dict.fromkeys([page for page in pages if page]))
    if not pages:
        raise HTTPException(status_code=400, detail="Tidak ada halaman yang diberikan")
    return pages


def _predict_on_rows(rows: List[Dict[str, str]]) -> Dict[str, object]:
    if not rows:
        raise HTTPException(status_code=400, detail="Tidak ada data untuk diproses")
    texts = [row.get("text", "") for row in rows]
    predictions = predict_texts(MODEL_PATH, texts)
    enriched = []
    for original, score, label in zip(rows, predictions["scores"], predictions["labels"]):
        enriched.append({**original, "score": score, "predicted_label": label, "query": original.get("query")})
    return {
        "predictions": predictions,
        "enriched": enriched,
    }


def _build_summary(query: str, rows: List[Dict[str, object]], predictions: Dict[str, List[float]]) -> Dict[str, object]:
    for row, score, label in zip(rows, predictions["scores"], predictions["labels"]):
        row["score"] = score
        row["predicted_label"] = label
        row["query"] = query
    summary = aggregate_score_for_query(rows)
    summary["query"] = query
    return summary


@app.post("/predict", response_model=PredictResponse)
async def predict(payload: PredictPayload, api_key: str = Depends(get_api_key), request: Request = None):
    if request:
        rate_limit(request)
    if not payload.texts:
        raise HTTPException(status_code=400, detail="Daftar teks kosong")
    predictions = predict_texts(MODEL_PATH, payload.texts)
    request_hash = hashlib.sha256(
        "".join(payload.texts).encode("utf-8") + os.urandom(4)
    ).hexdigest()
    _audit_log({
        "request_id": request_hash,
        "timestamp": str(time.time()),
        "model_version": MODEL_PATH,
    })
    return PredictResponse(scores=predictions["scores"], labels=predictions["labels"], model_version=MODEL_PATH)


@app.post("/analyze")
async def analyze(payload: AnalyzePayload, api_key: str = Depends(get_api_key), request: Request = None):
    if request:
        rate_limit(request)
    pages = _load_pages(payload)
    raw_path = Path("data/raw") / f"{payload.query.lower().replace(' ', '')}_api.jsonl"
    scrape_pages(pages, str(raw_path), pages_per_page=max(1, payload.max_posts // max(len(pages), 1)), delay=payload.delay)

    processed_path = Path("data/processed") / f"{payload.query.lower().replace(' ', '')}_items.csv"
    extract_items_from_raw(raw_path, processed_path)

    rows = read_jsonl(raw_path)
    if not rows:
        raise HTTPException(status_code=400, detail="Scraping tidak menghasilkan data")

    flat_rows: List[Dict[str, object]] = []
    for row in rows:
        flat_rows.append({"post_id": row.get("post_id"), "page": row.get("page"), "text": row.get("text", "")})
        for comment in (row.get("comments_sample") or [])[:10]:
            flat_rows.append({
                "post_id": comment.get("comment_id"),
                "page": row.get("page"),
                "text": comment.get("text", ""),
            })

    predictions = predict_texts(MODEL_PATH, [item["text"] for item in flat_rows])
    summary = _build_summary(payload.query, flat_rows, predictions)

    narrative = (
        f"Query: \"{payload.query}\"\n"
        f"Total item dianalisis: {summary['total_items']}\n"
        f"Item toxic: {summary['toxic_items']}\n"
        f"Persentase toxic: {summary['toxic_percent']:.1f}%\n"
        f"Per halaman: {summary['per_page']}\n"
        f"Top kata toxic: {summary['top_toxic_words']}\n"
        "Catatan: skor adalah persentase item yang model prediksi toxic (threshold 0.5)."
        " Model mungkin bias; lihat docs/ethics.md untuk pembatasan."
    )

    request_hash = hashlib.sha256(payload.query.encode("utf-8") + os.urandom(4)).hexdigest()
    _audit_log({
        "request_id": request_hash,
        "timestamp": str(time.time()),
        "model_version": MODEL_PATH,
        "query": payload.query,
    })

    return {
        "query": payload.query,
        "pages": pages,
        "summary": summary,
        "narrative": narrative,
    }
