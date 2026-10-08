from datetime import datetime
from sqlalchemy import DateTime, String, Text, func, ForeignKey, JSON, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.db import Base

class Brand(Base):
    __tablename__ = "brands"
    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True, nullable=True)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text)
    target_audience: Mapped[str] = mapped_column(Text)
    tone: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    google_sub: Mapped[str] = mapped_column(String(255), unique=True)
    email: Mapped[str] = mapped_column(String(320))
    name: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

class LoginSession(Base):
    __tablename__ = "login_sessions"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True)


class Generation(Base):
    __tablename__ = "ai_generations"
    __table_args__ = (UniqueConstraint("owner_id", "request_key", name="uq_generation_request"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    brand_id: Mapped[int] = mapped_column(ForeignKey("brands.id"), index=True)
    request_key: Mapped[str] = mapped_column(String(36))
    kind: Mapped[str] = mapped_column(String(20))
    input_data: Mapped[dict] = mapped_column(JSON)
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    provider: Mapped[str] = mapped_column(String(30))
    model: Mapped[str] = mapped_column(String(100))
    error: Mapped[str | None] = mapped_column(String(300), nullable=True)
    usage: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)

class Campaign(Base):
    __tablename__ = "campaigns"
    __table_args__ = (UniqueConstraint("source_generation_id", "idea_index", name="uq_campaign_idea"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    brand_id: Mapped[int] = mapped_column(ForeignKey("brands.id"), index=True)
    source_generation_id: Mapped[int | None] = mapped_column(ForeignKey("ai_generations.id"), nullable=True)
    idea_index: Mapped[int | None] = mapped_column(nullable=True)
    title: Mapped[str] = mapped_column(String(200))
    goal: Mapped[str] = mapped_column(String(500))
    brief: Mapped[str] = mapped_column(Text)
    keywords: Mapped[str] = mapped_column(String(500))
    channels: Mapped[list] = mapped_column(JSON)
    brand_snapshot: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

class Content(Base):
    __tablename__ = "contents"
    __table_args__ = (UniqueConstraint("campaign_id", "channel", name="uq_campaign_channel"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    campaign_id: Mapped[int] = mapped_column(ForeignKey("campaigns.id"), index=True)
    channel: Mapped[str] = mapped_column(String(30))
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text)
    revision: Mapped[int] = mapped_column(default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

class ContentRevision(Base):
    __tablename__ = "content_revisions"
    __table_args__ = (UniqueConstraint("content_id", "revision", name="uq_content_revision"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    content_id: Mapped[int] = mapped_column(ForeignKey("contents.id"), index=True)
    revision: Mapped[int]
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
