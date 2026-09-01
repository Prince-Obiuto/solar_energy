"""Database engine, sessions, and transaction handling."""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from apps.core.config import settings


engine = create_engine(
    settings.database_url.get_secret_value(),
    pool_pre_ping=True,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    """Yield a request-scoped session with rollback on failure."""

    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@contextmanager
def session_scope(
    session_factory: sessionmaker[Session] = SessionLocal,
) -> Generator[Session, None, None]:
    """Provide an explicit transactional scope for jobs and services."""

    session = session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
