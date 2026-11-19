from datetime import datetime, timezone


def utcnow() -> datetime:
    """Naive UTC 'now' (all DateTime columns store naive UTC)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def iso_utc(dt: datetime | None) -> str | None:
    """Serialise a naive-UTC datetime unambiguously (…Z) so browsers do not read it as local time."""
    if dt is None:
        return None
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt.isoformat(timespec="seconds") + "Z"
