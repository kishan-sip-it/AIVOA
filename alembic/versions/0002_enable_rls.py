"""Enable Row Level Security on the application table.

The AIVOA backend connects directly to PostgreSQL, so application requests do
not rely on Supabase's browser Data API for database access. Enabling RLS with
no anon/authenticated policies therefore blocks accidental public table access
while preserving the backend's privileged database connection.
"""

from alembic import op

revision = "0002_enable_rls"
down_revision = "0001_baseline_complaints"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # No permissive policies are created intentionally. The backend talks to
    # PostgreSQL directly, while Supabase's anon/authenticated Data API roles
    # should not be able to read or mutate complaint records.
    op.execute("ALTER TABLE public.complaints ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    # Restoring disabled RLS would re-introduce the Supabase security advisory.
    # Keep the downgrade explicit rather than silently weakening the database.
    op.execute("ALTER TABLE public.complaints DISABLE ROW LEVEL SECURITY")
