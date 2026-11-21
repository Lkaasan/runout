import enum


class SourceKind(enum.StrEnum):
    interview = "interview"
    liner_notes = "liner_notes"
    documentary = "documentary"
    press = "press"
    social_post = "social_post"
    database = "database"
    book = "book"


class Tier(enum.StrEnum):
    primary = "primary"
    secondary = "secondary"
    tertiary = "tertiary"


class ClaimType(enum.StrEnum):
    fact = "fact"
    artist_intent = "artist_intent"
    interpretation = "interpretation"
    trivia = "trivia"


class Phase(enum.StrEnum):
    before = "before"
    during = "during"
    between = "between"
    after = "after"


class Depth(enum.StrEnum):
    listen = "listen"
    study = "study"


class Status(enum.StrEnum):
    draft = "draft"
    approved = "approved"
    rejected = "rejected"


class Stance(enum.StrEnum):
    supports = "supports"
    contradicts = "contradicts"


class EntityType(enum.StrEnum):
    """Things a claim can be about, and things a link can connect."""

    artist = "artist"
    album = "album"
    track = "track"
    person = "person"


class Relation(enum.StrEnum):
    samples = "samples"
    influenced_by = "influenced_by"
    features = "features"
    covers = "covers"
    references = "references"
