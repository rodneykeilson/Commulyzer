"""Definisi model SQLAlchemy untuk menyimpan hasil scraping."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text  # type: ignore
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship  # type: ignore


class Base(DeclarativeBase):
    """Base deklaratif SQLAlchemy."""


class Page(Base):
    """Informasi halaman Facebook."""

    __tablename__ = "pages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    last_scraped_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    posts: Mapped[list[Post]] = relationship("Post", back_populates="page", cascade="all, delete-orphan")  # type: ignore


class Post(Base):
    """Post Facebook yang disimpan."""

    __tablename__ = "posts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    post_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    page_id: Mapped[int] = mapped_column(ForeignKey("pages.id"), nullable=False, index=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    num_comments: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    reactions_summary: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    raw_payload: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    page: Mapped[Page] = relationship("Page", back_populates="posts")  # type: ignore
    comments: Mapped[list[Comment]] = relationship("Comment", back_populates="post", cascade="all, delete-orphan")  # type: ignore


class Comment(Base):
    """Komentar yang terkait dengan post."""

    __tablename__ = "comments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    comment_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    post_id: Mapped[int] = mapped_column(ForeignKey("posts.id"), nullable=False, index=True)
    page_id: Mapped[int] = mapped_column(ForeignKey("pages.id"), nullable=False, index=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    raw_payload: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    toxicity_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    predicted_label: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    post: Mapped[Post] = relationship("Post", back_populates="comments")  # type: ignore
    page: Mapped[Page] = relationship("Page")  # type: ignore
