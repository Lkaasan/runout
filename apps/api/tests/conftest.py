from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.deps import get_session
from app.main import app
from app.models import Base
from app.services.importer import import_album
from app.services.seed_loader import load_album

CONTENT = Path(__file__).resolve().parents[3] / "content" / "albums"


@pytest.fixture
def engine():
    engine = create_engine(
        "sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def session(engine):
    with Session(engine) as s:
        yield s


@pytest.fixture
def client(engine):
    """API client on an empty database."""
    factory = sessionmaker(engine, expire_on_commit=False)

    def override():
        with factory() as s:
            yield s

    app.dependency_overrides[get_session] = override
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def seeded(client, engine):
    """API client with the placeholder album imported."""
    with Session(engine) as s:
        import_album(s, load_album(CONTENT, "placeholder-album"))
        s.commit()
    return client
