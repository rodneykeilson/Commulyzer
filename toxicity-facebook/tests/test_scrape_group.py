"""Uji perilaku scraping group Facebook ke database."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest  # type: ignore

from sqlalchemy import select  # type: ignore

from scrapers.facebook_to_db import scrape_group_to_db
from storage.models import Comment, Post
from storage.repository import ToxicityRepository


@pytest.mark.parametrize("env_flag", ["false", "0", "no"])
def test_scrape_group_requires_allow(monkeypatch, tmp_path, env_flag):
    """Scraping harus menolak ketika flag keamanan tidak diaktifkan."""
    db_url = f"sqlite:///{(tmp_path / 'toxicity.db').resolve().as_posix()}"
    monkeypatch.setenv("ALLOW_SCRAPE", env_flag)
    result = scrape_group_to_db(
        "mlbbidofficial",
        db_url=db_url,
        allow_scrape=False,
        max_posts=5,
        comments_per_post=2,
        delay=0,
    )
    assert result["status"] == "skipped"


def test_scrape_group_blocks_private(monkeypatch, tmp_path):
    """Group privat tidak boleh disimpan ke database."""
    db_url = f"sqlite:///{(tmp_path / 'toxicity.db').resolve().as_posix()}"

    def fake_get_posts(**kwargs):
        yield {"post_id": "p1", "privacy": "Friends"}

    monkeypatch.setattr("scrapers.facebook_to_db.get_posts", fake_get_posts)
    monkeypatch.setenv("ALLOW_SCRAPE", "true")

    result = scrape_group_to_db(
        "mlbbidofficial",
        db_url=db_url,
        allow_scrape=True,
        max_posts=3,
        comments_per_post=2,
        delay=0,
    )
    assert result["status"] == "blocked"
    repo = ToxicityRepository(db_url)
    with repo.session_scope() as session:
        posts = session.scalars(select(Post)).all()
    assert posts == []


def test_scrape_group_to_db_inserts_and_deduplicates(monkeypatch, tmp_path):
    """Pastikan post unik tersimpan dan komentar dibatasi sesuai parameter."""
    db_url = f"sqlite:///{(tmp_path / 'toxicity.db').resolve().as_posix()}"

    base_time = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)

    def make_post(idx: int):
        comment_time = base_time.replace(minute=base_time.minute + idx)
        return {
            "post_id": f"post-{idx}",
            "text": f"Contoh post {idx}",
            "time": base_time,
            "privacy": "Public",
            "comments": 2,
            "comments_full": [
                {
                    "comment_id": f"comment-{idx}-1",
                    "comment_text": "Komentar pertama",
                    "comment_time": comment_time,
                },
                {
                    "comment_id": f"comment-{idx}-2",
                    "comment_text": "Komentar kedua",
                    "comment_time": comment_time,
                },
            ],
        }

    payloads = [make_post(1), make_post(1), make_post(2)]

    captured = {}

    def fake_get_posts(**kwargs):
        captured["pages"] = kwargs.get("pages")
        captured["page_limit"] = kwargs.get("page_limit")
        for item in payloads:
            yield item

    monkeypatch.setattr("scrapers.facebook_to_db.get_posts", fake_get_posts)
    monkeypatch.setenv("ALLOW_SCRAPE", "false")

    result = scrape_group_to_db(
        "mlbbidofficial",
        db_url=db_url,
        allow_scrape=True,
        max_posts=5,
        comments_per_post=1,
        delay=0,
    )
    assert result["status"] == "success"
    assert result["posts_saved"] == 2
    assert captured["pages"] == 1
    assert captured["page_limit"] == 5

    repo = ToxicityRepository(db_url)
    with repo.session_scope() as session:
        posts = [row.post_id for row in session.scalars(select(Post)).all()]
        comments = [row.comment_id for row in session.scalars(select(Comment)).all()]
    assert len(posts) == 2
    assert len(comments) == 2
    assert set(comments) == {"comment-1-1", "comment-2-1"}


def test_scrape_group_uses_env_cookies(monkeypatch, tmp_path):
    """FACEBOOK_COOKIES harus otomatis digunakan saat argumen file tidak diberikan."""
    db_url = f"sqlite:///{(tmp_path / 'toxicity.db').resolve().as_posix()}"
    captured = {}

    def fake_get_posts(**kwargs):
        captured["cookies"] = kwargs.get("cookies")
        yield {
            "post_id": "post-env",
            "privacy": "Public",
            "comments_full": [],
        }

    monkeypatch.setattr("scrapers.facebook_to_db.get_posts", fake_get_posts)
    monkeypatch.setenv("ALLOW_SCRAPE", "true")
    monkeypatch.setenv("FACEBOOK_COOKIES", '{"c_user": "abc", "xs": "secret"}')

    result = scrape_group_to_db(
        "mlbbidofficial",
        db_url=db_url,
        allow_scrape=True,
        max_posts=1,
        comments_per_post=0,
        delay=0,
    )

    assert captured["cookies"] == {"c_user": "abc", "xs": "secret"}
    assert result["status"] == "success"
    assert result["posts_saved"] == 1


def test_scrape_group_handles_page_limit_typeerror(monkeypatch, tmp_path):
    """Fallback tanpa page_limit harus berjalan pada versi lama facebook_scraper."""
    db_url = f"sqlite:///{(tmp_path / 'toxicity.db').resolve().as_posix()}"

    def fake_get_posts_typeerror(**kwargs):
        if "page_limit" in kwargs:
            raise TypeError("unexpected keyword argument 'page_limit'")
        yield {
            "post_id": "legacy-1",
            "privacy": "Public",
            "comments_full": [],
        }

    monkeypatch.setattr("scrapers.facebook_to_db.get_posts", fake_get_posts_typeerror)
    monkeypatch.setenv("ALLOW_SCRAPE", "true")

    result = scrape_group_to_db(
        "mlbbidofficial",
        db_url=db_url,
        allow_scrape=True,
        max_posts=3,
        comments_per_post=0,
        delay=0,
    )

    assert result["status"] == "success"
    assert result["posts_saved"] == 1
