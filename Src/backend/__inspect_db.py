from sqlalchemy import create_engine, text

from app.config import settings


def main() -> None:
    engine = create_engine(
        f"postgresql+psycopg2://{settings.postgres_user}:{settings.postgres_password}"
        f"@{settings.postgres_host}:{settings.postgres_port}/{settings.postgres_db}"
    )
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT tablename FROM pg_catalog.pg_tables WHERE schemaname='public' ORDER BY tablename")
        )
        print([row[0] for row in rows])


if __name__ == "__main__":
    main()