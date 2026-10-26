"""Validate and persist EventHub's single authoritative JSON snapshot.

Expected invalid data raises ValueError; filesystem failures raise OSError.
Callers adopt a candidate only after save_state returns successfully. One local
writer is supported; replacement does not promise durability against power loss.
"""

from datetime import date
import json
import logging
import os
from pathlib import Path
import re
import tempfile


ROOT_FIELDS = {"schema_version", "events", "bookings"}
EVENT_FIELDS = {
    "event_id",
    "title",
    "date",
    "venue",
    "capacity",
    "status",
    "waiting_list",
}
BOOKING_FIELDS = {"booking_id", "event_id", "student_id", "student_name", "status"}


def empty_state() -> dict:
    """Return a fresh state; never share mutable containers between calls."""
    return {"schema_version": 1, "events": {}, "bookings": {}}


def _fields(record: dict, expected: set, label: str) -> None:
    if not isinstance(record, dict) or set(record) != expected:
        raise ValueError(
            f"{label} must contain exactly: {', '.join(sorted(expected))}."
        )


def _text(value: str, label: str, trimmed: bool = False) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a nonempty string.")
    if trimmed and value != value.strip():
        raise ValueError(f"{label} must not have surrounding whitespace.")


def validate_state(state: dict) -> None:
    """Reject invalid schema or domain invariants without modifying state."""
    _fields(state, ROOT_FIELDS, "State")
    if type(state["schema_version"]) is not int or state["schema_version"] != 1:
        raise ValueError("Unsupported schema_version; expected integer 1.")
    events, bookings = state["events"], state["bookings"]
    if not isinstance(events, dict) or not isinstance(bookings, dict):
        raise ValueError("events and bookings must be dictionaries.")

    for event_id, event in events.items():
        _text(event_id, "Event dictionary ID")
        _fields(event, EVENT_FIELDS, f"Event {event_id}")
        if event["event_id"] != event_id:
            raise ValueError(f"Event {event_id} has a mismatched embedded ID.")
        for field in ("title", "venue"):
            _text(event[field], f"Event {event_id} {field}", trimmed=True)
        value = event["date"]
        if not isinstance(value, str) or not re.fullmatch(
            r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value
        ):
            raise ValueError(f"Event {event_id} date must use YYYY-MM-DD.")
        try:
            date.fromisoformat(value)
        except ValueError as error:
            raise ValueError(
                f"Event {event_id} has an impossible calendar date."
            ) from error
        if type(event["capacity"]) is not int or event["capacity"] <= 0:
            raise ValueError(f"Event {event_id} capacity must be a positive integer.")
        if event["status"] not in ("active", "cancelled"):
            raise ValueError(f"Event {event_id} has an invalid status.")
        queue = event["waiting_list"]
        if not isinstance(queue, list):
            raise ValueError(f"Event {event_id} waiting_list must be a list.")
        for booking_id in queue:
            _text(booking_id, f"Event {event_id} waiting-list ID")
        if len(set(queue)) != len(queue):
            raise ValueError(f"Event {event_id} has duplicate waiting-list entries.")

    identities = set()
    confirmed = {event_id: 0 for event_id in events}
    waiting = {event_id: set() for event_id in events}
    for booking_id, booking in bookings.items():
        _text(booking_id, "Booking dictionary ID")
        _fields(booking, BOOKING_FIELDS, f"Booking {booking_id}")
        if booking["booking_id"] != booking_id:
            raise ValueError(f"Booking {booking_id} has a mismatched embedded ID.")
        event_id = booking["event_id"]
        _text(event_id, f"Booking {booking_id} event_id")
        if event_id not in events:
            raise ValueError(f"Booking {booking_id} references an unknown event.")
        if events[event_id]["status"] != "active":
            raise ValueError(f"Cancelled event {event_id} cannot have bookings.")
        for field in ("student_id", "student_name"):
            _text(booking[field], f"Booking {booking_id} {field}", trimmed=True)
        identity = (event_id, booking["student_id"])
        if identity in identities:
            raise ValueError(f"Duplicate student ID for event {event_id}.")
        identities.add(identity)
        if booking["status"] == "confirmed":
            confirmed[event_id] += 1
        elif booking["status"] == "waiting":
            waiting[event_id].add(booking_id)
        else:
            raise ValueError(f"Booking {booking_id} has an invalid status.")

    for event_id, event in events.items():
        queue = event["waiting_list"]
        if set(queue) != waiting[event_id]:
            raise ValueError(f"Event {event_id} queue and waiting bookings disagree.")
        if event["status"] == "cancelled" and queue:
            raise ValueError(f"Cancelled event {event_id} cannot have a waiting list.")
        if confirmed[event_id] > event["capacity"]:
            raise ValueError(f"Event {event_id} exceeds capacity.")
        if queue and confirmed[event_id] < event["capacity"]:
            raise ValueError(
                f"Event {event_id} has waiting students and available seats."
            )


def _unique_object(pairs: list) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON object key: {key}.")
        result[key] = value
    return result


def _read_snapshot(path: Path) -> dict:
    with path.open(encoding="utf-8") as stream:
        try:
            state = json.load(stream, object_pairs_hook=_unique_object)
        except RecursionError as error:
            raise ValueError(
                f"Invalid EventHub snapshot {path}: JSON nesting is too deep."
            ) from error
        except (ValueError, UnicodeError) as error:
            raise ValueError(f"Invalid EventHub snapshot {path}: {error}") from error
    validate_state(state)
    return state


def load_state(data_dir: Path) -> dict:
    """Load eventhub.json or initialize first run; never repair damaged data."""
    data_dir = Path(data_dir)
    path = data_dir / "eventhub.json"
    try:
        return _read_snapshot(path)
    except FileNotFoundError:
        # An abandoned first save needs review, not silent empty initialization.
        if any(data_dir.glob("eventhub-*.tmp")):
            raise ValueError(
                "eventhub.json is missing but temporary snapshots exist; "
                "review them before initializing a new dataset."
            ) from None
        return empty_state()


def _cleanup_temporary(path: Path) -> None:
    """Cleanup is optional and cannot change the outcome of a committed save."""
    try:
        path.unlink(missing_ok=True)
    except OSError as error:
        logging.getLogger(__name__).warning(
            "Could not remove temporary snapshot %s: %s", path, error
        )


def save_state(candidate: dict, data_dir: Path) -> None:
    """Validate, write/read back a sibling, then commit with os.replace.

    Pre-commit failures leave the previous authoritative file unchanged.
    No required work follows successful replacement; cleanup errors only log a
    warning. A crash after replacement can commit without acknowledgement.
    """
    validate_state(candidate)
    data_dir = Path(data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=data_dir,
            prefix="eventhub-",
            suffix=".tmp",
            delete=False,
        ) as stream:
            temporary = Path(stream.name)
            try:
                json.dump(
                    candidate, stream, ensure_ascii=False, indent=2, allow_nan=False
                )
            except (TypeError, UnicodeError) as error:
                raise ValueError(f"Cannot serialize EventHub state: {error}") from error
            stream.flush()
        readback = _read_snapshot(temporary)
        if readback != candidate:
            raise ValueError("Temporary snapshot does not match the candidate state.")
        os.replace(temporary, data_dir / "eventhub.json")
    finally:
        if temporary is not None:
            _cleanup_temporary(temporary)
