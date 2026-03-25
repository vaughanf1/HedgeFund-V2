import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.db.models import Base

# Alembic Config object
config = context.config

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Target metadata from models
target_metadata = Base.metadata

# Override sqlalchemy.url from environment variable
# Alembic runs synchronously, so replace asyncpg with psycopg2
raw_url = os.environ["DATABASE_URL"]
sync_url = raw_url.replace("+asyncpg", "+psycopg2").replace(
    "timescaledb+", "postgresql+"
)
config.set_main_option("sqlalchemy.url", sync_url)


def include_object(object, name, type_, reflected, compare_to):
    """Exclude TimescaleDB auto-created indexes from migrations."""
    if type_ == "index" and reflected and compare_to is None:
        return False
    # Exclude TimescaleDB internal indexes
    if type_ == "index" and name is not None:
        if name.startswith("_hyper_") or name.startswith("_ts_chunk"):
            return False
    return True


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_object=include_object,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_object=include_object,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
