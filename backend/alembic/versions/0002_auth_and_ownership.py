"""Google users, revocable sessions and brand ownership. Preserve existing brands."""
from alembic import op
import sqlalchemy as sa
revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("google_sub", sa.String(255), nullable=False, unique=True),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False))
    op.create_table("login_sessions",
        sa.Column("token_hash", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False))
    op.create_index("ix_login_sessions_user_id", "login_sessions", ["user_id"])
    op.create_index("ix_login_sessions_expires_at", "login_sessions", ["expires_at"])
    op.add_column("brands", sa.Column("owner_id", sa.Integer(), nullable=True))
    op.create_foreign_key("fk_brands_owner", "brands", "users", ["owner_id"], ["id"])
    op.create_index("ix_brands_owner_id", "brands", ["owner_id"])

def downgrade():
    op.drop_index("ix_brands_owner_id", table_name="brands")
    op.drop_constraint("fk_brands_owner", "brands", type_="foreignkey")
    op.drop_column("brands", "owner_id")
    op.drop_table("login_sessions")
    op.drop_table("users")
