"""Encrypt existing user credentials using external application keys."""

from alembic import op

from backend.app.core.db.credential_rotation import reencrypt_configs

revision = "0011_encrypt_user_configs"
down_revision = "0010_whatsapp_delivery_policy"
branch_labels = None
depends_on = None


def upgrade():
    """Encrypt all existing configuration rows in the migration transaction."""
    reencrypt_configs(op.get_bind())


def downgrade():
    """Keep ciphertext on downgrade so rollback cannot expose stored credentials."""
    pass
