import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import seed
from app.config import settings
from app.models import Album, Base


@pytest.fixture
def db(monkeypatch):
    engine = create_engine("sqlite://", poolclass=StaticPool)
    Base.metadata.create_all(engine)
    monkeypatch.setattr(seed, "SessionLocal", sessionmaker(engine, expire_on_commit=False))
    return engine


def slugs(engine):
    with sessionmaker(engine)() as s:
        return sorted(s.scalars(select(Album.slug)))


def test_import_all_loads_every_album_folder(db):
    assert seed.main(["import", "--all"]) == 0
    assert slugs(db) == seed.album_slugs(settings.content_dir)
    assert "placeholder-album" in slugs(db) and "animals" in slugs(db)


def test_import_one_still_works(db):
    assert seed.main(["import", "placeholder-album"]) == 0
    assert slugs(db) == ["placeholder-album"]


def test_needs_a_slug_or_all_but_not_both(db):
    with pytest.raises(SystemExit):
        seed.main(["import"])
    with pytest.raises(SystemExit):
        seed.main(["import", "animals", "--all"])


def test_a_broken_album_does_not_stop_the_others(db, tmp_path, monkeypatch):
    import shutil

    shutil.copytree(settings.content_dir / "placeholder-album", tmp_path / "placeholder-album")
    broken = tmp_path / "broken"
    broken.mkdir()
    (broken / "album.yaml").write_text("slug: broken\n")  # missing required fields
    monkeypatch.setattr(settings, "content_dir", tmp_path)
    assert seed.main(["import", "--all"]) == 1
    assert slugs(db) == ["placeholder-album"]


def test_unknown_album_is_an_error(db):
    assert seed.main(["import", "nope"]) == 1
