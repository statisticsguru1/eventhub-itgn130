"""Console boundaries over real application operations and temporary snapshots."""

from copy import deepcopy
import importlib.util
from pathlib import Path
from unittest.mock import Mock
from uuid import UUID

import pytest

import bookings
import main
import storage


@pytest.fixture
def state():
    value = storage.empty_state()
    for key, status, capacity in [
        ("e1", "active", 1),
        ("e2", "active", 3),
        ("e3", "cancelled", 9),
    ]:
        value["events"][key] = {
            "event_id": key,
            "title": f"Sample {key}",
            "date": "2024-02-29",
            "venue": "Room A",
            "capacity": capacity,
            "status": status,
            "waiting_list": [],
        }
    for key, student, status in [
        ("internal-confirmed", "001", "confirmed"),
        ("internal-waiter-first", "002", "waiting"),
        ("internal-waiter-second", "003", "waiting"),
    ]:
        value["bookings"][key] = {
            "booking_id": key,
            "event_id": "e1",
            "student_id": student,
            "student_name": f"Student {student}",
            "status": status,
        }
    value["events"]["e1"]["waiting_list"] = [
        "internal-waiter-first",
        "internal-waiter-second",
    ]
    storage.validate_state(value)
    return value


@pytest.fixture
def console(monkeypatch, tmp_path):
    monkeypatch.setattr(main, "DEFAULT_DATA_DIR", tmp_path)

    def script(answers):
        remaining = iter(answers)
        prompts = []

        def read(prompt):
            prompts.append(prompt)
            try:
                answer = next(remaining)
            except StopIteration:
                raise AssertionError(
                    "Console requested unexpected additional input"
                ) from None
            if answer == "$event":
                return next(iter(storage.load_state(tmp_path)["events"]))
            return answer

        monkeypatch.setattr("builtins.input", read)
        return prompts

    return script


def assert_no_booking_ids(output, state):
    for booking_id in state["bookings"]:
        assert booking_id not in output


def test_import_has_no_startup_or_console_side_effects(monkeypatch, tmp_path, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(storage, "load_state", Mock(side_effect=AssertionError("load")))
    monkeypatch.setattr(storage, "save_state", Mock(side_effect=AssertionError("save")))
    monkeypatch.setattr("builtins.input", Mock(side_effect=AssertionError("input")))
    monkeypatch.setattr(Path, "mkdir", Mock(side_effect=AssertionError("mkdir")))
    spec = importlib.util.spec_from_file_location("console_import_check", main.__file__)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert capsys.readouterr() == ("", "")
    assert list(tmp_path.iterdir()) == []


def test_first_run_exit_loads_empty_without_creating_files(
    console, tmp_path, monkeypatch, capsys
):
    load = Mock(wraps=storage.load_state)
    monkeypatch.setattr(storage, "load_state", load)
    console(["9"])
    main.main()
    load.assert_called_once_with(tmp_path)
    out = capsys.readouterr().out
    assert "No saved data found. Starting with an empty dataset." in out
    assert "EVENTHUB — EVENT REGISTRATION & BOOKING MANAGEMENT" in out
    for text in [
        "1. Add event",
        "2. Edit event",
        "3. List events",
        "4. Search events",
        "5. Cancel event",
        "6. Register participant",
        "7. Cancel registration",
        "8. View summary report",
        "9. Exit",
        "Goodbye.",
    ]:
        assert text in out
    assert not list(tmp_path.iterdir())


def test_valid_startup_passes_loaded_state_to_menu(
    state, tmp_path, monkeypatch, capsys
):
    storage.save_state(state, tmp_path)
    menu = Mock()
    monkeypatch.setattr(main, "DEFAULT_DATA_DIR", tmp_path)
    monkeypatch.setattr(main, "run_menu", menu)
    main.main()
    menu.assert_called_once_with(state, tmp_path)
    assert "No saved data" not in capsys.readouterr().out


@pytest.mark.parametrize(
    "raw", [b"{", b'{"schema_version": 2, "events": {}, "bookings": {}}']
)
def test_invalid_startup_preserves_file_and_never_enters_menu(
    tmp_path, monkeypatch, capsys, raw
):
    path = tmp_path / "eventhub.json"
    path.write_bytes(raw)
    monkeypatch.setattr(main, "DEFAULT_DATA_DIR", tmp_path)
    menu = Mock(side_effect=AssertionError("menu"))
    monkeypatch.setattr(main, "run_menu", menu)
    main.main()
    menu.assert_not_called()
    assert "Unable to start EventHub:" in capsys.readouterr().out
    assert path.read_bytes() == raw
    assert list(tmp_path.iterdir()) == [path]


def test_abandoned_first_save_is_not_discarded(tmp_path, monkeypatch, capsys):
    artifact = tmp_path / "eventhub-abandoned.tmp"
    artifact.write_text("unsaved")
    monkeypatch.setattr(main, "DEFAULT_DATA_DIR", tmp_path)
    menu = Mock()
    monkeypatch.setattr(main, "run_menu", menu)
    main.main()
    menu.assert_not_called()
    out = capsys.readouterr().out
    assert "Unable to start EventHub:" in out and "review" in out
    assert "Starting with an empty" not in out
    assert artifact.read_text() == "unsaved"
    assert not (tmp_path / "eventhub.json").exists()


def test_startup_oserror_is_controlled(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(main, "DEFAULT_DATA_DIR", tmp_path)
    monkeypatch.setattr(
        storage, "load_state", Mock(side_effect=PermissionError("denied"))
    )
    menu = Mock()
    monkeypatch.setattr(main, "run_menu", menu)
    main.main()
    menu.assert_not_called()
    assert capsys.readouterr().out == "Unable to start EventHub: denied\n"


def test_invalid_choice_loops_and_strips_choice(console, tmp_path, capsys):
    console(["bad", "", " 9 "])
    main.run_menu(storage.empty_state(), tmp_path)
    out = capsys.readouterr().out
    assert out.count("Invalid choice. Please select 1–9.") == 2
    assert out.count("EVENTHUB —") == 3
    assert out.endswith("Goodbye.\n")


def test_add_event_converts_capacity_persists_and_shows_id(console, tmp_path, capsys):
    console(["1", " New ", "2024-02-29", " Hall ", "2", "3", "9"])
    main.run_menu(storage.empty_state(), tmp_path)
    saved = storage.load_state(tmp_path)
    event = next(iter(saved["events"].values()))
    assert event["capacity"] == 2 and type(event["capacity"]) is int
    out = capsys.readouterr().out
    assert f"Event created: {event['event_id']} — New" in out
    assert "Title: New" in out and "Confirmed: 0 | Waiting: 0" in out


@pytest.mark.parametrize(
    "capacity,date,message",
    [
        ("fraction", "2024-02-29", "Capacity must be a whole number."),
        ("0", "2024-02-29", "positive integer"),
        ("-1", "2024-02-29", "positive integer"),
        ("2", "2023-02-29", "real calendar"),
    ],
)
def test_add_rejection_has_no_false_success_or_file(
    console, tmp_path, capsys, capacity, date, message
):
    console(["1", "New", date, "Hall", capacity, "9"])
    main.run_menu(storage.empty_state(), tmp_path)
    out = capsys.readouterr().out
    assert "Error:" in out and message in out
    assert "Event created:" not in out
    assert not (tmp_path / "eventhub.json").exists()


@pytest.mark.parametrize(
    "entries,expected",
    [
        ([" New ", "", "", ""], {"title": "New"}),
        (
            ["New", "2000-01-01", "Hall", "4"],
            {"title": "New", "date": "2000-01-01", "venue": "Hall", "capacity": 4},
        ),
    ],
)
def test_edit_current_values_optional_fields_and_persistence(
    state, console, tmp_path, capsys, entries, expected
):
    before = deepcopy(state)
    console(["2", "e2", *entries, "3", "9"])
    main.run_menu(state, tmp_path)
    saved = storage.load_state(tmp_path)
    before["events"]["e2"].update(expected)
    assert saved == before
    out = capsys.readouterr().out
    assert "ID: e2" in out and "Title: Sample e2" in out
    assert "Capacity: 3 | Status: active" in out
    assert "Event updated: e2." in out
    assert_no_booking_ids(out, state)


def test_all_blank_edit_calls_operation_without_saving(
    state, console, tmp_path, monkeypatch, capsys
):
    update = Mock(wraps=main.update_event_operation)
    monkeypatch.setattr(main, "update_event_operation", update)
    save = Mock(side_effect=AssertionError("save"))
    monkeypatch.setattr(storage, "save_state", save)
    console(["2", "e2", "", "", "", "", "9"])
    main.run_menu(state, tmp_path)
    update.assert_called_once_with(state, tmp_path, "e2", {})
    save.assert_not_called()
    assert "No changes made." in capsys.readouterr().out


@pytest.mark.parametrize(
    "event_id,entries,message",
    [
        ("e2", ["", "", "", "bad"], "Capacity must be a whole number."),
        ("e3", ["", "", "", ""], "Cancelled events cannot be edited."),
        ("missing", [], "Unknown event ID: missing"),
        ("e2", [" ", "", "", ""], "nonempty string"),
    ],
)
def test_edit_errors_are_controlled(
    state, console, tmp_path, capsys, event_id, entries, message
):
    console(["2", event_id, *entries, "9"])
    main.run_menu(state, tmp_path)
    out = capsys.readouterr().out
    assert "Error:" in out and message in out
    assert "Event updated:" not in out and "No changes made." not in out
    assert not (tmp_path / "eventhub.json").exists()


def test_capacity_reduction_below_attendance_is_rejected(
    state, console, tmp_path, capsys
):
    bookings.register_participant(state, "e2", "011", "Eleven")
    bookings.register_participant(state, "e2", "012", "Twelve")
    console(["2", "e2", "", "", "", "1", "9"])
    main.run_menu(state, tmp_path)
    out = capsys.readouterr().out
    assert "below confirmed attendance" in out
    assert "Event updated:" not in out


def test_edit_increase_displays_promotion_count_without_ids(
    state, console, tmp_path, capsys
):
    console(["2", "e1", "", "", "", "2", "3", "9"])
    main.run_menu(state, tmp_path)
    out = capsys.readouterr().out
    assert "Promoted from waiting list: 1" in out
    assert "Confirmed: 2 | Waiting: 1" in out
    assert_no_booking_ids(out, state)
    assert (
        storage.load_state(tmp_path)["bookings"]["internal-waiter-first"]["status"]
        == "confirmed"
    )


def test_list_displays_all_fields_and_no_internal_queue(
    state, console, tmp_path, capsys
):
    console(["3", "9"])
    main.run_menu(state, tmp_path)
    out = capsys.readouterr().out
    for text in [
        "ID: e1",
        "Title: Sample e1",
        "Date: 2024-02-29 | Venue: Room A",
        "Capacity: 1 | Status: active",
        "Confirmed: 1 | Waiting: 2",
        "Status: cancelled",
    ]:
        assert text in out
    assert_no_booking_ids(out, state)
    assert "waiting_list" not in out


def test_list_empty(console, tmp_path, capsys):
    console(["3", "9"])
    main.run_menu(storage.empty_state(), tmp_path)
    assert "No events found." in capsys.readouterr().out


@pytest.mark.parametrize(
    "search_answers,expected",
    [
        (["1", "e1"], "Title: Sample e1"),
        (["1", ""], "Title: Sample e3"),
        (["2", "2024-02-29"], "Confirmed: 1 | Waiting: 2"),
        (["1", "no-match"], "No events found."),
        (["2", "2023-02-29"], "Error: Date must be a real calendar date."),
        (["bad"], "Invalid choice. Please select 1–3."),
    ],
)
def test_search_submenu_returns_to_main(
    state, console, tmp_path, capsys, search_answers, expected
):
    console(["4", *search_answers, "3", "9"])
    main.run_menu(state, tmp_path)
    out = capsys.readouterr().out
    assert "SEARCH EVENTS" in out and expected in out
    assert out.endswith("Goodbye.\n")
    assert_no_booking_ids(out, state)


def test_search_recovers_from_error_with_another_search(
    state, console, tmp_path, capsys
):
    console(["4", "2", "bad-date", "1", "e3", "3", "9"])
    main.run_menu(state, tmp_path)
    out = capsys.readouterr().out
    assert "Error:" in out and "Title: Sample e3" in out
    assert "Status: cancelled" in out


def test_event_cancellation_and_repeat_messages(state, console, tmp_path, capsys):
    console(["5", "e1", "5", "e1", "3", "9"])
    main.run_menu(state, tmp_path)
    out = capsys.readouterr().out
    assert "Event cancelled. Removed 3 registration(s)." in out
    assert "Event is already cancelled. No changes made." in out
    assert "Confirmed: 0 | Waiting: 0" in out
    assert_no_booking_ids(out, state)
    saved = storage.load_state(tmp_path)
    assert saved["bookings"] == {} and saved["events"]["e1"]["waiting_list"] == []


@pytest.mark.parametrize(
    "event_id,status,message",
    [
        ("e2", "confirmed", "Registration confirmed for 00Ab — Sample Name."),
        ("e1", "waiting", "Added to waiting list: 00Ab — Sample Name."),
    ],
)
def test_registration_output_preserves_student_identity(
    state, console, tmp_path, capsys, event_id, status, message
):
    console(["6", event_id, " 00Ab ", " Sample Name ", "9"])
    main.run_menu(state, tmp_path)
    saved = storage.load_state(tmp_path)
    booking = bookings.find_registration(saved, event_id, "00Ab")
    assert booking["status"] == status and booking["student_id"] == "00Ab"
    out = capsys.readouterr().out
    assert message in out
    assert_no_booking_ids(out, saved)


@pytest.mark.parametrize(
    "event_id,student_id,message",
    [
        ("e1", "001", "already has a registration"),
        ("e3", "001", "requires an active event"),
    ],
)
def test_registration_error_has_no_success(
    state, console, tmp_path, capsys, event_id, student_id, message
):
    console(["6", event_id, student_id, "Sample", "9"])
    main.run_menu(state, tmp_path)
    out = capsys.readouterr().out
    assert "Error:" in out and message in out
    assert (
        "Registration confirmed for" not in out and "Added to waiting list:" not in out
    )


@pytest.mark.parametrize("student_id,promotion", [("001", True), ("002", False)])
def test_cancel_registration_outputs_participant_and_promotion(
    state, console, tmp_path, capsys, student_id, promotion
):
    console(["7", "e1", student_id, "9"])
    main.run_menu(state, tmp_path)
    out = capsys.readouterr().out
    assert f"Registration cancelled for {student_id} — Student {student_id}." in out
    if promotion:
        assert "Promoted from waiting list: 002 — Student 002." in out
    else:
        assert "Promoted from waiting list:" not in out
    assert_no_booking_ids(out, state)


def test_confirmed_cancel_without_waiter(state, console, tmp_path, capsys):
    bookings.register_participant(state, "e2", "010", "Ten")
    console(["7", "e2", "010", "9"])
    main.run_menu(state, tmp_path)
    out = capsys.readouterr().out
    assert "Registration cancelled for 010 — Ten." in out
    assert "Promoted from waiting list:" not in out


def test_unknown_registration_keyerror_has_no_extra_quotes(
    state, console, tmp_path, capsys
):
    console(["7", "e1", "missing", "9"])
    main.run_menu(state, tmp_path)
    out = capsys.readouterr().out
    assert "Error: No registration for student missing at event e1." in out
    assert "Error: '" not in out and 'Error: "' not in out


@pytest.mark.parametrize("kind", ["none", "one", "ties"])
def test_report_display_uses_one_report_call(
    state, console, tmp_path, monkeypatch, capsys, kind
):
    if kind == "none":
        state = storage.empty_state()
    elif kind == "ties":
        bookings.register_participant(state, "e2", "010", "Ten")
    expected = main.summary_report(state)
    summary = Mock(wraps=main.summary_report)
    monkeypatch.setattr(main, "summary_report", summary)
    console(["8", "9"])
    main.run_menu(state, tmp_path)
    summary.assert_called_once_with(state)
    out = capsys.readouterr().out
    assert "SUMMARY REPORT" in out and "Most registered event(s):" in out
    for label, key in [
        ("Total events", "total_events"),
        ("Active events", "active_events"),
        ("Cancelled events", "cancelled_events"),
        ("Confirmed registrations", "confirmed_registrations"),
        ("Waiting registrations", "waiting_registrations"),
        ("Available seats", "available_seats"),
    ]:
        assert f"{label}: {expected[key]}" in out
    if kind == "none":
        assert "No confirmed registrations." in out
    else:
        for leader in expected["most_registered_events"]:
            assert (
                f"{leader['event_id']} — {leader['title']} — {leader['confirmed_count']} confirmed"
                in out
            )


MUTATIONS = [
    ("create_event_operation", ["1", "New", "2024-02-29", "Room", "1"]),
    ("update_event_operation", ["2", "e1", "", "", "", "2"]),
    ("cancel_event_operation", ["5", "e1"]),
    ("register_participant_operation", ["6", "e2", "010", "Ten"]),
    ("cancel_registration_operation", ["7", "e1", "001"]),
]


@pytest.mark.parametrize("operation,answers", MUTATIONS)
def test_every_mutation_adopts_returned_state_for_next_read(
    state, console, tmp_path, monkeypatch, operation, answers
):
    real_operation = getattr(main, operation)
    real_list = main.list_events_view
    committed = []
    before = deepcopy(state)

    def mutate(*args):
        result = real_operation(*args)
        committed.append(result[0])
        return result

    def inspect_read(active):
        assert len(committed) == 1
        assert active is committed[0]
        assert storage.load_state(tmp_path) == active
        return real_list(active)

    monkeypatch.setattr(main, operation, mutate)
    monkeypatch.setattr(main, "list_events_view", inspect_read)
    console([*answers, "3", "9"])
    main.run_menu(state, tmp_path)
    assert state == before


@pytest.mark.parametrize("operation,answers", MUTATIONS)
def test_every_failed_mutation_retains_active_state(
    state, console, tmp_path, monkeypatch, capsys, operation, answers
):
    before = deepcopy(state)
    read = Mock(wraps=main.list_events_view)
    monkeypatch.setattr(main, operation, Mock(side_effect=OSError("operation denied")))
    monkeypatch.setattr(main, "list_events_view", read)
    console([*answers, "3", "9"])
    main.run_menu(state, tmp_path)
    read.assert_called_once_with(state)
    assert read.call_args.args[0] is state
    assert state == before
    out = capsys.readouterr().out
    assert "Error: operation denied" in out
    assert "Confirmed: 1 | Waiting: 2" in out
    for success in [
        "Event created:",
        "Event updated:",
        "Event cancelled.",
        "Registration confirmed for",
        "Registration cancelled for",
    ]:
        assert success not in out


def test_real_save_failure_preserves_file_and_menu_state(
    state, console, tmp_path, monkeypatch, capsys
):
    storage.save_state(state, tmp_path)
    raw = (tmp_path / "eventhub.json").read_bytes()
    monkeypatch.setattr(
        storage.os, "replace", Mock(side_effect=OSError("replace denied"))
    )
    console(["2", "e1", "", "", "", "2", "3", "8", "9"])
    main.run_menu(state, tmp_path)
    out = capsys.readouterr().out
    assert "Error: replace denied" in out and "Event updated:" not in out
    assert "Confirmed: 1 | Waiting: 2" in out
    assert "Confirmed registrations: 1" in out
    assert (tmp_path / "eventhub.json").read_bytes() == raw


def test_postcommit_cleanup_warning_adopts_committed_state(
    state, console, tmp_path, monkeypatch, capsys, caplog
):
    real_unlink = Path.unlink

    def fail_cleanup(path, *args, **kwargs):
        if path.suffix == ".tmp":
            raise OSError("cleanup warning")
        return real_unlink(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", fail_cleanup)
    console(["2", "e1", "", "", "", "2", "3", "8", "9"])
    main.run_menu(state, tmp_path)
    out = capsys.readouterr().out
    assert "Event updated: e1." in out and "Error:" not in out
    assert "Confirmed: 2 | Waiting: 1" in out
    assert "Confirmed registrations: 2" in out
    assert "cleanup warning" in caplog.text
    assert (
        bookings.event_counts(storage.load_state(tmp_path), "e1")["confirmed_count"]
        == 2
    )


def test_read_actions_and_exit_never_save(state, console, tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "save_state", Mock(side_effect=AssertionError("save")))
    console(["3", "4", "1", "", "2", "2024-02-29", "3", "8", "9"])
    main.run_menu(state, tmp_path)
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize(
    "function,answers",
    [
        ("create_event_operation", ["1", "New", "2024-02-29", "Room", "1"]),
        ("list_events_view", ["3"]),
        ("search_events_by_keyword_view", ["4", "1", ""]),
    ],
)
def test_unexpected_programming_error_propagates(
    state, console, tmp_path, monkeypatch, capsys, function, answers
):
    monkeypatch.setattr(
        main, function, Mock(side_effect=RuntimeError("programming bug"))
    )
    console(answers)
    with pytest.raises(RuntimeError, match="programming bug"):
        main.run_menu(state, tmp_path)
    assert "Error:" not in capsys.readouterr().out


@pytest.mark.parametrize("signal", [EOFError, KeyboardInterrupt])
@pytest.mark.parametrize("prefix", [[], ["1", "Unfinished"]])
def test_closed_input_exits_gracefully_without_save(
    console, tmp_path, monkeypatch, capsys, signal, prefix
):
    answers = iter(prefix)

    def read(prompt):
        try:
            return next(answers)
        except StopIteration:
            raise signal

    monkeypatch.setattr("builtins.input", read)
    main.main()
    assert "Session ended." in capsys.readouterr().out
    assert not (tmp_path / "eventhub.json").exists()


def test_console_demonstration_register_wait_cancel_promote_reload(
    console, tmp_path, capsys
):
    console(
        [
            "1",
            "Demo",
            "2024-02-29",
            "Hall",
            "1",
            "6",
            "$event",
            "001",
            "Participant A",
            "6",
            "$event",
            "002",
            "Participant B",
            "3",
            "4",
            "1",
            "Demo",
            "3",
            "7",
            "$event",
            "001",
            "3",
            "8",
            "9",
        ]
    )
    main.main()
    out = capsys.readouterr().out
    assert "Registration confirmed for 001 — Participant A." in out
    assert "Added to waiting list: 002 — Participant B." in out
    assert "Confirmed: 1 | Waiting: 1" in out
    assert "Promoted from waiting list: 002 — Participant B." in out
    assert "Confirmed: 1 | Waiting: 0" in out
    assert "Confirmed registrations: 1" in out and "Waiting registrations: 0" in out
    assert "Available seats: 0" in out and "Goodbye." in out
    saved = storage.load_state(tmp_path)
    storage.validate_state(saved)
    event_id = next(iter(saved["events"]))
    assert len(saved["bookings"]) == 1
    booking = bookings.find_registration(saved, event_id, "002")
    assert booking["status"] == "confirmed"
    assert saved["events"][event_id]["waiting_list"] == []
    assert_no_booking_ids(out, saved)


def test_booking_id_collision_is_sanitized_without_mutation_or_save(
    state, console, tmp_path, monkeypatch, capsys
):
    # Use a real UUID booking ID in a valid state; the next generation collides.
    existing = bookings.register_participant(state, "e2", "010", "Existing Student")
    booking_id = existing["booking_id"]
    storage.validate_state(state)
    before = deepcopy(state)
    storage.save_state(state, tmp_path)
    path = tmp_path / "eventhub.json"
    raw = path.read_bytes()
    monkeypatch.setattr(bookings.uuid, "uuid4", lambda: UUID(booking_id))
    save = Mock(wraps=storage.save_state)
    monkeypatch.setattr(storage, "save_state", save)

    # The domain still supplies its original detailed collision diagnostic.
    with pytest.raises(ValueError) as caught:
        bookings.register_participant(state, "e2", "011", "New Student")
    assert str(caught.value) == f"Generated booking ID already exists: {booking_id}"
    assert state == before

    console(["6", "e2", "011", "New Student", "3", "8", "9"])
    main.run_menu(state, tmp_path)
    out = capsys.readouterr().out
    assert (
        "Error: Could not allocate a unique registration ID. Please try again." in out
    )
    assert booking_id not in out
    assert "Generated booking ID already exists:" not in out
    assert "Registration confirmed" not in out
    assert "Added to waiting list" not in out
    assert "Title: Sample e2" in out
    assert "Confirmed registrations: 2" in out
    assert out.endswith("Goodbye.\n")
    save.assert_not_called()
    assert state == before
    assert state["bookings"] == before["bookings"]
    assert path.read_bytes() == raw
    assert storage.load_state(tmp_path) == before
