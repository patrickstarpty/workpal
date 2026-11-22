"""Go RFC3339 second precision with offset preservation and explicit null policy."""
from datetime import datetime, timezone


def format_timestamp(value, *, invalid=""):
    if value is None:
        return invalid
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace('Z', '+00:00'))
    elif isinstance(value, (int, float)):
        value = datetime.fromtimestamp(value, timezone.utc)
    offset = value.utcoffset()
    seconds = int(offset.total_seconds()) if offset is not None else 0
    minutes = abs(seconds) // 60 * (-1 if seconds < 0 else 1)
    zone = 'Z' if seconds == 0 else ('+' if minutes >= 0 else '-') + f'{abs(minutes)//60:02d}:{abs(minutes)%60:02d}'
    return f'{value.year:04d}-{value.month:02d}-{value.day:02d}T{value.hour:02d}:{value.minute:02d}:{value.second:02d}' + zone

