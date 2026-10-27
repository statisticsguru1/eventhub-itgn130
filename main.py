"""Application operations, read views, startup, and a thin interactive console.

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


def _show_error(error: ValueError | KeyError | OSError) -> None:
    """Display expected errors without KeyError's extra quotation marks."""
    message = (
        error.args[0] if isinstance(error, KeyError) and error.args else str(error)
    )
    if isinstance(error, ValueError) and message.startswith(
        "Generated booking ID already exists: "
    ):
        message = "Could not allocate a unique registration ID. Please try again."
    print(f"Error: {message}")


def _read_capacity(prompt: str) -> int:
    value = input(prompt)
    try:
        return int(value)
    except ValueError as error:
        raise ValueError("Capacity must be a whole number.") from error


def _prompt_event_changes(event: dict) -> dict:
    """Collect only supplied fields; Enter alone means keep the current value."""
    print(f"ID: {event['event_id']}")
    print(f"Title: {event['title']}")
    print(f"Date: {event['date']} | Venue: {event['venue']}")
    print(f"Capacity: {event['capacity']} | Status: {event['status']}")
    changes = {}
    for field, prompt in [
        ("title", f"Title [{event['title']}] (Enter to keep): "),
        ("date", f"Date [{event['date']}] (YYYY-MM-DD; Enter to keep): "),
        ("venue", f"Venue [{event['venue']}] (Enter to keep): "),
        ("capacity", f"Capacity [{event['capacity']}] (Enter to keep): "),
    ]:
        value = input(prompt)
        if value == "":
            continue
        if field == "capacity":
            try:
                value = int(value)
            except ValueError as error:
                raise ValueError("Capacity must be a whole number.") from error
        changes[field] = value
    return changes


def _display_events(records: list[dict]) -> None:
    if not records:
        print("No events found.")
        return
    for event in records:
        print(f"\nID: {event['event_id']}")
        print(f"Title: {event['title']}")
        print(f"Date: {event['date']} | Venue: {event['venue']}")
        print(f"Capacity: {event['capacity']} | Status: {event['status']}")
        print(
            f"Confirmed: {event['confirmed_count']} | Waiting: {event['waiting_count']}"
        )


def _display_report(report: dict) -> None:
    print("\nSUMMARY REPORT\n")
    print(f"Total events: {report['total_events']}")
    print(f"Active events: {report['active_events']}")
    print(f"Cancelled events: {report['cancelled_events']}")
    print(f"Confirmed registrations: {report['confirmed_registrations']}")
    print(f"Waiting registrations: {report['waiting_registrations']}")
    print(f"Available seats: {report['available_seats']}")
    print("\nMost registered event(s):")
    if not report["most_registered_events"]:
        print("No confirmed registrations.")
    for leader in report["most_registered_events"]:
        print(
            f"{leader['event_id']} — {leader['title']} — "
            f"{leader['confirmed_count']} confirmed"
        )


def _search_menu(state: dict) -> None:
    while True:
        print("\nSEARCH EVENTS\n\n1. Search by keyword\n2. Search by date\n3. Back")
        choice = input("Choice: ").strip()
        if choice == "3":
            return
        try:
            if choice == "1":
                records = search_events_by_keyword_view(
                    state, input("Keyword (Enter for all events): ")
                )
            elif choice == "2":
                records = search_events_by_date_view(
                    state, input("Date (YYYY-MM-DD): ")
                )
            else:
                print("Invalid choice. Please select 1–3.")
                continue
        except (ValueError, KeyError, OSError) as error:
            _show_error(error)
            continue
        _display_events(records)


def run_menu(state: dict, data_dir: Path) -> None:
    """Own the active binding; adopt committed state before success display."""
    while True:
        print(
            "\nEVENTHUB — EVENT REGISTRATION & BOOKING MANAGEMENT\n\n"
            "1. Add event\n2. Edit event\n3. List events\n4. Search events\n"
            "5. Cancel event\n6. Register participant\n7. Cancel registration\n"
            "8. View summary report\n9. Exit"
        )
        choice = input("Choice: ").strip()
        if choice == "9":
            print("Goodbye.")
            return
        if choice == "4":
            _search_menu(state)
            continue
        # Expected-error handling covers input/domain/storage work. Success
        # formatting below is separate so a display error cannot imply save failure.
        try:
            if choice == "1":
                title = input("Title: ")
                date = input("Date (YYYY-MM-DD): ")
                venue = input("Venue: ")
                capacity = _read_capacity("Capacity: ")
                new_state, result = create_event_operation(
                    state, data_dir, title, date, venue, capacity
                )
                state = new_state
            elif choice == "2":
                event_id = input("Event ID: ")
                event = events.get_event(state, event_id)
                changes = _prompt_event_changes(event)
                new_state, result = update_event_operation(
                    state, data_dir, event_id, changes
                )
                state = new_state
            elif choice == "3":
                records = list_events_view(state)
            elif choice == "5":
                event_id = input("Event ID: ")
                new_state, result = cancel_event_operation(state, data_dir, event_id)
                state = new_state
            elif choice == "6":
                event_id = input("Event ID: ")
                student_id = input("Student ID: ")
                student_name = input("Student name: ")
                new_state, result = register_participant_operation(
                    state, data_dir, event_id, student_id, student_name
                )
                state = new_state
            elif choice == "7":
                event_id = input("Event ID: ")
                student_id = input("Student ID: ")
                new_state, result = cancel_registration_operation(
                    state, data_dir, event_id, student_id
                )
                state = new_state
            elif choice == "8":
                report = summary_report(state)
            else:
                print("Invalid choice. Please select 1–9.")
                continue
        except (ValueError, KeyError, OSError) as error:
            _show_error(error)
            continue

        if choice == "1":
            event = result["event"]
            print(f"Event created: {event['event_id']} — {event['title']}")
        elif choice == "2":
            if result["changed"]:
                print(f"Event updated: {result['event']['event_id']}.")
            else:
                print("No changes made.")
            if result["promoted_booking_ids"]:
                print(
                    f"Promoted from waiting list: {len(result['promoted_booking_ids'])}"
                )
        elif choice == "3":
            _display_events(records)
        elif choice == "5":
            if result["changed"]:
                print(
                    f"Event cancelled. Removed {len(result['removed_booking_ids'])} "
                    "registration(s)."
                )
            else:
                print("Event is already cancelled. No changes made.")
        elif choice == "6":
            booking = result["booking"]
            label = (
                "Registration confirmed for"
                if booking["status"] == "confirmed"
                else "Added to waiting list:"
            )
            print(f"{label} {booking['student_id']} — {booking['student_name']}.")
        elif choice == "7":
            booking = result["cancelled_booking"]
            print(
                f"Registration cancelled for {booking['student_id']} — "
                f"{booking['student_name']}."
            )
            for promoted in result["promoted_bookings"]:
                print(
                    f"Promoted from waiting list: {promoted['student_id']} — "
                    f"{promoted['student_name']}."
                )
        elif choice == "8":
            _display_report(report)


def main() -> None:
    """Load once, stop on unsafe startup, and terminate closed input gracefully."""
    try:
        missing = not (DEFAULT_DATA_DIR / "eventhub.json").exists()
        state = storage.load_state(DEFAULT_DATA_DIR)
    except (ValueError, OSError) as error:
        print(f"Unable to start EventHub: {error}")
        return
    if missing:
        print("No saved data found. Starting with an empty dataset.")
    try:
        run_menu(state, DEFAULT_DATA_DIR)
    except (EOFError, KeyboardInterrupt):
        print("\nSession ended.")


if __name__ == "__main__":
    main()
