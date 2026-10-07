from alembic import context
from app.db import Base, engine
from app import models  # Register all models with metadata.
from app.config import settings

target_metadata = Base.metadata
if context.is_offline_mode():
    context.configure(url=settings.database_url, target_metadata=target_metadata,
                      literal_binds=True, dialect_opts={"paramstyle": "named"})
    with context.begin_transaction():
        context.run_migrations()
else:
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata,
                          compare_type=True)
        with context.begin_transaction():
            context.run_migrations()
