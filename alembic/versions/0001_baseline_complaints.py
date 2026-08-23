"""Baseline the complaints table with the current AIVOA model.

This migration is intentionally defensive because older AIVOA databases may
already have a complaints table created by SQLAlchemy create_all().
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001_baseline_complaints"
down_revision = None
branch_labels = None
depends_on = None


COLUMNS = [
    ("complaint_source", sa.String(length=100), False),
    ("customer_name", sa.String(length=255), False),
    ("product_name", sa.String(length=255), False),
    ("product_strength", sa.String(length=100), True),
    ("batch_number", sa.String(length=100), False),
    ("affected_quantity", sa.String(length=100), True),
    ("manufacturing_date", sa.String(length=50), True),
    ("expiry_date", sa.String(length=50), True),
    ("originating_site_block", sa.String(length=100), False),
    ("impacted_npm", sa.Text(), True),
    ("complaint_category", sa.String(length=100), False),
    ("complaint_date", sa.String(length=50), True),
    ("priority", sa.String(length=50), True),
    ("complaint_description", sa.Text(), False),
    ("severity_suggested", sa.String(length=50), True),
    ("suggested_next_action", sa.Text(), True),
    ("initial_risk_assessment", sa.Text(), True),
    ("complaint_summary", sa.Text(), True),
    ("root_cause_recommendation", sa.Text(), True),
    ("capa_recommendation", sa.Text(), True),
    ("raw_input", sa.Text(), True),
    ("chat_history", postgresql.JSON(astext_type=sa.Text()), True),
    ("status", sa.String(length=50), False),
    ("created_at", sa.DateTime(), True),
    ("committed_at", sa.DateTime(), True),
]


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "complaints" not in inspector.get_table_names():
        op.create_table(
            "complaints",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            *[
                sa.Column(name, column_type, nullable=nullable)
                for name, column_type, nullable in COLUMNS
            ],
        )
        return

    columns = {column["name"]: column for column in inspector.get_columns("complaints")}

    # Older AIVOA versions used an integer id. The current model uses UUIDs.
    # Only convert automatically when the old table is empty; never risk
    # corrupting existing production records.
    if "id" in columns:
        id_type = str(columns["id"]["type"]).lower()
        if "integer" in id_type or "bigint" in id_type:
            row_count = bind.execute(sa.text("SELECT COUNT(*) FROM complaints")).scalar_one()
            if row_count:
                raise RuntimeError(
                    "Cannot migrate complaints.id from integer to UUID while records exist. "
                    "Back up and migrate existing complaint IDs explicitly first."
                )
            op.execute("ALTER TABLE complaints ALTER COLUMN id DROP DEFAULT")
            op.execute(
                "ALTER TABLE complaints ALTER COLUMN id TYPE uuid "
                "USING gen_random_uuid()"
            )

    # Add columns that older schemas are missing.
    for name, column_type, nullable in COLUMNS:
        if name not in columns:
            if not nullable:
                row_count = bind.execute(sa.text("SELECT COUNT(*) FROM complaints")).scalar_one()
                if row_count:
                    raise RuntimeError(
                        f"Cannot add required column '{name}' to complaints while rows exist. "
                        "Backfill the column first."
                    )
            op.add_column(
                "complaints",
                sa.Column(name, column_type, nullable=nullable),
            )

    # Keep the model's defaults explicit at the database level for migrations.
    op.execute(
        "ALTER TABLE complaints ALTER COLUMN status SET DEFAULT 'committed'"
    )
    op.execute(
        "ALTER TABLE complaints ALTER COLUMN created_at SET DEFAULT CURRENT_TIMESTAMP"
    )
    op.execute(
        "ALTER TABLE complaints ALTER COLUMN committed_at SET DEFAULT CURRENT_TIMESTAMP"
    )


def downgrade() -> None:
    # This is a baseline migration. Do not drop the production complaints table
    # automatically during a downgrade.
    pass
