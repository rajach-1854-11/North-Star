from sqlalchemy import create_engine, text

from app.config import settings


def main() -> None:
    engine = create_engine(
        f"postgresql+psycopg2://{settings.postgres_user}:{settings.postgres_password}"
        f"@{settings.postgres_host}:{settings.postgres_port}/{settings.postgres_db}"
    )
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM event WHERE type = 'kb_chunk'"))


if __name__ == "__main__":
    main()