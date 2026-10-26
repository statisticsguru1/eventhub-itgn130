"""Event-level contracts; booking cleanup/promotion remain later operations."""

from copy import deepcopy
from unittest.mock import patch
from uuid import UUID

import pytest

import events
import storage


def event_record(event_id="b", **changes):
    record = {
        "event_id": event_id,
        "title": "Python Workshop",
        "date": "2024-02-29",
        "venue": "Lecture Hall",
        "capacity": 2,
        "status": "active",
        "waiting_list": [],
    }
    record.update(changes)
    return record


@pytest.fixture
def state():
    return {
        "schema_version": 1,
        "events": {
            "b": event_record(waiting_list=["w2", "w1"]),
            "a": event_record(
                "a", title="Workshop Annex", venue="Workshop Room", status="cancelled"
            ),
            "c": event_record("c", title="Earlier", date="2023-01-01"),
        },
        "bookings": {
            key: {
                "booking_id": key,
                "event_id": "b",
                "student_id": student,
                "student_name": "Sample Student",
                "status": status,
            }
            for key, student, status in [
                ("c1", "001", "confirmed"),
                ("c2", "002", "confirmed"),
                ("w1", "003", "waiting"),
                ("w2", "004", "waiting"),
            ]
        },
    }


def test_fixture_satisfies_persisted_state_contract(state):
    storage.validate_state(state)


def test_create_all_fields_generated_id_normalization_and_copy(state):
    before = deepcopy(state)
    created = events.create_event(state, "  New  ", "2000-02-29", " Room B ", 3)
    assert isinstance(created["event_id"], str)
    assert str(UUID(created["event_id"])) == created["event_id"]
    assert created == {
        "event_id": created["event_id"],
        "title": "New",
        "date": "2000-02-29",
        "venue": "Room B",
        "capacity": 3,
        "status": "active",
        "waiting_list": [],
    }
    inserted = deepcopy(created)
    created["title"] = "Changed"
    created["waiting_list"].append("not-in-state")
    assert state["events"][inserted["event_id"]] == inserted
    del state["events"][inserted["event_id"]]
    assert state == before


def test_generated_collision_does_not_overwrite(state):
    before = deepcopy(state)
    with patch("events.uuid.uuid4", return_value="b") as generate:
        with pytest.raises(ValueError, match="already exists"):
            events.create_event(state, "New", "2024-01-01", "Room", 1)
    generate.assert_called_once()
    assert state == before


@pytest.mark.parametrize(
    "field,value",
    [
        ("title", ""),
        ("title", " "),
        ("title", None),
        ("title", 1),
        ("venue", ""),
        ("venue", " "),
        ("venue", None),
        ("venue", []),
        ("date", "2024-2-29"),
        ("date", "20240229"),
        ("date", "2023-02-29"),
        ("date", "2024-13-01"),
        ("date", "0000-01-01"),
        ("date", "2024-01-01\n"),
        ("date", None),
        ("date", 1),
        ("capacity", 0),
        ("capacity", -1),
        ("capacity", 1.5),
        ("capacity", True),
        ("capacity", False),
        ("capacity", "2"),
        ("capacity", None),
    ],
)
def test_invalid_create_leaves_whole_state_unchanged(state, field, value):
    before = deepcopy(state)
    arguments = {"title": "New", "date": "2024-01-01", "venue": "Room", "capacity": 1}
    arguments[field] = value
    with pytest.raises(ValueError):
        events.create_event(state, **arguments)
    assert state == before


@pytest.mark.parametrize(
    "field",
    [
        "event_id",
        "title",
        "date",
        "venue",
        "capacity",
        "status",
        "waiting_list",
    ],
)
def test_validate_requires_each_explicit_field(field):
    record = event_record()
    del record[field]
    with pytest.raises(ValueError):
        events.validate_event(record)


@pytest.mark.parametrize(
    "field,value",
    [
        ("event_id", ""),
        ("event_id", " "),
        ("event_id", 1),
        ("title", " padded "),
        ("venue", " padded "),
        ("status", "unknown"),
        ("status", []),
        ("waiting_list", None),
        ("waiting_list", "booking"),
        ("waiting_list", [1]),
        ("waiting_list", [""]),
        ("waiting_list", [" "]),
        ("waiting_list", ["same", "same"]),
    ],
)
def test_invalid_complete_record_is_not_normalized(field, value):
    record = event_record(**{field: value})
    before = deepcopy(record)
    with pytest.raises(ValueError):
        events.validate_event(record)
    assert record == before


@pytest.mark.parametrize("record", [None, [], "event", {**event_record(), "extra": 1}])
def test_validate_rejects_nonrecord_or_unexpected_fields(record):
    with pytest.raises(ValueError):
        events.validate_event(record)


def test_validation_is_event_only_and_does_not_mutate():
    # Reference resolution and cancelled-event cleanup are storage responsibilities.
    record = event_record(status="cancelled", waiting_list=["unknown-booking"])
    before = deepcopy(record)
    assert events.validate_event(record) is None
    assert record == before


@pytest.mark.parametrize("event_id", ["b", "a"])
def test_get_includes_both_statuses_and_returns_nested_copy(state, event_id):
    before = deepcopy(state)
    result = events.get_event(state, event_id)
    assert result == before["events"][event_id]
    result["title"] = "Changed"
    result["waiting_list"].append("changed")
    assert state == before


@pytest.mark.parametrize("operation", ["get", "update", "cancel"])
@pytest.mark.parametrize("event_id", [None, "", " ", 3, [], {}])
def test_invalid_lookup_id_is_controlled_and_does_not_mutate(
    state, operation, event_id
):
    before = deepcopy(state)
    with pytest.raises(ValueError):
        if operation == "get":
            events.get_event(state, event_id)
        elif operation == "update":
            events.update_event(state, event_id, {})
        else:
            events.cancel_event(state, event_id)
    assert state == before


@pytest.mark.parametrize("event_id", ["missing", " b ", "B"])
def test_exact_unknown_ids_for_all_operations(state, event_id):
    before = deepcopy(state)
    for operation in [
        lambda: events.get_event(state, event_id),
        lambda: events.update_event(state, event_id, {}),
        lambda: events.cancel_event(state, event_id),
    ]:
        with pytest.raises(KeyError):
            operation()
    assert state == before


def test_list_order_cancelled_inclusion_and_copy(state):
    before = deepcopy(state)
    result = events.list_events(state)
    assert [event["event_id"] for event in result] == ["c", "a", "b"]
    assert result[1]["status"] == "cancelled"
    result[2]["waiting_list"].clear()
    result[0]["title"] = "changed"
    assert state == before
    assert events.list_events(storage.empty_state()) == []


@pytest.mark.parametrize(
    "changes,expected",
    [
        ({"title": " New "}, {"title": "New"}),
        ({"venue": " Room B "}, {"venue": "Room B"}),
        ({"date": "1999-01-01"}, {"date": "1999-01-01"}),
        ({"capacity": 3}, {"capacity": 3}),
        (
            {"title": " New ", "venue": " Room ", "date": "2025-01-01", "capacity": 4},
            {"title": "New", "venue": "Room", "date": "2025-01-01", "capacity": 4},
        ),
    ],
)
def test_valid_edit_changes_only_requested_fields(state, changes, expected):
    before = deepcopy(state)
    kwargs = {"confirmed_count": 2} if "capacity" in changes else {}
    assert events.update_event(state, "b", changes, **kwargs) is None
    before["events"]["b"].update(expected)
    assert state == before


@pytest.mark.parametrize(
    "changes",
    [
        {"title": ""},
        {"venue": None},
        {"date": "2023-02-29"},
        {"title": "Valid", "venue": " "},
        {"title": "Valid", "capacity": False},
        {"capacity": 0},
        {"capacity": -1},
        {"capacity": 1.5},
        {"capacity": "3"},
        {"capacity": None},
        {"date": "20240101"},
        {"event_id": "new"},
        {"status": "active"},
        {"status": "cancelled"},
        {"waiting_list": []},
        {"unknown": 1},
        None,
        [],
        "title",
    ],
)
def test_invalid_edit_is_atomic_at_event_boundary(state, changes):
    before = deepcopy(state)
    with pytest.raises(ValueError):
        events.update_event(state, "b", changes, confirmed_count=2)
    assert state == before


@pytest.mark.parametrize("changes", [{}, {"title": "New"}, {"status": "active"}])
def test_cancelled_event_rejects_edit_and_reactivation(state, changes):
    before = deepcopy(state)
    with pytest.raises(ValueError, match="Cancelled"):
        events.update_event(state, "a", changes)
    assert state == before


def test_empty_active_edit_is_noop_without_count(state):
    before = deepcopy(state)
    assert events.update_event(state, "b", {}) is None
    assert state == before


@pytest.mark.parametrize("count", [None, True, False, -1, 1.5, "1", [], 3])
def test_capacity_change_requires_valid_explicit_count(state, count):
    before = deepcopy(state)
    with pytest.raises(ValueError):
        events.update_event(state, "b", {"capacity": 3}, confirmed_count=count)
    assert state == before


def test_omitted_capacity_count_is_rejected(state):
    before = deepcopy(state)
    with pytest.raises(ValueError, match="require confirmed_count"):
        events.update_event(state, "b", {"capacity": 3})
    assert state == before


@pytest.mark.parametrize("count", [True, -1, 1.5, "1", 3])
def test_noncapacity_edit_validates_supplied_count(state, count):
    before = deepcopy(state)
    with pytest.raises(ValueError, match="confirmed_count"):
        events.update_event(state, "b", {"title": "New"}, confirmed_count=count)
    assert state == before


@pytest.mark.parametrize("count", [None, 0, 1, 2])
def test_noncapacity_edit_accepts_valid_count_without_using_it(state, count):
    before = deepcopy(state)
    events.update_event(state, "b", {"title": "New"}, confirmed_count=count)
    before["events"]["b"]["title"] = "New"
    assert state == before


@pytest.mark.parametrize("new_capacity", [3, 2])
def test_capacity_reduction_above_or_equal_to_attendance(state, new_capacity):
    state["events"]["c"]["capacity"] = 4
    for booking_id, student_id in [("c3", "005"), ("c4", "006")]:
        state["bookings"][booking_id] = {
            "booking_id": booking_id,
            "event_id": "c",
            "student_id": student_id,
            "student_name": "Sample Student",
            "status": "confirmed",
        }
    storage.validate_state(state)
    assert (
        sum(
            booking["event_id"] == "c" and booking["status"] == "confirmed"
            for booking in state["bookings"].values()
        )
        == 2
    )
    before = deepcopy(state)
    assert (
        events.update_event(state, "c", {"capacity": new_capacity}, confirmed_count=2)
        is None
    )
    before["events"]["c"]["capacity"] = new_capacity
    assert state == before


def test_capacity_edit_uses_supplied_count_without_recounting(state):
    # Deliberately supply a higher count than c's actual zero to prove this
    # helper enforces the orchestration input rather than recounting bookings.
    state["events"]["c"]["capacity"] = 4
    before = deepcopy(state)
    with pytest.raises(ValueError, match="below confirmed"):
        events.update_event(state, "c", {"capacity": 1}, confirmed_count=2)
    assert state == before


def test_capacity_edit_accepts_zero_confirmed_count(state):
    assert not any(booking["event_id"] == "c" for booking in state["bookings"].values())
    before = deepcopy(state)
    assert events.update_event(state, "c", {"capacity": 1}, confirmed_count=0) is None
    before["events"]["c"]["capacity"] = 1
    assert state == before
    assert state["events"]["c"]["waiting_list"] == []


def test_reduction_below_confirmed_count_rejected(state):
    before = deepcopy(state)
    with pytest.raises(ValueError, match="below confirmed"):
        events.update_event(state, "b", {"capacity": 1}, confirmed_count=2)
    assert state == before


def test_capacity_increase_does_not_promote_or_mutate_booking_records(state):
    before = deepcopy(state)
    assert events.update_event(state, "b", {"capacity": 4}, confirmed_count=2) is None
    before["events"]["b"]["capacity"] = 4
    assert state == before
    assert state["events"]["b"]["waiting_list"] == ["w2", "w1"]
    assert state["bookings"]["w2"]["status"] == "waiting"


def test_cancel_changes_only_status_and_repeat_is_noop(state):
    before = deepcopy(state)
    assert events.cancel_event(state, "b") is True
    before["events"]["b"]["status"] = "cancelled"
    assert state == before
    assert events.cancel_event(state, "b") is False
    assert state == before
    assert state["events"]["b"]["waiting_list"] == ["w2", "w1"]


@pytest.mark.parametrize(
    "query,ids",
    [
        ("Python", ["b"]),
        ("lecture", ["c", "b"]),
        ("  pYtHoN  ", ["b"]),
        ("workshop", ["a", "b"]),
        ("Room", ["a"]),
        ("none", []),
        ("", ["c", "a", "b"]),
        (" \t ", ["c", "a", "b"]),
    ],
)
def test_keyword_matching_order_and_no_duplicates(state, query, ids):
    before = deepcopy(state)
    result = events.search_by_keyword(state, query)
    assert [event["event_id"] for event in result] == ids
    assert state == before


@pytest.mark.parametrize("query", [None, 1, [], {}])
def test_keyword_requires_string(state, query):
    with pytest.raises(ValueError):
        events.search_by_keyword(state, query)


@pytest.mark.parametrize(
    "date,ids",
    [
        ("2024-02-29", ["a", "b"]),
        ("2023-01-01", ["c"]),
        ("2000-01-01", []),
    ],
)
def test_exact_date_search_includes_cancelled_and_past_events(state, date, ids):
    before = deepcopy(state)
    assert [event["event_id"] for event in events.search_by_date(state, date)] == ids
    assert state == before


@pytest.mark.parametrize(
    "date",
    [
        "",
        " ",
        "2024-2-29",
        "20240229",
        "2023-02-29",
        "2024-01-01T00:00:00",
        "2024-01-01\n",
        None,
        1,
    ],
)
def test_date_search_rejects_invalid_dates(state, date):
    with pytest.raises(ValueError):
        events.search_by_date(state, date)


@pytest.mark.parametrize(
    "search",
    [
        lambda state: events.search_by_keyword(state, "workshop"),
        lambda state: events.search_by_date(state, "2024-02-29"),
    ],
)
def test_search_returns_independent_records_without_counts(state, search):
    before = deepcopy(state)
    result = search(state)
    assert set(result[0]) == {
        "event_id",
        "title",
        "date",
        "venue",
        "capacity",
        "status",
        "waiting_list",
    }
    result[0]["title"] = "changed"
    result[-1]["waiting_list"].clear()
    assert state == before


def test_domain_operations_do_not_print(state, capsys):
    events.create_event(state, "New", "2024-01-01", "Room", 2)
    events.get_event(state, "b")
    events.list_events(state)
    events.update_event(state, "b", {"title": "Changed"})
    events.search_by_keyword(state, "changed")
    events.search_by_date(state, "2024-02-29")
    events.cancel_event(state, "b")
    captured = capsys.readouterr()
    assert captured.out == captured.err == ""
