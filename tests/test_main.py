"""Application operations complete domain changes before a single safe save."""

import ast
from copy import deepcopy
import importlib.util
from pathlib import Path
from unittest.mock import Mock

import pytest

import bookings
import events
import main
import storage


@pytest.fixture
def state():
    value = storage.empty_state()
    for event_id, capacity, status in [
        ("full", 2, "active"),
        ("open", 4, "active"),
        ("closed", 2, "cancelled"),
    ]:
        value["events"][event_id] = {
            "event_id": event_id,
            "title": "Sample Event",
            "date": "2024-02-29",
            "venue": "Room A",
            "capacity": capacity,
            "status": status,
            "waiting_list": [],
        }
    for booking_id, event_id, student_id, status in [
        ("c1", "full", "001", "confirmed"),
        ("c2", "full", "002", "confirmed"),
        ("w1", "full", "003", "waiting"),
        ("w2", "full", "004", "waiting"),
        ("w3", "full", "005", "waiting"),
        ("other", "open", "001", "confirmed"),
    ]:
        value["bookings"][booking_id] = {
            "booking_id": booking_id,
            "event_id": event_id,
            "student_id": student_id,
            "student_name": f"Sample {student_id}",
            "status": status,
        }
    # FIFO deliberately differs from dictionary order.
    value["events"]["full"]["waiting_list"] = ["w2", "w1", "w3"]
    storage.validate_state(value)
    return value


def assert_saved(original, before, returned, data_dir):
    assert original == before
    assert returned is not original
    storage.validate_state(returned)
    assert storage.load_state(data_dir) == returned


def test_create_event_persists_independent_result(state, tmp_path):
    before = deepcopy(state)
    returned, result = main.create_event_operation(
        state, tmp_path, " New ", "2025-01-01", " Hall ", 3
    )
    assert set(result) == {"event"}
    event = result["event"]
    assert event == {
        "event_id": event["event_id"],
        "title": "New",
        "date": "2025-01-01",
        "venue": "Hall",
        "capacity": 3,
        "status": "active",
        "waiting_list": [],
    }
    expected = deepcopy(before)
    expected["events"][event["event_id"]] = deepcopy(event)
    assert returned == expected
    assert_saved(state, before, returned, tmp_path)
    event["title"] = "Changed"
    event["waiting_list"].append("not-a-booking")
    assert returned == expected


@pytest.mark.parametrize(
    "changes,expected",
    [
        ({"title": " New "}, {"title": "New"}),
        ({"venue": " Hall "}, {"venue": "Hall"}),
        ({"date": "2000-01-01"}, {"date": "2000-01-01"}),
        ({"title": " New ", "venue": " Hall "}, {"title": "New", "venue": "Hall"}),
    ],
)
def test_update_fields_persists_only_requested_change(
    state, tmp_path, changes, expected
):
    before = deepcopy(state)
    returned, result = main.update_event_operation(state, tmp_path, "full", changes)
    target = deepcopy(before)
    target["events"]["full"].update(expected)
    assert returned == target
    assert result == {
        "changed": True,
        "event": target["events"]["full"],
        "promoted_booking_ids": [],
    }
    assert_saved(state, before, returned, tmp_path)
    result["event"]["waiting_list"].clear()
    result["event"]["title"] = "Changed"
    assert returned == target


@pytest.mark.parametrize(
    "changes",
    [{}, {"title": "Sample Event"}, {"venue": " Room A "}, {"capacity": 2}],
)
def test_valid_noop_edit_runs_domain_but_skips_save(
    state, tmp_path, monkeypatch, changes
):
    before = deepcopy(state)
    update = Mock(wraps=events.update_event)
    save = Mock(side_effect=AssertionError("unexpected save"))
    monkeypatch.setattr(events, "update_event", update)
    monkeypatch.setattr(storage, "save_state", save)
    returned, result = main.update_event_operation(state, tmp_path, "full", changes)
    update.assert_called_once()
    save.assert_not_called()
    assert returned is state
    assert result == {
        "changed": False,
        "event": before["events"]["full"],
        "promoted_booking_ids": [],
    }
    result["event"]["waiting_list"].clear()
    assert state == before
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize(
    "capacity,promoted,remaining",
    [
        (3, ["w2"], ["w1", "w3"]),
        (4, ["w2", "w1"], ["w3"]),
        (8, ["w2", "w1", "w3"], []),
    ],
)
def test_capacity_increase_completes_fifo_before_save(
    state, tmp_path, capacity, promoted, remaining
):
    before = deepcopy(state)
    returned, result = main.update_event_operation(
        state, tmp_path, "full", {"capacity": capacity}
    )
    expected = deepcopy(before)
    expected["events"]["full"].update(capacity=capacity, waiting_list=remaining)
    for booking_id in promoted:
        expected["bookings"][booking_id]["status"] = "confirmed"
    assert returned == expected
    assert result == {
        "changed": True,
        "event": expected["events"]["full"],
        "promoted_booking_ids": promoted,
    }
    assert_saved(state, before, returned, tmp_path)
    result["promoted_booking_ids"].clear()
    result["event"]["waiting_list"].append("changed")
    assert returned == expected


@pytest.mark.parametrize("capacity", [1, 2, 6])
def test_capacity_decrease_above_equal_and_increase_without_queue(
    state, tmp_path, capacity
):
    before = deepcopy(state)
    returned, result = main.update_event_operation(
        state, tmp_path, "open", {"capacity": capacity}
    )
    expected = deepcopy(before)
    expected["events"]["open"]["capacity"] = capacity
    assert returned == expected
    assert result["promoted_booking_ids"] == []
    assert_saved(state, before, returned, tmp_path)


def test_capacity_calls_counts_update_and_fill_for_equal_edit(
    state, tmp_path, monkeypatch
):
    counts = Mock(wraps=bookings.event_counts)
    update = Mock(wraps=events.update_event)
    fill = Mock(wraps=bookings.fill_available_seats)
    monkeypatch.setattr(bookings, "event_counts", counts)
    monkeypatch.setattr(events, "update_event", update)
    monkeypatch.setattr(bookings, "fill_available_seats", fill)
    main.update_event_operation(state, tmp_path, "full", {"capacity": 2})
    candidate = update.call_args.args[0]
    assert candidate is not state
    assert counts.call_args_list[0].args == (candidate, "full")
    assert update.call_args.kwargs == {"confirmed_count": 2}
    fill.assert_called_once_with(candidate, "full")


def test_noncapacity_edit_does_not_supply_count_or_fill(state, tmp_path, monkeypatch):
    update = Mock(wraps=events.update_event)
    monkeypatch.setattr(events, "update_event", update)
    monkeypatch.setattr(bookings, "event_counts", Mock(side_effect=AssertionError))
    monkeypatch.setattr(
        bookings, "fill_available_seats", Mock(side_effect=AssertionError)
    )
    main.update_event_operation(state, tmp_path, "full", {"title": "New"})
    assert update.call_args.kwargs == {}


def test_cancel_event_cleans_bookings_and_preserves_other_state(state, tmp_path):
    before = deepcopy(state)
    returned, result = main.cancel_event_operation(state, tmp_path, "full")
    expected = deepcopy(before)
    expected["events"]["full"].update(status="cancelled", waiting_list=[])
    expected["bookings"] = {"other": before["bookings"]["other"]}
    assert returned == expected
    assert result == {
        "changed": True,
        "event": expected["events"]["full"],
        "removed_booking_ids": ["c1", "c2", "w1", "w2", "w3"],
    }
    assert_saved(state, before, returned, tmp_path)
    result["event"]["waiting_list"].append("changed")
    result["removed_booking_ids"].clear()
    assert returned == expected


def test_repeated_cancellation_skips_cleanup_and_save(state, tmp_path, monkeypatch):
    before = deepcopy(state)
    cleanup = Mock(side_effect=AssertionError("unexpected cleanup"))
    save = Mock(side_effect=AssertionError("unexpected save"))
    monkeypatch.setattr(bookings, "remove_event_registrations", cleanup)
    monkeypatch.setattr(storage, "save_state", save)
    returned, result = main.cancel_event_operation(state, tmp_path, "closed")
    assert returned is state
    assert result == {
        "changed": False,
        "event": before["events"]["closed"],
        "removed_booking_ids": [],
    }
    cleanup.assert_not_called()
    save.assert_not_called()
    result["event"]["waiting_list"].append("changed")
    assert state == before


@pytest.mark.parametrize(
    "event_id,status", [("open", "confirmed"), ("full", "waiting")]
)
def test_registration_persists_status_and_independent_copy(
    state, tmp_path, event_id, status
):
    before = deepcopy(state)
    returned, result = main.register_participant_operation(
        state, tmp_path, event_id, " 006 ", " Sample Six "
    )
    assert set(result) == {"booking"}
    booking = result["booking"]
    assert booking == {
        "booking_id": booking["booking_id"],
        "event_id": event_id,
        "student_id": "006",
        "student_name": "Sample Six",
        "status": status,
    }
    expected = deepcopy(before)
    expected["bookings"][booking["booking_id"]] = deepcopy(booking)
    if status == "waiting":
        expected["events"][event_id]["waiting_list"].append(booking["booking_id"])
    assert returned == expected
    assert_saved(state, before, returned, tmp_path)
    booking["student_name"] = "Changed"
    assert returned == expected


@pytest.mark.parametrize(
    "event_id,student_id,cancelled_id,promoted,remaining",
    [
        ("open", " 001 ", "other", [], []),
        ("full", " 001 ", "c1", ["w2"], ["w1", "w3"]),
        ("full", "003", "w1", [], ["w2", "w3"]),
    ],
)
def test_cancel_by_student_persists_details_and_independent_results(
    state, tmp_path, event_id, student_id, cancelled_id, promoted, remaining
):
    before = deepcopy(state)
    returned, result = main.cancel_registration_operation(
        state, tmp_path, event_id, student_id
    )
    expected = deepcopy(before)
    del expected["bookings"][cancelled_id]
    expected["events"][event_id]["waiting_list"] = remaining
    for booking_id in promoted:
        expected["bookings"][booking_id]["status"] = "confirmed"
    assert returned == expected
    assert result == {
        "cancelled_booking": before["bookings"][cancelled_id],
        "promoted_bookings": [expected["bookings"][key] for key in promoted],
    }
    assert_saved(state, before, returned, tmp_path)
    result["cancelled_booking"]["student_name"] = "Changed"
    if promoted:
        assert result["promoted_bookings"][0]["student_id"] == "004"
        result["promoted_bookings"][0]["student_name"] = "Changed"
    result["promoted_bookings"].clear()
    assert returned == expected
    assert state == before


# A small test-only call table exercises the same failure guarantees for all APIs.
OPERATIONS = [
    ("create_event_operation", ("New", "2025-01-01", "Hall", 2)),
    ("update_event_operation", ("full", {"capacity": 4})),
    ("cancel_event_operation", ("full",)),
    ("register_participant_operation", ("full", "006", "Sample Six")),
    ("cancel_registration_operation", ("full", "001")),
]


@pytest.mark.parametrize("operation,args", OPERATIONS)
@pytest.mark.parametrize("error_type", [ValueError, OSError])
def test_save_failure_leaves_caller_binding_and_state_unchanged(
    state, tmp_path, monkeypatch, operation, args, error_type
):
    storage.save_state(state, tmp_path)
    before = deepcopy(state)
    raw = (tmp_path / "eventhub.json").read_bytes()
    error = error_type("save rejected")
    seen = []

    def fail(candidate, data_dir):
        assert candidate is not state
        storage.validate_state(candidate)
        seen.append(deepcopy(candidate))
        raise error

    monkeypatch.setattr(storage, "save_state", fail)
    active = state
    with pytest.raises(error_type) as caught:
        active, result = getattr(main, operation)(active, tmp_path, *args)
    assert caught.value is error
    assert active is state
    assert state == before
    assert len(seen) == 1 and seen[0] != before
    assert (tmp_path / "eventhub.json").read_bytes() == raw


@pytest.mark.parametrize(
    "operation,args,error_type",
    [
        ("create_event_operation", ("", "2025-01-01", "Hall", 2), ValueError),
        ("update_event_operation", ("full", {"capacity": 1}), ValueError),
        ("update_event_operation", ("closed", {}), ValueError),
        ("update_event_operation", ("full", {"status": "active"}), ValueError),
        ("update_event_operation", ("full", {"title": ""}), ValueError),
        ("update_event_operation", ("full", None), ValueError),
        ("update_event_operation", ("full", []), ValueError),
        ("update_event_operation", ("missing", {}), KeyError),
        ("cancel_event_operation", ("missing",), KeyError),
        ("register_participant_operation", ("full", " 001 ", "New"), ValueError),
        ("register_participant_operation", ("closed", "006", "New"), ValueError),
        ("register_participant_operation", ("missing", "006", "New"), KeyError),
        ("cancel_registration_operation", ("full", "missing"), KeyError),
        ("cancel_registration_operation", ("missing", "001"), KeyError),
    ],
)
def test_domain_rejection_never_saves(
    state, tmp_path, monkeypatch, operation, args, error_type
):
    before = deepcopy(state)
    save = Mock(side_effect=AssertionError("unexpected save"))
    monkeypatch.setattr(storage, "save_state", save)
    with pytest.raises(error_type):
        getattr(main, operation)(state, tmp_path, *args)
    save.assert_not_called()
    assert state == before
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize(
    "module,function,operation,args",
    [
        (events, "create_event", *OPERATIONS[0]),
        (bookings, "fill_available_seats", *OPERATIONS[1]),
        (bookings, "remove_event_registrations", *OPERATIONS[2]),
        (bookings, "register_participant", *OPERATIONS[3]),
        (bookings, "cancel_registration", *OPERATIONS[4]),
        (bookings, "get_booking", *OPERATIONS[4]),
    ],
)
def test_candidate_only_mutation_then_failure_is_discarded(
    state, tmp_path, monkeypatch, module, function, operation, args
):
    before = deepcopy(state)
    save = Mock(side_effect=AssertionError("unexpected save"))
    error = ValueError("injected domain failure")

    def fail(candidate, *args, **kwargs):
        assert candidate is not state
        candidate["events"]["open"]["waiting_list"].append("candidate-only")
        candidate["bookings"]["other"]["student_name"] = "candidate-only"
        raise error

    monkeypatch.setattr(module, function, fail)
    monkeypatch.setattr(storage, "save_state", save)
    with pytest.raises(ValueError) as caught:
        getattr(main, operation)(state, tmp_path, *args)
    assert caught.value is error
    assert state == before
    save.assert_not_called()


def test_real_replace_failure_preserves_authoritative_bytes(
    state, tmp_path, monkeypatch
):
    storage.save_state(state, tmp_path)
    before = deepcopy(state)
    path = tmp_path / "eventhub.json"
    raw = path.read_bytes()
    monkeypatch.setattr(
        storage.os, "replace", Mock(side_effect=OSError("replace failed"))
    )
    with pytest.raises(OSError, match="replace failed"):
        main.update_event_operation(state, tmp_path, "full", {"capacity": 4})
    assert state == before
    assert path.read_bytes() == raw
    assert storage.load_state(tmp_path) == before
    assert not list(tmp_path.glob("*.tmp"))


def test_complete_candidate_validation_failure_preserves_snapshot(
    state, tmp_path, monkeypatch
):
    storage.save_state(state, tmp_path)
    before = deepcopy(state)
    raw = (tmp_path / "eventhub.json").read_bytes()
    real_create = events.create_event

    def invalid_candidate(candidate, *args):
        event = real_create(candidate, *args)
        candidate["schema_version"] = 2
        return event

    monkeypatch.setattr(events, "create_event", invalid_candidate)
    with pytest.raises(ValueError, match="schema_version"):
        main.create_event_operation(state, tmp_path, "New", "2025-01-01", "Hall", 2)
    assert state == before
    assert (tmp_path / "eventhub.json").read_bytes() == raw


def test_committed_save_cleanup_warning_still_returns_new_state(
    state, tmp_path, monkeypatch, caplog
):
    before = deepcopy(state)
    real_unlink = Path.unlink

    def fail_temporary_cleanup(path, *args, **kwargs):
        if path.suffix == ".tmp":
            raise OSError("cleanup warning")
        return real_unlink(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", fail_temporary_cleanup)
    returned, result = main.update_event_operation(
        state, tmp_path, "full", {"capacity": 4}
    )
    assert result["promoted_booking_ids"] == ["w2", "w1"]
    assert "cleanup warning" in caplog.text
    assert_saved(state, before, returned, tmp_path)


def test_cancellation_result_is_resolved_on_candidate_before_save(
    state, tmp_path, monkeypatch
):
    real_find = bookings.find_registration
    real_get = bookings.get_booking
    real_save = storage.save_state
    candidates = []
    saved = False

    def find(candidate, *args):
        assert candidate is not state
        assert not saved
        candidates.append(candidate)
        return real_find(candidate, *args)

    def get(candidate, *args):
        assert candidate is candidates[0]
        assert not saved
        return real_get(candidate, *args)

    def save(candidate, data_dir):
        nonlocal saved
        assert candidate is candidates[0]
        real_save(candidate, data_dir)
        saved = True

    monkeypatch.setattr(bookings, "find_registration", find)
    monkeypatch.setattr(bookings, "get_booking", get)
    monkeypatch.setattr(storage, "save_state", save)
    returned, result = main.cancel_registration_operation(
        state, tmp_path, "full", "001"
    )
    assert saved
    assert returned is candidates[0]
    assert result["promoted_bookings"][0]["booking_id"] == "w2"


def test_import_is_side_effect_free_and_api_has_no_interaction(
    tmp_path, monkeypatch, capsys
):
    # Execute a fresh module without invoking any operation or application startup.
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(storage, "load_state", Mock(side_effect=AssertionError("load")))
    monkeypatch.setattr(storage, "save_state", Mock(side_effect=AssertionError("save")))
    monkeypatch.setattr(Path, "mkdir", Mock(side_effect=AssertionError("mkdir")))
    monkeypatch.setattr(Path, "open", Mock(side_effect=AssertionError("open")))
    monkeypatch.setattr("builtins.input", Mock(side_effect=AssertionError("input")))
    source_path = Path(main.__file__)
    spec = importlib.util.spec_from_file_location(
        "orchestration_import_check", source_path
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.DEFAULT_DATA_DIR == source_path.resolve().parent / "data"
    assert not list(tmp_path.iterdir())
    assert capsys.readouterr() == ("", "")


def test_operations_have_no_terminal_io(state, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr("builtins.input", Mock(side_effect=AssertionError("input")))
    for operation, args in OPERATIONS:
        getattr(main, operation)(state, tmp_path, *args)
    assert capsys.readouterr() == ("", "")
    tree = ast.parse(Path(main.__file__).read_text())
    public = {node.name for node in tree.body if isinstance(node, ast.FunctionDef)}
    orchestration_api = {name for name, _ in OPERATIONS}
    read_api = {
        "list_events_view",
        "search_events_by_keyword_view",
        "search_events_by_date_view",
        "summary_report",
    }
    console_api = {"main", "run_menu"}
    private_helpers = {
        "_event_view",
        "_show_error",
        "_read_capacity",
        "_prompt_event_changes",
        "_display_events",
        "_display_report",
        "_search_menu",
    }
    assert public == orchestration_api | read_api | console_api | private_helpers


VIEW_FIELDS = {
    "event_id",
    "title",
    "date",
    "venue",
    "capacity",
    "status",
    "confirmed_count",
    "waiting_count",
}
READ_CALLS = [
    ("list_events_view", ()),
    ("search_events_by_keyword_view", ("",)),
    ("search_events_by_date_view", ("2024-02-29",)),
    ("summary_report", ()),
]


def test_list_view_exact_fields_counts_order_and_independence(state):
    state["events"]["open"]["date"] = "2000-01-01"
    storage.validate_state(state)
    before = deepcopy(state)
    rows = main.list_events_view(state)
    assert [row["event_id"] for row in rows] == ["open", "closed", "full"]
    for row in rows:
        assert set(row) == VIEW_FIELDS
        event_id = row["event_id"]
        assert {
            key: row[key] for key in VIEW_FIELDS - {"confirmed_count", "waiting_count"}
        } == {
            key: before["events"][event_id][key]
            for key in VIEW_FIELDS - {"confirmed_count", "waiting_count"}
        }
    assert [(row["confirmed_count"], row["waiting_count"]) for row in rows] == [
        (1, 0),
        (0, 0),
        (2, 3),
    ]
    expected = deepcopy(rows)
    rows[0]["title"] = "Changed"
    rows[2]["waiting_count"] = 99
    rows.clear()
    assert main.list_events_view(state) == expected
    assert state == before


def test_empty_and_single_event_views():
    state = storage.empty_state()
    assert main.list_events_view(state) == []
    assert main.search_events_by_keyword_view(state, "") == []
    assert main.search_events_by_date_view(state, "2024-02-29") == []
    event = events.create_event(state, "Sample", "2000-01-01", "Room", 2)
    storage.validate_state(state)
    assert main.list_events_view(state) == [
        {
            "event_id": event["event_id"],
            "title": "Sample",
            "date": "2000-01-01",
            "venue": "Room",
            "capacity": 2,
            "status": "active",
            "confirmed_count": 0,
            "waiting_count": 0,
        }
    ]


@pytest.mark.parametrize(
    "query,expected_ids",
    [
        ("Workshop", ["full"]),
        ("Annex", ["open"]),
        (" wOrKsHoP ", ["full"]),
        ("Room", ["closed", "full"]),
        ("", ["closed", "full", "open"]),
        (" \t ", ["closed", "full", "open"]),
        ("not-found", []),
        ("Closed", ["closed"]),
    ],
)
def test_keyword_views_reuse_matching_and_enrich_counts(state, query, expected_ids):
    state["events"]["full"]["title"] = "Workshop Room"
    state["events"]["open"]["venue"] = "Annex"
    state["events"]["closed"]["title"] = "Closed Event"
    storage.validate_state(state)
    before = deepcopy(state)
    rows = main.search_events_by_keyword_view(state, query)
    assert [row["event_id"] for row in rows] == expected_ids
    expected_counts = {"closed": (0, 0), "full": (2, 3), "open": (1, 0)}
    for row in rows:
        assert set(row) == VIEW_FIELDS
        assert (row["confirmed_count"], row["waiting_count"]) == expected_counts[
            row["event_id"]
        ]
    assert state == before


@pytest.mark.parametrize("query", [None, 1, [], {}])
def test_keyword_view_invalid_types_propagate_without_mutation(state, query):
    before = deepcopy(state)
    with pytest.raises(ValueError):
        main.search_events_by_keyword_view(state, query)
    assert state == before


@pytest.mark.parametrize(
    "date,expected_ids",
    [
        ("2024-02-29", ["closed", "full"]),
        ("2000-01-01", ["open"]),
        ("1999-01-01", []),
    ],
)
def test_date_views_preserve_exact_matching_and_order(state, date, expected_ids):
    state["events"]["open"]["date"] = "2000-01-01"
    storage.validate_state(state)
    before = deepcopy(state)
    rows = main.search_events_by_date_view(state, date)
    assert [row["event_id"] for row in rows] == expected_ids
    expected_counts = {"closed": (0, 0), "full": (2, 3), "open": (1, 0)}
    for row in rows:
        assert set(row) == VIEW_FIELDS
        assert (row["confirmed_count"], row["waiting_count"]) == expected_counts[
            row["event_id"]
        ]
    assert state == before


@pytest.mark.parametrize("date", ["", " ", "2024-2-29", "2023-02-29", None, 1])
def test_date_view_propagates_validation_errors(state, date):
    before = deepcopy(state)
    with pytest.raises(ValueError):
        main.search_events_by_date_view(state, date)
    assert state == before


@pytest.mark.parametrize("function,args", READ_CALLS[:3])
def test_each_view_result_is_independent(state, function, args):
    before = deepcopy(state)
    rows = getattr(main, function)(state, *args)
    expected = deepcopy(rows)
    rows[0]["title"] = "Changed"
    rows[0]["confirmed_count"] = 100
    rows.append({"unexpected": True})
    assert state == before
    assert getattr(main, function)(state, *args) == expected


@pytest.mark.parametrize(
    "reader,view,args",
    [
        ("list_events", "list_events_view", ()),
        ("search_by_keyword", "search_events_by_keyword_view", ("arbitrary",)),
        ("search_by_date", "search_events_by_date_view", ("delegated-date",)),
    ],
)
def test_views_delegate_to_domain_reader_and_enrich_only_matches(
    state, monkeypatch, reader, view, args
):
    # Deliberately nonstandard selection/order proves the wrapper does not refilter.
    selected = [events.get_event(state, "open"), events.get_event(state, "full")]
    before = deepcopy(selected)
    domain = Mock(return_value=selected)
    count = Mock(wraps=bookings.event_counts)
    monkeypatch.setattr(events, reader, domain)
    monkeypatch.setattr(bookings, "event_counts", count)
    rows = getattr(main, view)(state, *args)
    domain.assert_called_once_with(state, *args)
    assert [row["event_id"] for row in rows] == ["open", "full"]
    assert [call.args for call in count.call_args_list] == [
        (state, "open"),
        (state, "full"),
    ]
    assert selected == before
    rows[0]["title"] = "Changed"
    assert selected == before


def test_summary_mixed_state_exact_shape_and_totals(state):
    before = deepcopy(state)
    assert main.summary_report(state) == {
        "total_events": 3,
        "active_events": 2,
        "cancelled_events": 1,
        "confirmed_registrations": 3,
        "waiting_registrations": 3,
        # Full event contributes zero, open contributes 4 - 1, cancelled zero.
        "available_seats": 3,
        "most_registered_events": [
            {
                "event_id": "full",
                "title": "Sample Event",
                "confirmed_count": 2,
            }
        ],
    }
    # Student 001's confirmed registrations at two events both contribute.
    assert (
        state["bookings"]["c1"]["student_id"]
        == state["bookings"]["other"]["student_id"]
    )
    assert state == before


@pytest.mark.parametrize("kind", ["empty", "cancelled-only", "active-zero"])
def test_summary_empty_and_zero_cases(state, kind):
    if kind == "empty":
        state = storage.empty_state()
        total, active, cancelled, seats = 0, 0, 0, 0
    elif kind == "cancelled-only":
        state["events"] = {"closed": state["events"]["closed"]}
        state["bookings"] = {}
        total, active, cancelled, seats = 1, 0, 1, 0
    else:
        state["bookings"] = {}
        state["events"]["full"]["waiting_list"] = []
        total, active, cancelled, seats = 3, 2, 1, 6
    storage.validate_state(state)
    before = deepcopy(state)
    assert main.summary_report(state) == {
        "total_events": total,
        "active_events": active,
        "cancelled_events": cancelled,
        "confirmed_registrations": 0,
        "waiting_registrations": 0,
        "available_seats": seats,
        "most_registered_events": [],
    }
    assert state == before


def test_summary_positive_ties_use_date_then_id_not_insertion_order(state):
    # Both existing active events have two confirmed registrations.
    bookings.register_participant(state, "open", "006", "Sample Six")
    state["events"]["open"]["date"] = "2000-01-01"
    state["events"]["early"] = {
        **state["events"]["open"],
        "event_id": "early",
        "waiting_list": [],
    }
    for student in ["007", "008"]:
        bookings.register_participant(state, "early", student, "Sample")
    # An earlier zero-count event must never become a leader.
    state["events"]["zero"] = {
        **state["events"]["open"],
        "event_id": "zero",
        "date": "1990-01-01",
        "waiting_list": [],
    }
    storage.validate_state(state)
    before = deepcopy(state)
    report = main.summary_report(state)
    assert report["most_registered_events"] == [
        {"event_id": key, "title": "Sample Event", "confirmed_count": 2}
        for key in ["early", "open", "full"]
    ]
    assert report["confirmed_registrations"] == 6
    assert report["available_seats"] == 8
    assert state == before
    expected = deepcopy(report)
    report["most_registered_events"][0]["title"] = "Changed"
    report["most_registered_events"].clear()
    report["confirmed_registrations"] = 999
    assert state == before
    assert main.summary_report(state) == expected


def test_summary_later_larger_count_replaces_earlier_leader(state):
    bookings.register_participant(state, "open", "006", "Sample Six")
    bookings.register_participant(state, "open", "007", "Sample Seven")
    storage.validate_state(state)
    assert main.summary_report(state)["most_registered_events"] == [
        {
            "event_id": "open",
            "title": "Sample Event",
            "confirmed_count": 3,
        }
    ]


def test_summary_counts_each_active_event_once_and_skips_cancelled(state, monkeypatch):
    counts = Mock(wraps=bookings.event_counts)
    listing = Mock(wraps=events.list_events)
    monkeypatch.setattr(bookings, "event_counts", counts)
    monkeypatch.setattr(events, "list_events", listing)
    main.summary_report(state)
    listing.assert_called_once_with(state)
    assert [call.args for call in counts.call_args_list] == [
        (state, "full"),
        (state, "open"),
    ]


def test_capacity_orchestration_then_views_and_report(state, tmp_path):
    returned, _ = main.update_event_operation(state, tmp_path, "full", {"capacity": 4})
    assert storage.load_state(tmp_path) == returned
    storage.validate_state(returned)
    for rows in [
        main.list_events_view(returned),
        main.search_events_by_keyword_view(returned, "Sample"),
        main.search_events_by_date_view(returned, "2024-02-29"),
    ]:
        full = next(row for row in rows if row["event_id"] == "full")
        assert full["confirmed_count"] == 4
        assert full["waiting_count"] == 1
    assert returned["events"]["full"]["waiting_list"] == ["w3"]
    assert main.summary_report(returned) == {
        "total_events": 3,
        "active_events": 2,
        "cancelled_events": 1,
        "confirmed_registrations": 5,
        "waiting_registrations": 1,
        "available_seats": 3,
        "most_registered_events": [
            {
                "event_id": "full",
                "title": "Sample Event",
                "confirmed_count": 4,
            }
        ],
    }


def test_event_cancellation_then_views_and_report(state, tmp_path):
    returned, _ = main.cancel_event_operation(state, tmp_path, "full")
    assert storage.load_state(tmp_path) == returned
    storage.validate_state(returned)
    for rows in [
        main.list_events_view(returned),
        main.search_events_by_keyword_view(returned, "Sample"),
        main.search_events_by_date_view(returned, "2024-02-29"),
    ]:
        full = next(row for row in rows if row["event_id"] == "full")
        assert full["status"] == "cancelled"
        assert full["confirmed_count"] == full["waiting_count"] == 0
    assert main.summary_report(returned) == {
        "total_events": 3,
        "active_events": 1,
        "cancelled_events": 2,
        "confirmed_registrations": 1,
        "waiting_registrations": 0,
        "available_seats": 3,
        "most_registered_events": [
            {
                "event_id": "open",
                "title": "Sample Event",
                "confirmed_count": 1,
            }
        ],
    }


@pytest.mark.parametrize("function,args", READ_CALLS)
def test_reads_do_not_mutate_persist_validate_or_interact(
    state, tmp_path, monkeypatch, capsys, function, args
):
    storage.save_state(state, tmp_path)
    path = tmp_path / "eventhub.json"
    raw = path.read_bytes()
    before = deepcopy(state)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(storage, "save_state", Mock(side_effect=AssertionError("save")))
    monkeypatch.setattr(storage, "load_state", Mock(side_effect=AssertionError("load")))
    monkeypatch.setattr(
        storage, "validate_state", Mock(side_effect=AssertionError("validate"))
    )
    monkeypatch.setattr(
        main, "deepcopy", Mock(side_effect=AssertionError("whole-state copy"))
    )
    monkeypatch.setattr("builtins.input", Mock(side_effect=AssertionError("input")))
    getattr(main, function)(state, *args)
    assert state == before
    assert path.read_bytes() == raw
    assert list(tmp_path.iterdir()) == [path]
    assert capsys.readouterr() == ("", "")
