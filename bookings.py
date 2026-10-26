"""Booking-domain operations on caller-owned candidates, without persistence.

Registration/cancellation expect completed valid state. Promotion also accepts a
capacity-increase intermediate; cleanup accepts status-only event cancellation.
Expected input/queue errors raise ValueError; unknown identifiers raise KeyError.
"""

from copy import deepcopy
import uuid

import events


def _text(value: str, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a nonempty string.")
    return value.strip()


def _event_reference(state: dict, event_id: str) -> dict:
    # get_event enforces exact ID semantics, but returns a copy, not a live queue.
    events.get_event(state, event_id)
    return state["events"][event_id]


def _active_event(state: dict, event_id: str) -> dict:
    event = _event_reference(state, event_id)
    if event["status"] != "active":
        raise ValueError("This booking operation requires an active event.")
    return event


def _booking_reference(state: dict, booking_id: str) -> dict:
    _text(booking_id, "Booking ID")
    if booking_id not in state["bookings"]:
        raise KeyError(f"Unknown booking ID: {booking_id}")
    return state["bookings"][booking_id]


def _checked_queue(state: dict, event_id: str) -> list[str]:
    """Preflight the affected queue and its complete waiting membership."""
    queue = state["events"][event_id]["waiting_list"]
    if not isinstance(queue, list):
        raise ValueError("Waiting queue must be a list.")
    seen = set()
    for booking_id in queue:
        _text(booking_id, "Waiting-list booking ID")
        if booking_id in seen:
            raise ValueError("Waiting queue contains duplicate IDs.")
        seen.add(booking_id)
        booking = state["bookings"].get(booking_id)
        if (
            not isinstance(booking, dict)
            or booking.get("booking_id") != booking_id
            or booking.get("event_id") != event_id
            or booking.get("status") != "waiting"
        ):
            raise ValueError("Waiting queue references an invalid waiting booking.")
    waiting_ids = {
        booking_id
        for booking_id, booking in state["bookings"].items()
        if booking["event_id"] == event_id and booking["status"] == "waiting"
    }
    if seen != waiting_ids:
        raise ValueError("Waiting bookings and queue membership disagree.")
    return queue.copy()


def get_booking(state: dict, booking_id: str) -> dict:
    """Return an independent copy using exact, unnormalized booking-ID lookup."""
    return deepcopy(_booking_reference(state, booking_id))


def find_registration(state: dict, event_id: str, student_id: str) -> dict:
    """Resolve event/student identity without exposing a live booking record."""
    _event_reference(state, event_id)
    student_id = _text(student_id, "Student ID")
    for booking in state["bookings"].values():
        if booking["event_id"] == event_id and booking["student_id"] == student_id:
            return deepcopy(booking)
    raise KeyError(f"No registration for student {student_id} at event {event_id}.")


def event_counts(state: dict, event_id: str) -> dict:
    """Count actual records, including a status-only cancellation intermediate."""
    _event_reference(state, event_id)
    confirmed = 0
    waiting = 0
    for booking in state["bookings"].values():
        if booking["event_id"] == event_id:
            if booking["status"] == "confirmed":
                confirmed += 1
            elif booking["status"] == "waiting":
                waiting += 1
    return {"confirmed_count": confirmed, "waiting_count": waiting}


def register_participant(
    candidate: dict, event_id: str, student_id: str, student_name: str
) -> dict:
    """Confirm or append FIFO, rejecting duplicates and unresolved vacancies."""
    student_id = _text(student_id, "Student ID")
    student_name = _text(student_name, "Student name")
    event = _active_event(candidate, event_id)
    queue = _checked_queue(candidate, event_id)
    for booking in candidate["bookings"].values():
        if booking["event_id"] == event_id and booking["student_id"] == student_id:
            raise ValueError("Student already has a registration for this event.")
    confirmed = event_counts(candidate, event_id)["confirmed_count"]
    if confirmed > event["capacity"]:
        raise ValueError("Confirmed attendance exceeds capacity.")
    if queue and confirmed < event["capacity"]:
        raise ValueError("Fill available seats before registering a newcomer.")
    booking_id = str(uuid.uuid4())
    if booking_id in candidate["bookings"]:
        raise ValueError(f"Generated booking ID already exists: {booking_id}")
    status = "confirmed" if confirmed < event["capacity"] else "waiting"
    booking = {
        "booking_id": booking_id,
        "event_id": event_id,
        "student_id": student_id,
        "student_name": student_name,
        "status": status,
    }
    if status == "waiting":
        queue.append(booking_id)
    result = deepcopy(booking)
    candidate["bookings"][booking_id] = booking
    if status == "waiting":
        event["waiting_list"] = queue
    return result


def fill_available_seats(candidate: dict, event_id: str) -> list[str]:
    """Complete a capacity increase by confirming the fitting FIFO prefix."""
    event = _active_event(candidate, event_id)
    queue = _checked_queue(candidate, event_id)
    available = event["capacity"] - event_counts(candidate, event_id)["confirmed_count"]
    if available <= 0 or not queue:
        return []
    promoted = queue[:available]
    remaining = queue[len(promoted) :]
    for booking_id in promoted:
        candidate["bookings"][booking_id]["status"] = "confirmed"
    event["waiting_list"] = remaining
    return promoted


def cancel_registration(candidate: dict, booking_id: str) -> dict:
    """Delete one current registration; confirmed cancellation promotes one head."""
    booking = _booking_reference(candidate, booking_id)
    event_id = booking["event_id"]
    event = _active_event(candidate, event_id)
    if booking["status"] not in ("confirmed", "waiting"):
        raise ValueError("Registration has an invalid booking status.")
    queue = _checked_queue(candidate, event_id)
    confirmed = event_counts(candidate, event_id)["confirmed_count"]
    if confirmed > event["capacity"] or (queue and confirmed < event["capacity"]):
        raise ValueError("Complete the earlier capacity operation before cancellation.")
    promoted = []
    if booking["status"] == "waiting":
        queue.remove(booking_id)
    elif queue:
        promoted = queue[:1]
        queue = queue[1:]
    result = {"cancelled_booking_id": booking_id, "promoted_booking_ids": promoted}
    del candidate["bookings"][booking_id]
    for promoted_id in promoted:
        candidate["bookings"][promoted_id]["status"] = "confirmed"
    event["waiting_list"] = queue
    return result


def remove_event_registrations(candidate: dict, event_id: str) -> list[str]:
    """Complete event cancellation, deleting bookings without any promotion."""
    event = _event_reference(candidate, event_id)
    if event["status"] != "cancelled":
        raise ValueError("Only cancelled events may have all registrations removed.")
    _checked_queue(candidate, event_id)
    removed = [
        booking_id
        for booking_id, booking in candidate["bookings"].items()
        if booking["event_id"] == event_id
    ]
    for booking_id in removed:
        _text(booking_id, "Booking ID")
    removed.sort()
    for booking_id in removed:
        del candidate["bookings"][booking_id]
    event["waiting_list"] = []
    return removed
