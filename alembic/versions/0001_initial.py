"""
Initial migration — create PostGIS extension, users, geo_files, geo_features tables.

Revision ID: 0001_initial
"""

from __future__ import annotations
from typing import Sequence, Union

import geoalchemy2
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enable PostGIS extension
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis_topology")

    # ── users ──────────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("username", sa.String(100), nullable=False),
        sa.Column("hashed_password", sa.Text, nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("is_superuser", sa.Boolean, nullable=False, server_default="false"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_users_id", "users", ["id"])
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_username", "users", ["username"], unique=True)

    # ── geo_files ──────────────────────────────────────────────────────────
    op.create_table(
        "geo_files",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("owner_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column("stored_filename", sa.String(255), nullable=False),
        sa.Column("file_format", sa.Enum("geojson", "kml", "shapefile", name="file_format_enum"), nullable=False),
        sa.Column("file_size_bytes", sa.BigInteger, nullable=False),
        sa.Column("file_path", sa.Text, nullable=False),
        sa.Column(
            "status",
            sa.Enum("pending", "processing", "completed", "failed", name="processing_status_enum"),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("job_id", sa.String(36), nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("source_crs", sa.String(64), nullable=True),
        sa.Column("measurement_result", postgresql.JSONB, nullable=True),
        sa.Column(
            "geometry",
            geoalchemy2.Geography(geometry_type="GEOMETRY", srid=4326, spatial_index=False),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_geo_files_id", "geo_files", ["id"])
    op.create_index("ix_geo_files_owner_id", "geo_files", ["owner_id"])
    op.create_index("ix_geo_files_stored_filename", "geo_files", ["stored_filename"], unique=True)
    op.create_index("ix_geo_files_status", "geo_files", ["status"])
    op.create_index("ix_geo_files_job_id", "geo_files", ["job_id"])
    op.create_index("ix_geo_files_owner_created", "geo_files", ["owner_id", "created_at"])
    op.create_index(
        "ix_geo_files_geom_gist",
        "geo_files",
        ["geometry"],
        postgresql_using="gist",
    )

    # ── geo_features ───────────────────────────────────────────────────────
    op.create_table(
        "geo_features",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("geo_file_id", sa.String(36), sa.ForeignKey("geo_files.id", ondelete="CASCADE"), nullable=False),
        sa.Column("feature_index", sa.Integer, nullable=False),
        sa.Column("geometry_type", sa.String(64), nullable=False),
        sa.Column("properties", postgresql.JSONB, nullable=True),
        sa.Column("measurements", postgresql.JSONB, nullable=True),
        sa.Column("warnings", sa.JSON, nullable=True),
        sa.Column(
            "geometry",
            geoalchemy2.Geography(geometry_type="GEOMETRY", srid=4326, spatial_index=False),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_geo_features_id", "geo_features", ["id"])
    op.create_index("ix_geo_features_geo_file_id", "geo_features", ["geo_file_id"])
    op.create_index(
        "ix_geo_features_geom_gist",
        "geo_features",
        ["geometry"],
        postgresql_using="gist",
    )
    op.create_index("ix_geo_features_file_idx", "geo_features", ["geo_file_id", "feature_index"])


def downgrade() -> None:
    op.drop_table("geo_features")
    op.drop_table("geo_files")
    op.drop_table("users")
    op.execute("DROP TYPE IF EXISTS processing_status_enum")
    op.execute("DROP TYPE IF EXISTS file_format_enum")
    op.execute("DROP EXTENSION IF EXISTS postgis_topology")
    op.execute("DROP EXTENSION IF EXISTS postgis")
