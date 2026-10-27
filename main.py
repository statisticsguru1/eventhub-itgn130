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


def _event_view(state: dict, event: dict) -> dict:
    """Build a fresh display record without exposing the internal waiting queue."""
    counts = bookings.event_counts(state, event["event_id"])
    return {
        "event_id": event["event_id"],
        "title": event["title"],
        "date": event["date"],
        "venue": event["venue"],
        "capacity": event["capacity"],
        "status": event["status"],
        "confirmed_count": counts["confirmed_count"],
        "waiting_count": counts["waiting_count"],
    }


def list_events_view(state: dict) -> list[dict]:
    """Return ordered display records from a completed valid application state."""
    return [_event_view(state, event) for event in events.list_events(state)]


def search_events_by_keyword_view(state: dict, query: str) -> list[dict]:
    """Enrich domain keyword matches without changing their matching or order."""
    return [
        _event_view(state, event) for event in events.search_by_keyword(state, query)
    ]


def search_events_by_date_view(state: dict, date: str) -> list[dict]:
    """Enrich domain date matches, propagating domain validation errors."""
    return [_event_view(state, event) for event in events.search_by_date(state, date)]


def summary_report(state: dict) -> dict:
    """Derive totals and positive active leaders from completed valid state."""
    ordered_events = events.list_events(state)
    report = {
        "total_events": len(ordered_events),
        "active_events": 0,
        "cancelled_events": 0,
        "confirmed_registrations": 0,
        "waiting_registrations": 0,
        "available_seats": 0,
        "most_registered_events": [],
    }
    max_confirmed = 0
    for event in ordered_events:
        if event["status"] == "cancelled":
            report["cancelled_events"] += 1
            continue
        report["active_events"] += 1
        counts = bookings.event_counts(state, event["event_id"])
        confirmed = counts["confirmed_count"]
        report["confirmed_registrations"] += confirmed
        report["waiting_registrations"] += counts["waiting_count"]
        report["available_seats"] += event["capacity"] - confirmed
        leader = {
            "event_id": event["event_id"],
            "title": event["title"],
            "confirmed_count": confirmed,
        }
        if confirmed > max_confirmed:
            max_confirmed = confirmed
            report["most_registered_events"] = [leader]
        elif confirmed == max_confirmed and confirmed > 0:
            report["most_registered_events"].append(leader)
    return report
