"""artist slug

Revision ID: 0002
Revises: 0001

Artists get a URL name ("pink-floyd") so they can have pages. Existing rows are filled in from
their names; a clash gets a numeric suffix.
"""

import sqlalchemy as sa

from alembic import op
from app.services.slugs import slugify, unique_slug

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("artist") as batch:
        batch.add_column(sa.Column("slug", sa.String(length=128), nullable=True))

    connection = op.get_bind()
    taken: set[str] = set()
    rows = connection.execute(sa.text("SELECT id, name FROM artist ORDER BY id")).fetchall()
    for artist_id, name in rows:
        slug = unique_slug(slugify(name), taken)
        taken.add(slug)
        connection.execute(
            sa.text("UPDATE artist SET slug = :slug WHERE id = :id"),
            {"slug": slug, "id": artist_id},
        )

    with op.batch_alter_table("artist") as batch:
        batch.alter_column("slug", existing_type=sa.String(length=128), nullable=False)
        batch.create_unique_constraint(op.f("uq_artist_slug"), ["slug"])


def downgrade() -> None:
    with op.batch_alter_table("artist") as batch:
        batch.drop_constraint(op.f("uq_artist_slug"), type_="unique")
        batch.drop_column("slug")
