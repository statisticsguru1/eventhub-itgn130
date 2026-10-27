"""Event-only validation, candidate mutations, and independent read snapshots.

No function persists state or changes bookings. Application orchestration must
complete promotion/cleanup before validating and saving cross-module operations.
"""

from copy import deepcopy
from datetime import date as calendar_date
import re
import uuid


_EVENT_FIELDS = {
    "event_id",
    "title",
    "date",
    "venue",
    "capacity",
    "status",
    "waiting_list",
}
_EDITABLE_FIELDS = {"title", "date", "venue", "capacity"}


def _nonempty_text(value: str, label: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a nonempty string.")


def _validate_date(value: str) -> None:
    if not isinstance(value, str) or not re.fullmatch(
        r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value
    ):
        raise ValueError("Date must use canonical YYYY-MM-DD.")
    try:
        calendar_date.fromisoformat(value)
    except ValueError as error:
        raise ValueError("Date must be a real calendar date.") from error


def validate_event(fields: dict) -> None:
    """Validate a complete event without mutation or booking-reference checks."""
    if not isinstance(fields, dict) or set(fields) != _EVENT_FIELDS:
        raise ValueError("Event must contain exactly the required event fields.")
    _nonempty_text(fields["event_id"], "Event ID")
    for name in ("title", "venue"):
        _nonempty_text(fields[name], name)
        if fields[name] != fields[name].strip():
            raise ValueError(f"{name} must not have surrounding whitespace.")
    _validate_date(fields["date"])
    if type(fields["capacity"]) is not int or fields["capacity"] <= 0:
        raise ValueError("Capacity must be a positive integer, excluding bool.")
    if fields["status"] not in ("active", "cancelled"):
        raise ValueError("Event status must be active or cancelled.")
    queue = fields["waiting_list"]
    if not isinstance(queue, list):
        raise ValueError("waiting_list must be a list of booking IDs.")
    for booking_id in queue:
        _nonempty_text(booking_id, "Waiting-list booking ID")
    if len(set(queue)) != len(queue):
        raise ValueError("Waiting-list booking IDs must be unique.")


def _event_reference(state: dict, event_id: str) -> dict:
    """Internal live reference; public readers always copy this record."""
    _nonempty_text(event_id, "Event ID")
    if event_id not in state["events"]:
        raise KeyError(f"Unknown event ID: {event_id}")
    return state["events"][event_id]


def create_event(
    candidate: dict, title: str, date: str, venue: str, capacity: int
) -> dict:
    """Insert one fully validated active event and return an independent copy."""
    _nonempty_text(title, "Title")
    _nonempty_text(venue, "Venue")
    event_id = str(uuid.uuid4())
    event = {
        "event_id": event_id,
        "title": title.strip(),
        "date": date,
        "venue": venue.strip(),
        "capacity": capacity,
        "status": "active",
        "waiting_list": [],
    }
    validate_event(event)
    if event_id in candidate["events"]:
        raise ValueError(f"Generated event ID already exists: {event_id}")
    candidate["events"][event_id] = event
    return deepcopy(event)


def get_event(state: dict, event_id: str) -> dict:
    """Return an independent event copy; preserve the exact lookup ID."""
    return deepcopy(_event_reference(state, event_id))


def list_events(state: dict) -> list[dict]:
    """Include cancelled events and order by date, then event ID."""
    return [
        deepcopy(event)
        for event in sorted(
            state["events"].values(),
            key=lambda event: (event["date"], event["event_id"]),
        )
    ]


def update_event(
    candidate: dict,
    event_id: str,
    changes: dict,
    *,
    confirmed_count: int | None = None,
) -> None:
    """Apply a validated event-level edit to a caller-owned candidate.

    Capacity edits require a count supplied by booking-aware orchestration. Any
    non-None count, even for another edit, must be an integer in [0, old capacity].
    This helper never promotes students. Main must complete promotions and obtain
    the final event snapshot before persistence; no intermediate copy is returned.
    """
    event = _event_reference(candidate, event_id)
    if event["status"] == "cancelled":
        raise ValueError("Cancelled events cannot be edited.")
    if not isinstance(changes, dict) or not set(changes) <= _EDITABLE_FIELDS:
        raise ValueError("Only title, date, venue, and capacity may be edited.")
    if "capacity" in changes and confirmed_count is None:
        raise ValueError("Capacity edits require confirmed_count.")
    if confirmed_count is not None:
        if (
            type(confirmed_count) is not int
            or not 0 <= confirmed_count <= event["capacity"]
        ):
            raise ValueError(
                "confirmed_count must be an integer from 0 to current capacity."
            )
    proposed = event.copy()
    for field, value in changes.items():
        if field in ("title", "venue"):
            _nonempty_text(value, field)
            value = value.strip()
        proposed[field] = value
    validate_event(proposed)
    if confirmed_count is not None and proposed["capacity"] < confirmed_count:
        raise ValueError("Capacity cannot be reduced below confirmed attendance.")
    event.update(proposed)


def cancel_event(candidate: dict, event_id: str) -> bool:
    """Change status only; orchestration completes booking cleanup before saving."""
    event = _event_reference(candidate, event_id)
    if event["status"] == "cancelled":
        return False
    event["status"] = "cancelled"
    return True


def search_by_keyword(state: dict, query: str) -> list[dict]:
    """Return ordered independent matches, without booking-derived counts."""
    if not isinstance(query, str):
        raise ValueError("Search keyword must be a string.")
    keyword = query.strip().casefold()
    return [
        event
        for event in list_events(state)
        if keyword in event["title"].casefold() or keyword in event["venue"].casefold()
    ]


def search_by_date(state: dict, date: str) -> list[dict]:
    """Match an exact valid date, including past dates and cancelled events."""
    _validate_date(date)
    return [event for event in list_events(state) if event["date"] == date]
