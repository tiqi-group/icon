from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

import icon.server.data_access.db_context.sqlite
import icon.server.data_access.models.sqlite.base

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Setting the database URL (see https://stackoverflow.com/a/66829448)
config.set_main_option(
    "sqlalchemy.url", icon.server.data_access.db_context.sqlite.SQLITE_URL
)

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None and not getattr(
    context, "_from_application", False
):
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
target_metadata = icon.server.data_access.models.sqlite.base.Base.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
