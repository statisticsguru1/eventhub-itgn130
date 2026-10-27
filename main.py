"""Complete candidate-state operations; startup and the console menu come later.

Callers adopt the returned state only after an operation returns successfully.
Domain and storage errors propagate without changing the caller's input state.
"""

from copy import deepcopy
from pathlib import Path

import bookings
import events
import storage


DEFAULT_DATA_DIR = Path(__file__).resolve().parent / "data"


def create_event_operation(
    state: dict,
    data_dir: Path,
    title: str,
    date: str,
    venue: str,
    capacity: int,
) -> tuple[dict, dict]:
    """Create and persist an event, returning its independent snapshot."""
    candidate = deepcopy(state)
    event = events.create_event(candidate, title, date, venue, capacity)
    result = {"event": event}
    storage.save_state(candidate, data_dir)
    return candidate, result


def update_event_operation(
    state: dict, data_dir: Path, event_id: str, changes: dict
) -> tuple[dict, dict]:
    """Complete edits and capacity promotions before saving; skip valid no-ops."""
    candidate = deepcopy(state)
    original = events.get_event(candidate, event_id)
    if not isinstance(changes, dict):
        raise ValueError("Event changes must be a dictionary.")
    promoted = []
    if "capacity" in changes:
        counts = bookings.event_counts(candidate, event_id)
        events.update_event(
            candidate, event_id, changes, confirmed_count=counts["confirmed_count"]
        )
        promoted = bookings.fill_available_seats(candidate, event_id)
    else:
        events.update_event(candidate, event_id, changes)
    event = events.get_event(candidate, event_id)
    changed = event != original or bool(promoted)
    result = {
        "changed": changed,
        "event": event,
        "promoted_booking_ids": promoted,
    }
    if not changed:
        return state, result
    storage.save_state(candidate, data_dir)
    return candidate, result


def cancel_event_operation(
    state: dict, data_dir: Path, event_id: str
) -> tuple[dict, dict]:
    """Cancel status, then remove registrations; repeated cancellation is a no-op."""
    candidate = deepcopy(state)
    changed = events.cancel_event(candidate, event_id)
    removed = []
    if changed:
        removed = bookings.remove_event_registrations(candidate, event_id)
    result = {
        "changed": changed,
        "event": events.get_event(candidate, event_id),
        "removed_booking_ids": removed,
    }
    if not changed:
        return state, result
    storage.save_state(candidate, data_dir)
    return candidate, result


def register_participant_operation(
    state: dict,
    data_dir: Path,
    event_id: str,
    student_id: str,
    student_name: str,
) -> tuple[dict, dict]:
    """Persist a confirmed or waiting registration and return its snapshot."""
    candidate = deepcopy(state)
    booking = bookings.register_participant(
        candidate, event_id, student_id, student_name
    )
    result = {"booking": booking}
    storage.save_state(candidate, data_dir)
    return candidate, result


def cancel_registration_operation(
    state: dict, data_dir: Path, event_id: str, student_id: str
) -> tuple[dict, dict]:
    """Resolve the student on the candidate and persist cancellation/promotion."""
    candidate = deepcopy(state)
    cancelled = bookings.find_registration(candidate, event_id, student_id)
    cancellation = bookings.cancel_registration(candidate, cancelled["booking_id"])
    promoted = [
        bookings.get_booking(candidate, booking_id)
        for booking_id in cancellation["promoted_booking_ids"]
    ]
    result = {"cancelled_booking": cancelled, "promoted_bookings": promoted}
    storage.save_state(candidate, data_dir)
    return candidate, result
