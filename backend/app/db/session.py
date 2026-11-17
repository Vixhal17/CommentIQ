from contextlib import contextmanager
from typing import Generator
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from backend.config.settings import settings
from backend.app.core.logging import logger
from backend.app.db.models import Base

# Engine configuration
connect_args = {}
if settings.DATABASE_URL.startswith("sqlite"):
    connect_args["check_same_thread"] = False

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=True,
    echo=False,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """Dependency generator for clean transaction lifecycle and automatic session closing."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Database transaction error: {e}")
        raise
    finally:
        db.close()


db_context = contextmanager(get_db)


def init_db(target_engine=None) -> None:
    """
    Initialize database schema.
    If connected to PostgreSQL, attempts to enable the vector extension.
    """
    eng = target_engine or engine
    if "postgresql" in str(eng.url):
        with eng.connect() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
            conn.commit()
            logger.info("PostgreSQL pgvector extension verified/enabled.")

    Base.metadata.create_all(bind=eng)
    logger.info("Database tables initialized successfully.")

    # Automatic safe migration for SQLite
    with eng.connect() as conn:
        try:
            res = conn.execute(text("PRAGMA table_info(analyses);")).fetchall()
            col_names = [r[1] for r in res]
            if col_names and "rule_name" not in col_names:
                conn.execute(text("ALTER TABLE analyses ADD COLUMN rule_name VARCHAR(100);"))
                conn.commit()
                logger.info("Migrated analyses table: added rule_name column.")
            if col_names and "persona_name" not in col_names:
                conn.execute(text("ALTER TABLE analyses ADD COLUMN persona_name VARCHAR(100);"))
                conn.commit()
                logger.info("Migrated analyses table: added persona_name column.")
        except Exception:
            pass

    # Seed default autopilot rules if table is empty
    try:
        from backend.app.safety.rules import seed_default_autopilot_rules
        with Session(bind=eng) as session:
            seed_default_autopilot_rules(session)
    except Exception as e:
        logger.warning(f"Failed to auto-seed autopilot rules: {e}")

    # Seed default creator personas if table is empty
    try:
        from backend.app.persona.service import seed_default_personas
        with Session(bind=eng) as session:
            seed_default_personas(session)
    except Exception as e:
        logger.warning(f"Failed to auto-seed creator personas: {e}")

