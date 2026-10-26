"""Booking-only contracts and narrow event/storage boundary integration."""

from copy import deepcopy
from uuid import UUID
from unittest.mock import patch

import pytest

import bookings
import events
import storage


@pytest.fixture(autouse=True)
def deterministic_ids(monkeypatch):
    identifiers = iter(range(1, 100))
    monkeypatch.setattr(bookings.uuid, "uuid4", lambda: UUID(int=next(identifiers)))


@pytest.fixture
def empty():
    return {
        "schema_version": 1,
        "events": {
            key: {
                "event_id": key,
                "title": "Sample Event",
                "date": "2024-02-29",
                "venue": "Room",
                "capacity": 2,
                "status": status,
                "waiting_list": [],
            }
            for key, status in [("e1", "active"), ("e2", "active"), ("e3", "cancelled")]
        },
        "bookings": {},
    }


def add_record(state, booking_id, event_id, student_id, status):
    state["bookings"][booking_id] = {
        "booking_id": booking_id,
        "event_id": event_id,
        "student_id": student_id,
        "student_name": "Sample Student",
        "status": status,
    }


@pytest.fixture
def full(empty):
    empty = deepcopy(empty)
    # Booking-dictionary order deliberately disagrees with FIFO order.
    for key, student, status in [
        ("c1", "001", "confirmed"),
        ("c2", "002", "confirmed"),
        ("w1", "003", "waiting"),
        ("w2", "004", "waiting"),
        ("w3", "005", "waiting"),
    ]:
        add_record(empty, key, "e1", student, status)
    empty["events"]["e1"]["waiting_list"] = ["w2", "w1", "w3"]
    add_record(empty, "other", "e2", "001", "confirmed")
    storage.validate_state(empty)
    return empty


def test_register_confirmed_exact_schema_normalization_and_copy(empty):
    before = deepcopy(empty)
    result = bookings.register_participant(empty, "e1", " 001 ", " Sample Student ")
    assert str(UUID(result["booking_id"])) == result["booking_id"]
    assert result == {
        "booking_id": result["booking_id"],
        "event_id": "e1",
        "student_id": "001",
        "student_name": "Sample Student",
        "status": "confirmed",
    }
    before["bookings"][result["booking_id"]] = deepcopy(result)
    assert empty == before
    result["student_name"] = "Changed"
    assert empty == before
    storage.validate_state(empty)


def test_capacity_boundary_and_fifo_append(empty):
    results = [
        bookings.register_participant(empty, "e1", str(i), "Sample") for i in range(5)
    ]
    assert [record["status"] for record in results] == [
        "confirmed",
        "confirmed",
        "waiting",
        "waiting",
        "waiting",
    ]
    assert empty["events"]["e1"]["waiting_list"] == [
        r["booking_id"] for r in results[2:]
    ]
    storage.validate_state(empty)


def test_identity_preserves_case_and_leading_zeros_and_event_scope(empty):
    records = [
        bookings.register_participant(empty, "e1", sid, "Sample")
        for sid in ["001", "1", "ABC", "abc"]
    ]
    assert [record["student_id"] for record in records] == ["001", "1", "ABC", "abc"]
    other = bookings.register_participant(empty, "e2", "001", "Other Name")
    assert other["status"] == "confirmed"
    storage.validate_state(empty)


@pytest.mark.parametrize("student_id", ["001", " 001 ", "004", " 004 "])
def test_duplicate_confirmed_and_waiting_rejected_atomically(full, student_id):
    before = deepcopy(full)
    with pytest.raises(ValueError, match="already has"):
        bookings.register_participant(full, "e1", student_id, "Another Name")
    assert full == before


@pytest.mark.parametrize("field", ["student_id", "student_name"])
@pytest.mark.parametrize("value", ["", " ", None, 1, True, [], {}])
def test_invalid_participant_fields_leave_state_unchanged(empty, field, value):
    before = deepcopy(empty)
    args = {"student_id": "001", "student_name": "Sample"}
    args[field] = value
    with pytest.raises(ValueError):
        bookings.register_participant(empty, "e1", **args)
    assert empty == before


def test_registration_on_cancelled_event_rejected(empty):
    before = deepcopy(empty)
    with pytest.raises(ValueError, match="active"):
        bookings.register_participant(empty, "e3", "001", "Sample")
    assert empty == before


@pytest.mark.parametrize("event_id", ["missing", " e1 ", "E1"])
def test_unknown_event_for_event_operations(empty, event_id):
    before = deepcopy(empty)
    operations = [
        lambda: bookings.register_participant(empty, event_id, "001", "Sample"),
        lambda: bookings.find_registration(empty, event_id, "001"),
        lambda: bookings.event_counts(empty, event_id),
        lambda: bookings.fill_available_seats(empty, event_id),
        lambda: bookings.remove_event_registrations(empty, event_id),
    ]
    for operation in operations:
        with pytest.raises(KeyError):
            operation()
    assert empty == before


@pytest.mark.parametrize("event_id", ["", " ", None, 1, [], {}])
def test_invalid_event_ids_for_all_event_operations(empty, event_id):
    before = deepcopy(empty)
    for operation in [
        lambda: bookings.register_participant(empty, event_id, "001", "Sample"),
        lambda: bookings.find_registration(empty, event_id, "001"),
        lambda: bookings.event_counts(empty, event_id),
        lambda: bookings.fill_available_seats(empty, event_id),
        lambda: bookings.remove_event_registrations(empty, event_id),
    ]:
        with pytest.raises(ValueError):
            operation()
    assert empty == before


def test_booking_id_collision_does_not_overwrite(full):
    before = deepcopy(full)
    with patch("bookings.uuid.uuid4", return_value="c1") as generate:
        with pytest.raises(ValueError, match="already exists"):
            bookings.register_participant(full, "e1", "new", "Sample")
    generate.assert_called_once()
    assert full == before


def test_newcomer_cannot_bypass_waiters_after_capacity_increase(full):
    events.update_event(full, "e1", {"capacity": 4}, confirmed_count=2)
    before = deepcopy(full)
    with pytest.raises(ValueError, match="Fill available seats"):
        bookings.register_participant(full, "e1", "new", "Sample")
    assert full == before
    assert bookings.fill_available_seats(full, "e1") == ["w2", "w1"]
    result = bookings.register_participant(full, "e1", "new", "Sample")
    assert result["status"] == "waiting"
    assert full["events"]["e1"]["waiting_list"] == ["w3", result["booking_id"]]
    storage.validate_state(full)


def test_get_and_find_return_independent_copies(full):
    before = deepcopy(full)
    for result in [
        bookings.get_booking(full, "c1"),
        bookings.find_registration(full, "e1", " 001 "),
    ]:
        assert result == before["bookings"]["c1"]
        result["student_name"] = "Changed"
    assert full == before
    assert bookings.find_registration(full, "e2", "001")["booking_id"] == "other"


@pytest.mark.parametrize("booking_id", ["", " ", None, 1, [], {}])
def test_malformed_booking_id_for_lookup_and_cancel(full, booking_id):
    before = deepcopy(full)
    for operation in [bookings.get_booking, bookings.cancel_registration]:
        with pytest.raises(ValueError):
            operation(full, booking_id)
    assert full == before


@pytest.mark.parametrize("booking_id", ["missing", " c1 ", "C1"])
def test_unknown_exact_booking_id_for_lookup_and_cancel(full, booking_id):
    before = deepcopy(full)
    for operation in [bookings.get_booking, bookings.cancel_registration]:
        with pytest.raises(KeyError):
            operation(full, booking_id)
    assert full == before


@pytest.mark.parametrize("student_id", ["", " ", None, 1, [], {}])
def test_find_rejects_invalid_student_id(full, student_id):
    with pytest.raises(ValueError):
        bookings.find_registration(full, "e1", student_id)


def test_find_preserves_case_and_zeros(empty):
    for sid in ["001", "1", "ABC", "abc"]:
        record = bookings.register_participant(empty, "e1", sid, "Sample")
        assert bookings.find_registration(empty, "e1", f" {sid} ") == record
    with pytest.raises(KeyError):
        bookings.find_registration(empty, "e1", "Abc")
    with pytest.raises(KeyError):
        bookings.find_registration(empty, "e2", "001")


def test_counts_are_actual_isolated_and_read_only(empty, full):
    before = deepcopy(full)
    assert bookings.event_counts(empty, "e1") == {
        "confirmed_count": 0,
        "waiting_count": 0,
    }
    assert bookings.event_counts(full, "e1") == {
        "confirmed_count": 2,
        "waiting_count": 3,
    }
    assert bookings.event_counts(full, "e2") == {
        "confirmed_count": 1,
        "waiting_count": 0,
    }
    assert bookings.event_counts(full, "e3") == {
        "confirmed_count": 0,
        "waiting_count": 0,
    }
    assert full == before
    events.cancel_event(full, "e1")
    intermediate = deepcopy(full)
    assert bookings.event_counts(full, "e1") == {
        "confirmed_count": 2,
        "waiting_count": 3,
    }
    assert full == intermediate


def test_waiting_only_counts_on_explicit_intermediate(full):
    del full["bookings"]["c1"]
    del full["bookings"]["c2"]
    before = deepcopy(full)
    assert bookings.event_counts(full, "e1") == {
        "confirmed_count": 0,
        "waiting_count": 3,
    }
    assert full == before


def test_confirmed_cancellation_without_waiters(empty):
    record = bookings.register_participant(empty, "e1", "001", "Sample")
    before = deepcopy(empty)
    result = bookings.cancel_registration(empty, record["booking_id"])
    assert result == {
        "cancelled_booking_id": record["booking_id"],
        "promoted_booking_ids": [],
    }
    del before["bookings"][record["booking_id"]]
    assert empty == before
    storage.validate_state(empty)


def test_confirmed_cancellation_promotes_exactly_first_waiter(full):
    before = deepcopy(full)
    result = bookings.cancel_registration(full, "c1")
    assert result == {"cancelled_booking_id": "c1", "promoted_booking_ids": ["w2"]}
    del before["bookings"]["c1"]
    before["bookings"]["w2"]["status"] = "confirmed"
    before["events"]["e1"]["waiting_list"] = ["w1", "w3"]
    assert full == before
    assert (
        bookings.get_booking(full, result["promoted_booking_ids"][0])["student_id"]
        == "004"
    )
    storage.validate_state(full)


@pytest.mark.parametrize(
    "booking_id,remaining",
    [("w2", ["w1", "w3"]), ("w1", ["w2", "w3"]), ("w3", ["w2", "w1"])],
)
def test_waiting_cancellation_preserves_relative_order_without_promotion(
    full, booking_id, remaining
):
    before = deepcopy(full)
    assert bookings.cancel_registration(full, booking_id) == {
        "cancelled_booking_id": booking_id,
        "promoted_booking_ids": [],
    }
    del before["bookings"][booking_id]
    before["events"]["e1"]["waiting_list"] = remaining
    assert full == before
    storage.validate_state(full)


def test_removed_registration_cannot_be_cancelled_twice_and_can_reregister(full):
    bookings.cancel_registration(full, "w1")
    before = deepcopy(full)
    with pytest.raises(KeyError):
        bookings.cancel_registration(full, "w1")
    assert full == before
    record = bookings.register_participant(full, "e1", "003", "Sample Again")
    assert record["status"] == "waiting"
    assert full["events"]["e1"]["waiting_list"][-1] == record["booking_id"]
    storage.validate_state(full)


@pytest.mark.parametrize(
    "capacity,promoted,remaining",
    [
        (2, [], ["w2", "w1", "w3"]),
        (3, ["w2"], ["w1", "w3"]),
        (4, ["w2", "w1"], ["w3"]),
        (8, ["w2", "w1", "w3"], []),
    ],
)
def test_fill_available_seats_fifo_prefix_and_scope(
    full, capacity, promoted, remaining
):
    count = bookings.event_counts(full, "e1")["confirmed_count"]
    events.update_event(full, "e1", {"capacity": capacity}, confirmed_count=count)
    before = deepcopy(full)
    assert bookings.fill_available_seats(full, "e1") == promoted
    before["events"]["e1"]["waiting_list"] = remaining
    for booking_id in promoted:
        before["bookings"][booking_id]["status"] = "confirmed"
    assert full == before
    storage.validate_state(full)


def test_fill_empty_queue_is_noop(empty):
    before = deepcopy(empty)
    assert bookings.fill_available_seats(empty, "e1") == []
    assert empty == before


def test_promotion_on_cancelled_event_rejected(full):
    events.cancel_event(full, "e1")
    before = deepcopy(full)
    with pytest.raises(ValueError, match="active"):
        bookings.fill_available_seats(full, "e1")
    assert full == before


@pytest.mark.parametrize(
    "corruption",
    [
        "not-list",
        "nonstring",
        "blank",
        "duplicate",
        "missing",
        "wrong-event",
        "confirmed-entry",
        "missing-member",
        "embedded-id",
        "invalid-record",
    ],
)
@pytest.mark.parametrize(
    "operation",
    ["register", "confirmed-cancel", "waiting-cancel", "promote", "cleanup"],
)
def test_queue_preflight_failure_is_atomic(full, corruption, operation):
    queue = full["events"]["e1"]["waiting_list"]
    if corruption == "not-list":
        full["events"]["e1"]["waiting_list"] = "w2"
    elif corruption == "nonstring":
        queue[1] = []
    elif corruption == "blank":
        queue[1] = " "
    elif corruption == "duplicate":
        queue[1] = "w2"
    elif corruption == "missing":
        del full["bookings"]["w1"]
    elif corruption == "wrong-event":
        full["bookings"]["w1"]["event_id"] = "e2"
    elif corruption == "confirmed-entry":
        full["bookings"]["w1"]["status"] = "confirmed"
    elif corruption == "missing-member":
        queue.remove("w1")
    elif corruption == "embedded-id":
        full["bookings"]["w1"]["booking_id"] = "wrong"
    else:
        full["bookings"]["w1"] = None
    if operation == "promote":
        full["events"]["e1"]["capacity"] = 8
    if operation == "cleanup":
        full["events"]["e1"]["status"] = "cancelled"
    before = deepcopy(full)
    with pytest.raises(ValueError):
        if operation == "register":
            bookings.register_participant(full, "e1", "new", "Sample")
        elif operation == "confirmed-cancel":
            bookings.cancel_registration(full, "c1")
        elif operation == "waiting-cancel":
            bookings.cancel_registration(full, "w2")
        elif operation == "promote":
            bookings.fill_available_seats(full, "e1")
        else:
            bookings.remove_event_registrations(full, "e1")
    assert full == before


def test_cancellation_rejects_unfinished_capacity_increase(full):
    events.update_event(full, "e1", {"capacity": 4}, confirmed_count=2)
    before = deepcopy(full)
    with pytest.raises(ValueError, match="earlier capacity"):
        bookings.cancel_registration(full, "c1")
    assert full == before


def test_cancelled_event_cannot_cancel_individual_booking(full):
    events.cancel_event(full, "e1")
    before = deepcopy(full)
    with pytest.raises(ValueError, match="active"):
        bookings.cancel_registration(full, "c1")
    assert full == before


def test_cleanup_removes_sorted_target_ids_without_promotion(full):
    insertion_order = ["w2", "c1", "w3", "c2", "w1", "other"]
    full["bookings"] = {
        booking_id: full["bookings"][booking_id] for booking_id in insertion_order
    }
    assert [
        booking_id
        for booking_id, booking in full["bookings"].items()
        if booking["event_id"] == "e1"
    ] == ["w2", "c1", "w3", "c2", "w1"]
    events.cancel_event(full, "e1")
    before = deepcopy(full)
    assert bookings.remove_event_registrations(full, "e1") == [
        "c1",
        "c2",
        "w1",
        "w2",
        "w3",
    ]
    for booking_id in ["c1", "c2", "w1", "w2", "w3"]:
        del before["bookings"][booking_id]
    before["events"]["e1"]["waiting_list"] = []
    assert full == before
    assert bookings.remove_event_registrations(full, "e1") == []
    assert full == before
    storage.validate_state(full)


def test_cleanup_already_clean_cancelled_event(empty):
    before = deepcopy(empty)
    assert bookings.remove_event_registrations(empty, "e3") == []
    assert empty == before


def test_cleanup_active_event_rejected_atomically(full):
    before = deepcopy(full)
    with pytest.raises(ValueError, match="Only cancelled"):
        bookings.remove_event_registrations(full, "e1")
    assert full == before


def test_capacity_increase_then_promotion_completes_storage_invariant(full):
    storage.validate_state(full)
    count = bookings.event_counts(full, "e1")["confirmed_count"]
    events.update_event(full, "e1", {"capacity": 4}, confirmed_count=count)
    with pytest.raises(ValueError, match="available seats"):
        storage.validate_state(full)
    assert bookings.fill_available_seats(full, "e1") == ["w2", "w1"]
    storage.validate_state(full)


def test_event_cancellation_then_cleanup_completes_storage_invariant(full):
    storage.validate_state(full)
    assert events.cancel_event(full, "e1") is True
    assert bookings.event_counts(full, "e1") == {
        "confirmed_count": 2,
        "waiting_count": 3,
    }
    with pytest.raises(ValueError, match="Cancelled"):
        storage.validate_state(full)
    bookings.remove_event_registrations(full, "e1")
    storage.validate_state(full)
    assert bookings.event_counts(full, "e1") == {
        "confirmed_count": 0,
        "waiting_count": 0,
    }


def test_booking_core_has_no_output_or_persistence(empty, capsys):
    with patch("storage.save_state", side_effect=AssertionError("unexpected save")):
        record = bookings.register_participant(empty, "e1", "001", "Sample")
        bookings.get_booking(empty, record["booking_id"])
        bookings.find_registration(empty, "e1", "001")
        bookings.event_counts(empty, "e1")
        bookings.fill_available_seats(empty, "e1")
        bookings.cancel_registration(empty, record["booking_id"])
        events.cancel_event(empty, "e1")
        bookings.remove_event_registrations(empty, "e1")
    captured = capsys.readouterr()
    assert captured.out == captured.err == ""
