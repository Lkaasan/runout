import re
import unicodedata


def slugify(text: str) -> str:
    """'Sigur Rós & Friends' -> 'sigur-ros-friends'. Accents are folded, never dropped whole."""
    folded = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", folded.lower()).strip("-") or "artist"


def unique_slug(base: str, taken: set[str]) -> str:
    """`base`, or `base-2`, `base-3`... the first one not already taken."""
    slug, n = base, 2
    while slug in taken:
        slug, n = f"{base}-{n}", n + 1
    return slug
