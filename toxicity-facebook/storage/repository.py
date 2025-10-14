"""Repository untuk interaksi database pipeline toksisitas."""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
from typing import Iterable, List, Optional

from sqlalchemy import create_engine, select  # type: ignore
from sqlalchemy.exc import IntegrityError  # type: ignore
from sqlalchemy.orm import Session  # type: ignore

from utils.logger import get_logger

from .models import Base, Comment, Page, Post

LOGGER = get_logger(__name__)


class ToxicityRepository:
    """Lapisan akses data sederhana."""

    def __init__(self, db_url: str, echo: bool = False) -> None:
        self.engine = create_engine(db_url, echo=echo, future=True)
        Base.metadata.create_all(self.engine)

    @contextmanager
    def session_scope(self):  # type: ignore
        session = Session(self.engine)
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def upsert_page(self, session: Session, page_name: str) -> Page:
        stmt = select(Page).where(Page.name == page_name)
        page = session.scalar(stmt)
        if page:
            page.last_scraped_at = datetime.utcnow()
            return page
        page = Page(name=page_name, last_scraped_at=datetime.utcnow())
        session.add(page)
        session.flush()
        return page

    def upsert_post(self, session: Session, page: Page, payload: dict) -> Post:
        stmt = select(Post).where(Post.post_id == payload.get("post_id"))
        post = session.scalar(stmt)
        if post is None:
            post = Post(
                post_id=payload.get("post_id"),
                page=page,
            )
        post.text = payload.get("text")
        post.created_at = _parse_datetime(payload.get("time"))
        post.fetched_at = _parse_datetime(payload.get("fetched_time")) or datetime.utcnow()
        post.num_comments = payload.get("comments_count")
        post.reactions_summary = payload.get("reactions_summary")
        post.raw_payload = payload
        session.add(post)
        session.flush()
        return post

    def upsert_comment(self, session: Session, page: Page, post: Post, payload: dict) -> Optional[Comment]:
        comment_id = payload.get("comment_id")
        if not comment_id:
            return None
        stmt = select(Comment).where(Comment.comment_id == comment_id)
        comment = session.scalar(stmt)
        if comment is None:
            comment = Comment(comment_id=comment_id, post=post, page=page)
        comment.text = payload.get("text")
        comment.created_at = _parse_datetime(payload.get("time"))
        comment.raw_payload = payload
        session.add(comment)
        session.flush()
        return comment

    def save_posts(self, page_name: str, posts: Iterable[dict], max_comments: int = 10) -> int:
        count = 0
        with self.session_scope() as session:
            page = self.upsert_page(session, page_name)
            for payload in posts:
                try:
                    post = self.upsert_post(session, page, payload)
                    comments = payload.get("comments_sample") or []
                    for comment in comments[:max_comments]:
                        self.upsert_comment(session, page, post, comment)
                    count += 1
                except IntegrityError as exc:
                    LOGGER.warning("Gagal menyimpan post %s: %s", payload.get("post_id"), exc)
                    session.rollback()
        LOGGER.info("Tersimpan %d post untuk halaman %s", count, page_name)
        return count

    def fetch_unlabeled_items(self, limit: int = 1000) -> List[dict]:
        with self.session_scope() as session:
            stmt = (
                select(Post)
                .where(Post.text.isnot(None))
                .order_by(Post.fetched_at.desc())
                .limit(limit)
            )
            rows = session.scalars(stmt).all()
            return [
                {
                    "id": row.post_id,
                    "page": row.page.name,
                    "time": row.created_at.isoformat() if row.created_at else None,
                    "text": row.text,
                }
                for row in rows
            ]


def _parse_datetime(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
