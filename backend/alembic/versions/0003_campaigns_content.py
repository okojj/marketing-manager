"""Idea generations, campaigns and versioned drafts."""
from alembic import op
import sqlalchemy as sa
revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("ai_generations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("owner_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("brand_id", sa.Integer(), sa.ForeignKey("brands.id"), nullable=False),
        sa.Column("request_key", sa.String(36), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("input_data", sa.JSON(), nullable=False),
        sa.Column("result", sa.JSON(), nullable=True),
        sa.Column("provider", sa.String(30), nullable=False),
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column("error", sa.String(300), nullable=True),
        sa.Column("usage", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("owner_id", "request_key", name="uq_generation_request"))
    for col in ("owner_id", "brand_id", "created_at"):
        op.create_index("ix_ai_generations_" + col, "ai_generations", [col])
    op.create_table("campaigns",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("brand_id", sa.Integer(), sa.ForeignKey("brands.id"), nullable=False),
        sa.Column("source_generation_id", sa.Integer(), sa.ForeignKey("ai_generations.id"), nullable=True),
        sa.Column("idea_index", sa.Integer(), nullable=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("goal", sa.String(500), nullable=False),
        sa.Column("brief", sa.Text(), nullable=False),
        sa.Column("keywords", sa.String(500), nullable=False),
        sa.Column("channels", sa.JSON(), nullable=False),
        sa.Column("brand_snapshot", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("source_generation_id", "idea_index", name="uq_campaign_idea"))
    op.create_index("ix_campaigns_brand_id", "campaigns", ["brand_id"])
    op.create_table("contents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("campaign_id", sa.Integer(), sa.ForeignKey("campaigns.id"), nullable=False),
        sa.Column("channel", sa.String(30), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("campaign_id", "channel", name="uq_campaign_channel"))
    op.create_index("ix_contents_campaign_id", "contents", ["campaign_id"])
    op.create_table("content_revisions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("content_id", sa.Integer(), sa.ForeignKey("contents.id"), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("source", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("content_id", "revision", name="uq_content_revision"))
    op.create_index("ix_content_revisions_content_id", "content_revisions", ["content_id"])

def downgrade():
    for name in ("content_revisions", "contents", "campaigns", "ai_generations"):
        op.drop_table(name)
