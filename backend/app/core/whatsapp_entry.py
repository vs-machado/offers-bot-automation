"""Persist validated entry snapshots shared by the monitor and public redirects."""

import re
from datetime import datetime, timedelta, timezone

INVITE_PATTERN = re.compile(r"https://chat\.whatsapp\.com/[A-Za-z0-9]{20,32}\Z")
INVITE_TTL_SECONDS = 180


def clear_entry(row):
    """Withdraw admission without changing offer publishing or active-group identity."""
    row.invite_url = None
    row.invite_expires_at = None


def set_entry(row, invite):
    """Publish a validated invite and expire it from refresh time, not observation age."""
    if (
        not isinstance(invite, str)
        or not INVITE_PATTERN.fullmatch(invite)
        or row.observed_at is None
        or row.member_count is None
        or row.observed_entry_limit is None
        or row.member_count >= row.observed_entry_limit
    ):
        raise ValueError("A verified invite and vacancy observation are required")
    row.invite_url = invite
    row.invite_expires_at = datetime.now(timezone.utc) + timedelta(
        seconds=INVITE_TTL_SECONDS
    )
