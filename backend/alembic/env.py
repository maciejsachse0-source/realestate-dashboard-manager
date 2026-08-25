"""Konfiguracja Alembica. URL bazy bierzemy z najem.config, nie z alembic.ini."""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from najem.baza import Baza
from najem.config import ustawienia

# Import modeli jest konieczny, zeby autogenerate widzial tabele.
import najem.modele  # noqa: F401  isort:skip

config = context.config
config.set_main_option("sqlalchemy.url", ustawienia().baza_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Baza.metadata


def uruchom_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def uruchom_online() -> None:
    silnik = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with silnik.connect() as polaczenie:
        context.configure(
            connection=polaczenie,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    uruchom_offline()
else:
    uruchom_online()
