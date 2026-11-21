from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.deps import SessionDep
from app.models import Album, Artist, Link, Person, Track
from app.models.enums import Depth, EntityType
from app.schemas import EntityDetail
from app.services import serialize as ser

router = APIRouter()

_NAME = {
    EntityType.artist: (Artist, "name"),
    EntityType.album: (Album, "title"),
    EntityType.track: (Track, "title"),
    EntityType.person: (Person, "name"),
}


@router.get("/entities/{type}/{id}")
def get_entity(
    type: EntityType, id: int, session: SessionDep, depth: Depth | None = None
) -> EntityDetail:
    """Deep-dive card: approved claims plus links in both directions."""
    model, attr = _NAME[type]
    obj = session.get(model, id)
    if obj is None:
        raise HTTPException(404, f"No {type.value} {id}")

    def links(*where):
        rows = session.scalars(
            select(Link)
            .where(*where)
            .options(ser.selectinload(Link.claim).options(ser.CLAIM_LOAD))
            .order_by(Link.id)
        )
        return [out for link in rows if (out := ser.link_out(link, depth))]

    return EntityDetail(
        type=type,
        id=id,
        name=getattr(obj, attr),
        claims=[ser.claim_out(c) for c in ser.public_claims(session, [(type, id)], depth=depth)],
        links_out=links(Link.from_type == type, Link.from_id == id),
        links_in=links(Link.to_type == type, Link.to_id == id),
    )
