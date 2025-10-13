import json
from pathlib import Path

import pytest  # type: ignore

from scrapers import facebook_safe


class DummyPost:
    def __init__(self, idx: int):
        self.idx = idx

    def to_dict(self):
        return {
            "post_id": f"post{self.idx}",
            "page_id": "page",
            "time": None,
            "text": f"Text {self.idx}",
            "comments": 0,
            "reactions": {"like": self.idx},
            "comments_full": [],
        }


def fake_get_posts(page, pages=1, options=None, cookies=None):
    for idx in range(pages):
        yield {
            "post_id": f"{page}_{idx}",
            "time": None,
            "text": f"Konten {idx}",
            "comments": 0,
            "reactions": {"like": idx},
            "comments_full": [],
        }


@pytest.fixture(autouse=True)
def mock_get_posts(monkeypatch, tmp_path):
    monkeypatch.setattr(facebook_safe, "get_posts", fake_get_posts, raising=False)
    yield


def test_scrape_pages_writes_jsonl(tmp_path):
    out_file = tmp_path / "out.jsonl"
    facebook_safe.scrape_pages(["page1"], str(out_file), pages_per_page=2, delay=0)
    assert out_file.exists()
    lines = out_file.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    sample = json.loads(lines[0])
    assert {"post_id", "page", "text", "comments_sample"}.issubset(sample.keys())
