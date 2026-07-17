from __future__ import annotations

from config import DATABASE_URL
from repositories.sqlalchemy_adapter import SqlAlchemyAdapter
from repositories.sqlalchemy_migrations import ensure_domain_schema


def main() -> None:
    adapter = SqlAlchemyAdapter(database_url=DATABASE_URL)
    status = adapter.ping()
    if not status.ok:
        raise RuntimeError(f"Database ping failed: {status.message}")

    engine = adapter.get_engine()
    if engine is None:
        raise RuntimeError("SQLAlchemy engine unavailable")

    version = ensure_domain_schema(engine)
    print(
        f"Database bootstrap completed. dialect={status.dialect} version={version} url={DATABASE_URL}"
    )


if __name__ == "__main__":
    main()
